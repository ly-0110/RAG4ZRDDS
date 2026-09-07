"""Prompt v2（多来源 + 冲突披露 + 来源优先级）与 context_builder 来源标签的单元测试。"""
from __future__ import annotations

import asyncio

from generation.context_builder import build_context
from generation.prompts import v2
from generation.query_engine import AnswerStream
from generation.source_labels import DEFAULT_PRIORITY, SOURCE_CATEGORY


def _chunk(source_id="user_manual", source_name="ZRDDS用户手册.pdf", **kw) -> dict:
    base = {
        "node_id": "n1",
        "text": "正文",
        "source_id": source_id,
        "source_name": source_name,
        "section": "3.4",
        "page_print": 36,
        "score": 0.9,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- prompt v2


def test_v2_has_conflict_disclosure_rule():
    content = v2.build_messages("问题", "context")[0]["content"]
    assert "五条规则" in content
    assert "冲突" in content      # 规则 5：冲突披露
    assert "掩盖" in content


def test_v2_priority_note_injected_when_configured():
    content = v2.build_messages("问题", "context", ["zrdds_dev_guide", "user_manual"])[0]["content"]
    assert "来源优先级" in content
    assert "开发者指南" in content
    assert "用户手册" in content


def test_v2_priority_note_absent_when_empty():
    for sp in (None, []):
        content = v2.build_messages("问题", "context", sp)[0]["content"]
        assert "来源优先级" not in content


def test_default_priority_consistent_with_categories():
    assert all(p in SOURCE_CATEGORY for p in DEFAULT_PRIORITY)


# ---------------------------------------------------------------- context_builder


def test_context_builder_injects_category_tag():
    ctx = build_context([_chunk(source_id="user_manual")])
    assert "ZRDDS用户手册.pdf（用户手册）" in ctx


def test_context_builder_no_tag_when_unknown_source():
    ctx = build_context([_chunk(source_id=None, source_type=None, source_name="X.pdf")])
    assert "（" not in ctx  # 无类别/类型 → 不追加标签


# ---------------------------------------------------------------- answer stream


def test_answer_stream_v2_uses_priority():
    captured: dict = {}

    async def fake_chat(messages):
        captured["system"] = messages[0]["content"]
        yield "x"

    stream = AnswerStream(
        fake_chat, prompt_version="v2", source_priority=["zrdds_dev_guide", "user_manual"]
    )

    async def run():
        out = []
        async for t in stream.stream("问题", [_chunk()]):
            out.append(t)
        return "".join(out)

    asyncio.run(run())
    assert "来源优先级" in captured["system"]
