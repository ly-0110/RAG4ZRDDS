"""回答级日志（LoggedAnswerStream）回归测试（docs/answer-log-schema.md）。

三级日志的第三级：每次生成一条，终态 done / error / cancelled 都落盘。
字段口径与会签稿一致；这里只测包装器本身（不触真实 LLM / 索引）。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from server.core.request_log import JsonlLog, LoggedAnswerStream, request_log_scope

REPO_ROOT = Path(__file__).resolve().parents[2]


class _StubStream:
    """可控的假生成器：tokens 逐条产出；raise_at 指定在第 N 条后抛错。"""

    def __init__(self, tokens, raise_at=None):
        self._tokens = tokens
        self._raise_at = raise_at

    async def stream(self, question, chunks):
        for i, t in enumerate(self._tokens):
            if self._raise_at is not None and i == self._raise_at:
                raise RuntimeError("上游 LLM 不可达")
            yield t


def _chunks():
    return [
        {"node_id": "n1", "source_id": "user_manual", "text": "…"},
        {"node_id": "n2", "source_id": "zrdds_dev_guide", "text": "…"},
        {"node_id": "n3", "source_id": "user_manual", "text": "…"},
    ]


def _wrap(tmp_path, inner):
    log = JsonlLog(tmp_path / "answers.jsonl")
    return LoggedAnswerStream(
        inner, log, experiment="struct_v1", config_hash8="0a7830b7",
        prompt_version="v2", model="qwen3.5-9b",
    ), tmp_path / "answers.jsonl"


def _read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_success_path_writes_one_record(tmp_path):
    stream, path = _wrap(tmp_path, _StubStream(["答案", "片段", "。"]))

    async def run():
        with request_log_scope("req_abc"):
            return [t async for t in stream.stream("问题", _chunks())]

    tokens = asyncio.run(run())

    assert tokens == ["答案", "片段", "。"]          # 透传不改变内容
    rows = _read(path)
    assert len(rows) == 1                            # 一次生成一条
    r = rows[0]
    assert r["request_id"] == "req_abc"              # ContextVar 注入
    assert r["experiment"] == "struct_v1" and r["config_hash8"] == "0a7830b7"
    assert r["prompt_version"] == "v2" and r["model"] == "qwen3.5-9b"
    assert r["answer"] == "答案片段。"
    assert r["finish_reason"] == "stop" and r["error"] is None
    assert r["citation_count"] == 3
    assert r["source_ids"] == ["user_manual", "zrdds_dev_guide"]   # 去重且排序
    assert r["token_chunks"] == 3
    assert r["first_token_ms"] is not None and r["duration_ms"] >= r["first_token_ms"]
    assert r["abstained"] is False
    assert r["ts"]


def test_abstention_answer_is_flagged(tmp_path):
    """拒答判定复用 generation.abstention 单一事实源。"""
    from generation.abstention import ABSTENTION_MARKERS

    marker = next(iter(ABSTENTION_MARKERS))
    stream, path = _wrap(tmp_path, _StubStream([f"当前知识库{marker}相关内容"]))

    async def run():
        return [t async for t in stream.stream("不存在的问题", _chunks())]

    asyncio.run(run())
    assert _read(path)[0]["abstained"] is True


def test_upstream_error_is_recorded_and_reraised(tmp_path):
    stream, path = _wrap(tmp_path, _StubStream(["开头", "后续"], raise_at=1))

    async def run():
        return [t async for t in stream.stream("问题", _chunks())]

    with pytest.raises(RuntimeError, match="上游 LLM 不可达"):
        asyncio.run(run())

    r = _read(path)[0]
    assert r["finish_reason"] == "error"
    assert "上游 LLM 不可达" in r["error"]
    assert r["answer"] == "开头"                     # 部分答案仍留档（与 sources.jsonl 对齐）


def test_cancellation_records_partial_answer(tmp_path):
    """客户端中止：生成器被关闭（GeneratorExit）时也要落一条 cancelled。"""
    stream, path = _wrap(tmp_path, _StubStream(["部分", "答案", "后续"]))

    async def run():
        collected = []
        agen = stream.stream("问题", _chunks())
        async for t in agen:
            collected.append(t)
            break                                    # 模拟前端"停止生成"
        await agen.aclose()
        return collected

    asyncio.run(run())

    r = _read(path)[0]
    assert r["finish_reason"] == "cancelled"
    assert r["answer"] == "部分"


def test_log_write_failure_does_not_break_streaming(tmp_path, monkeypatch):
    """日志写盘失败不得影响回答投递（与 sources store 同原则）。"""
    stream, _ = _wrap(tmp_path, _StubStream(["ok"]))

    def boom(_record):
        raise OSError("disk full")

    monkeypatch.setattr(stream._log, "append", boom)

    async def run():
        return [t async for t in stream.stream("问题", _chunks())]

    assert asyncio.run(run()) == ["ok"]
