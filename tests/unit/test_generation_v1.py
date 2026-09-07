"""Prompt v1 与 query_engine v1 接线的单元测试（不联网）。"""
from __future__ import annotations

import asyncio

from generation.prompts import v1
from generation.query_engine import AnswerStream


def _chunk() -> dict:
    return {
        "node_id": "n1",
        "text": "正文",
        "source_id": "user_manual",
        "source_name": "ZRDDS用户手册.pdf",
        "section": "3.4",
        "page_print": 36,
        "page_physical": 42,
        "score": 0.9,
    }


def test_v1_system_prompt_has_four_rules():
    messages = v1.build_messages("如何创建 DataWriter？", "[1] 来源：…")
    content = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "仅依据" in content  # 规则 1
    assert "给出来源" in content  # 规则 2
    assert "当前知识库无法确认" in content  # 规则 3 拒答
    assert "版本差异" in content  # 规则 4 版本披露
    assert messages[1]["role"] == "user"
    assert "如何创建 DataWriter？" in messages[1]["content"]


def test_answer_stream_v1_uses_v1_system_prompt():
    captured: dict = {}

    async def fake_chat(messages):
        captured["system"] = messages[0]["content"]
        yield "x"

    stream = AnswerStream(fake_chat, prompt_version="v1")

    async def run():
        out = []
        async for t in stream.stream("问题", [_chunk()]):
            out.append(t)
        return "".join(out)

    asyncio.run(run())
    assert "当前知识库无法确认" in captured["system"]
