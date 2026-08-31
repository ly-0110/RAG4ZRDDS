"""LLM 客户端：读 .env 的 OpenAI 兼容配置，产出流式回答（指南 §5 成员 C 第一条）。

约定：
  * 密钥进 .env（不入 Git），经环境变量读取；前缀由实验配置
    generation.llm_env_prefix 决定（默认 LLM_）；
  * 任何 OpenAI 兼容服务（DeepSeek / Qwen / Moonshot …）都可经 LLM_BASE_URL 接入；
  * openai SDK 延迟导入，未安装时给出可读错误而非 ImportError 崩溃；
  * 连接/鉴权错误原样上抛，交由 /query 的 SSE error 事件上报（可读回显）。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """一次生成所需的 LLM 配置；provider 为前瞻字段，第一周统一走 OpenAI 兼容。"""

    provider: str
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls, prefix: str = "LLM_") -> "LLMConfig":
        def read(name: str) -> str:
            return (os.getenv(prefix + name) or "").strip()

        provider = read("PROVIDER") or "openai"
        base_url = read("BASE_URL")
        api_key = read("API_KEY")
        model = read("MODEL")
        missing = [
            n for n, v in (("BASE_URL", base_url), ("API_KEY", api_key), ("MODEL", model)) if not v
        ]
        if missing:
            raise RuntimeError(
                "生成侧 LLM 未配置：缺少环境变量 "
                + "、".join(f"{prefix}{n}" for n in missing)
                + "。请在仓库根 .env 中填写（模板见 .env.example），密钥不入 Git。"
            )
        return cls(provider=provider, base_url=base_url, api_key=api_key, model=model)


async def stream_chat(
    config: LLMConfig, messages: list[dict[str, str]]
) -> AsyncIterator[str]:
    """OpenAI 兼容 /chat/completions 流式调用，逐段产出回答文本增量。"""
    try:
        from openai import AsyncOpenAI
    except ImportError as e:  # pragma: no cover —— 依赖缺失时给可读错误
        raise RuntimeError(
            "缺少 openai SDK：请先 pip install openai（或 make setup）；"
            "requirements.txt 已锁定 openai==2.46.0"
        ) from e

    client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
    try:
        stream = await client.chat.completions.create(
            model=config.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                yield content
    finally:
        await client.close()
