"""生成域（generation/）的单元测试。

不联网、不依赖真实 LLM：chat_stream 用确定性假实现注入；
LLM 环境变量用 monkeypatch 临时设置/清除。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from generation.query_engine import AnswerStream, build_answer_stream
from generation.context_builder import build_context
from generation.llm import LLMConfig
from generation.prompts import v0


def _chunk(node_id="n1", text="正文", **kw) -> dict:
    base = {
        "node_id": node_id,
        "text": text,
        "source_id": "user_manual",
        "source_name": "ZRDDS用户手册.pdf",
        "section": "3.4",
        "page_print": 36,
        "page_physical": 42,
        "score": 0.9,
    }
    base.update(kw)
    return base


def _fake_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        generation=SimpleNamespace(llm_env_prefix="LLM_", prompt_version="v0")
    )


async def _collect(stream: AnswerStream, question: str, chunks: list[dict]) -> str:
    return "".join([t async for t in stream.stream(question, chunks)])


# ---------------------------------------------------------------- context


def test_build_context_formats_numbered_blocks():
    chunks = [
        _chunk(node_id="n1", text="第一段正文", section="3.4", page_print=42),
        _chunk(node_id="n2", text="第二段正文", section="3.5", page_print=47),
    ]

    ctx = build_context(chunks)

    assert "[1] 来源：ZRDDS用户手册.pdf · 第 42 页 · 3.4" in ctx
    assert "[2] 来源：ZRDDS用户手册.pdf · 第 47 页 · 3.5" in ctx
    assert "第一段正文" in ctx
    assert "第二段正文" in ctx


def test_build_context_handles_missing_page_and_section():
    ctx = build_context([_chunk(page_print=None, section="")])

    assert "ZRDDS用户手册.pdf" in ctx
    assert "未知来源" not in ctx
    assert "第 " not in ctx  # 无页码不产生"第 页"


def test_build_context_empty_text_keeps_header():
    ctx = build_context([_chunk(text="   ")])

    assert "[1] 来源：" in ctx


# ---------------------------------------------------------------- prompt


def test_v0_messages_contain_two_hard_rules():
    messages = v0.build_messages("如何创建 DataWriter？", "[1] 来源：…")

    assert messages[0]["role"] == "system"
    assert "仅依据" in messages[0]["content"]
    assert "给出来源" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "如何创建 DataWriter？" in messages[1]["content"]
    assert "[1] 来源：" in messages[1]["content"]


# ---------------------------------------------------------------- answer stream


def test_answer_stream_yields_llm_tokens():
    async def fake_chat(messages):
        assert messages[0]["role"] == "system"
        yield "依据"
        yield "检索内容"

    stream = AnswerStream(fake_chat)

    out = asyncio.run(_collect(stream, "问题", [_chunk()]))

    assert out == "依据检索内容"


def test_answer_stream_empty_chunks_yields_abstention():
    async def fake_chat(messages):
        yield "不应调用 LLM"

    stream = AnswerStream(fake_chat)

    out = asyncio.run(_collect(stream, "问题", []))

    assert "无法给出有依据的回答" in out
    assert "不应调用" not in out  # 空检索时不得触发 LLM 调用


def test_answer_stream_rejects_unknown_prompt_version():
    async def noop(messages):
        if False:
            yield ""

    with pytest.raises(ValueError, match="prompt_version"):
        AnswerStream(noop, prompt_version="v9")


# ---------------------------------------------------------------- 组装


def test_build_answer_stream_reads_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    stream = build_answer_stream(_fake_cfg())

    assert isinstance(stream, AnswerStream)


def test_build_answer_stream_requires_llm_env(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="LLM_"):
        build_answer_stream(_fake_cfg())


# ---------------------------------------------------------------- llm config


def test_llm_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    cfg = LLMConfig.from_env("LLM_")

    assert cfg.base_url == "http://x/v1"
    assert cfg.api_key == "sk-test"
    assert cfg.model == "test-model"
    assert cfg.provider == "openai"


def test_llm_config_missing_raises(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        LLMConfig.from_env("LLM_")
