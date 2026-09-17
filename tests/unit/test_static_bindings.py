"""源码级静态检查：模块被使用但从未导入（NameError 类缺陷的护栏）。

起因是一类真实缺陷：`server/core/pipeline.py` 的 live 启动路径用了 `os.getenv`
但模块没有 `import os`，`data_pipeline/chunkers/base.py` 用了 `re.finditer`
但只导入了 `json, tiktoken`。两处都不会被导入期捕获，`pytest` 全绿也照样过——
直到真的跑到那一行才 `NameError`（前者直接让 live 模式起不来）。

判据保守但足够抓真问题：只检查"以裸名字访问属性"（`os.getenv` 这类）且该名字
从未在本模块内被绑定（导入 / 赋值 / def / 参数 / 类名 / except 别名）。
名字一旦在本模块任意作用域绑定即放过，因此不会对参数名巧合报错。
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "cypress"}

# 常用作 `<name>.<attr>` 的模块名（含常见别名）。只查这些，避免把业务对象误判成模块。
MODULE_NAMES = """
os sys json re time random hashlib shutil subprocess asyncio datetime math copy itertools
functools warnings logging uuid base64 tempfile urllib socket threading traceback contextvars
enum dataclasses collections typing pathlib io csv glob statistics string secrets platform
numpy pandas matplotlib yaml np pd plt
""".split()


def _bound_names(tree: ast.AST) -> set[str]:
    """模块内出现过的所有名字绑定（作用域不敏感：取宽松口径，只求不误报）。"""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.Global):
            bound.update(node.names)
    return bound


def _module_attr_uses(tree: ast.AST) -> set[str]:
    """以裸名字访问属性的名字集合，如 `os.getenv` → {"os"}。"""
    return {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }


def _repo_python_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def test_收集到的源文件非空():
    """护栏自身的前提：确实扫到了源码，避免目录结构变化后静默变成空转。"""
    files = _repo_python_files()
    assert len(files) > 50, f"只扫到 {len(files)} 个文件，检查 REPO_ROOT 与 SKIP_PARTS"
    names = {p.name for p in files}
    assert "pipeline.py" in names and "base.py" in names


def test_没有用到未导入的模块():
    offenders: list[str] = []
    for path in _repo_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        bound = _bound_names(tree)
        for name in sorted(_module_attr_uses(tree) & set(MODULE_NAMES)):
            if name not in bound:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: 用了 {name}.… 但未导入 {name}")
    assert not offenders, "存在'用了没导入'的模块引用（运行到该行会 NameError）：\n" + "\n".join(offenders)


def test_扫描器能抓出缺失导入():
    """给护栏本身上一道锁：构造一个缺导入的样本，扫描逻辑必须报出来。"""
    sample = ast.parse("def f():\n    return os.getenv('X')\n")
    bound = _bound_names(sample)
    used = _module_attr_uses(sample)
    assert "os" in used and "os" not in bound, "扫描器未能识别缺失导入，护栏失效"


def test_live_启动路径依赖的模块已就位():
    """具体锁定两处历史缺陷：live 接线用 os、分块基类用 re。"""
    import data_pipeline.chunkers.base as base_mod
    import server.core.pipeline as pipeline_mod

    assert hasattr(pipeline_mod, "os"), "pipeline.py 缺 import os：live 模式启动会 NameError"
    assert hasattr(base_mod, "re"), "base.py 缺 import re：_protect_code_tables 会 NameError"
