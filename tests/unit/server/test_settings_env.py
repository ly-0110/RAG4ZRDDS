"""settings 层 .env → os.environ 导出的回归测试（2026-08-31）。

背景：generation/llm.py 经 os.getenv 读 LLM_*；此前仓库没有任何
load_dotenv 调用，pydantic-settings 只填充自身声明字段、不导出其余键，
导致 .env 填好 LLM 配置、RAG_MODE=live 启动仍报"生成侧 LLM 未配置"
（C 交付物 0f69600 接线后暴露）。本测试锁定修复：仓库根 .env 必须被
导出进 os.environ，且行内注释被剥离。
"""

from __future__ import annotations

from generation.llm import LLMConfig
from server.core.settings import load_env_file


def test_load_env_file_exports_llm_vars_for_os_getenv(tmp_path, monkeypatch):
    for key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 整行注释不应产生变量\n"
        "LLM_BASE_URL=https://openrouter.ai/api/v1   # OpenRouter 网关\n"
        "LLM_API_KEY=sk-test-key      # 换成你的 Key（行内注释）\n"
        "LLM_MODEL=minimax/minimax-m3:free   # :free=免费但限速\n",
        encoding="utf-8",
    )

    load_env_file(env_file)

    cfg = LLMConfig.from_env("LLM_")  # 走 os.getenv，等价于服务启动期的读取路径
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.api_key == "sk-test-key"  # 行内注释不得混入密钥
    assert cfg.model == "minimax/minimax-m3:free"


def test_load_env_file_does_not_override_existing_env(tmp_path, monkeypatch):
    """进程已有同名环境变量时优先进程值（与 pydantic-settings 的优先级一致）。"""
    monkeypatch.setenv("LLM_MODEL", "from-process-env")
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=from-dotenv-file\n", encoding="utf-8")

    load_env_file(env_file)

    import os

    assert os.environ["LLM_MODEL"] == "from-process-env"
