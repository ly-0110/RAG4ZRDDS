"""run_experiment 直调时加载仓库根 .env 的回归测试（2026-09-17）。

背景：答案侧评测（`evaluation.response_metrics` 非空 → `make answer-eval`、
`make experiment CFG=final_v1.yaml`）走 generation.llm 的 os.getenv 读
LLM_*，而脚本并不经服务启动路径（server.core.settings 的模块级加载）。
结果 `.env` 填好 LLM 配置、`make answer-eval` 仍直接报"生成侧 LLM 未配置：
缺少环境变量 LLM_BASE_URL/LLM_API_KEY/LLM_MODEL"并退出（实测复现）。

与 2026-08-31 `build_pipeline` live 分支同类缺陷（同一根因：os.getenv 通路
没人导出 .env），修法与既有 server 侧测试同源：显式调用 load_env_file()。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_experiment as rx  # noqa: E402

from generation.llm import LLMConfig  # noqa: E402


def test_load_dotenv_exports_repo_env_for_llm_config(tmp_path, monkeypatch):
    """_load_dotenv 后 LLMConfig.from_env（os.getenv 通路）应能读到 .env 的值。"""
    from server.core import settings

    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://127.0.0.1:11500/v1   # 本地网关\n"
        "LLM_API_KEY=sk-local\n"
        "LLM_MODEL=qwen3.5-9b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)

    rx._load_dotenv()

    cfg = LLMConfig.from_env("LLM_")
    assert cfg.base_url == "http://127.0.0.1:11500/v1"
    assert cfg.model == "qwen3.5-9b"


def test_answer_eval_generate_loads_env_for_real_path(tmp_path, monkeypatch):
    """回答侧 runner 的真实通路（chat_stream=None）同样要自己加载 .env。

    `make abstention` / `answer_eval` CLI 直调时无人导出 .env，修前直接报
    "生成侧 LLM 未配置"（2026-09-17 实测复现；与 run_experiment 同一根因）。
    """
    import asyncio
    import os
    from types import SimpleNamespace

    import generation.query_engine as qe
    from evaluation.runners import answer_eval as ae
    from server.core import settings

    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://127.0.0.1:11500/v1\n"
        "LLM_API_KEY=sk-local\n"
        "LLM_MODEL=qwen3.5-9b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)

    class _Stream:
        async def stream(self, question, chunks):
            yield "ok"

    monkeypatch.setattr(qe, "build_answer_stream", lambda cfg: _Stream())
    cfg = SimpleNamespace(
        generation=SimpleNamespace(prompt_version="v2"),
        retrieval=SimpleNamespace(source_priority=[]),
    )

    out = asyncio.run(ae._generate(cfg, "问题", [], None))

    assert out == "ok"
    assert os.environ["LLM_BASE_URL"] == "http://127.0.0.1:11500/v1"


def test_main_loads_dotenv_before_llm_env_check(monkeypatch):
    """顺序锁：main() 必须在 LLM 前置校验之前加载 .env。

    否则 final_v1 这类 response_metrics 非空的配置会在任何检索/生成之前
    就以"未配置"失败（这正是修复前 `make answer-eval` 的实测行为）。
    """
    calls: list[str] = []
    monkeypatch.setattr(rx, "_load_dotenv", lambda: calls.append("dotenv"))

    class _StopHere(RuntimeError):
        pass

    def fake_from_env(prefix):
        calls.append("llm")
        raise _StopHere()  # 停在 LLM 校验处：后半程需要真实索引/模型

    monkeypatch.setattr("generation.llm.LLMConfig.from_env", staticmethod(fake_from_env))

    with pytest.raises(_StopHere):
        rx.main(["--config", "configs/experiments/final_v1.yaml"])

    assert calls == ["dotenv", "llm"]
