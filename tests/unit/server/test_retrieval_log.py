"""检索日志接线单测（docs/retrieval-log-schema.md v0.1，B/D 会签）。

覆盖：记录字段与 B 文档 §3 对齐、request_id 经 ContextVar 关联（HTTP 路径）
与缺省 null（预热/直调语义）、filters 可选字段、检索异常不落日志、
/query 端到端把 rid 写进 retrievals.jsonl。不触碰真实索引/embedding。
"""

from __future__ import annotations

import asyncio
import json

import httpx

from server.core.request_log import JsonlLog, LoggedRetriever, request_log_scope
from server.core.settings import Settings
from server.main import create_app

_RICH_RESULT = {
    "node_id": "struct_v1_s_9_3_3_1_00000",
    "text": "9.3.3.1 创建DataReader 时配置QoS 策略……（正文完整）",
    "source_id": "user_manual",
    "source_name": "ZRDDS用户手册.pdf",
    "section": "第9章 订阅数据 / 9.3 DataReader / 9.3.3.1",
    "page_print": 101,
    "page_physical": 107,
    "score": 0.6234,
}


class _FakeRetriever:
    def __init__(self, results: list[dict] | None = None, raise_exc: Exception | None = None) -> None:
        self._results = results
        self._raise = raise_exc
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        self.calls.append((question, top_k))
        if self._raise is not None:
            raise self._raise
        return list(self._results or [])


def _wrap(log_path, retriever: _FakeRetriever, **kwargs) -> LoggedRetriever:
    base = dict(
        experiment="struct_v1",
        config_hash8="0a7830b7",
        index_dirname="struct_bge-m3_0a7830b7",
        mode="vector",
    )
    base.update(kwargs)
    return LoggedRetriever(retriever, JsonlLog(log_path), **base)


def _read_lines(path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_record_matches_schema_and_results_passthrough(tmp_path):
    log_path = tmp_path / "retrievals.jsonl"
    r = _wrap(log_path, _FakeRetriever([dict(_RICH_RESULT)]))

    out = asyncio.run(r.retrieve("如何创建 DataWriter？", 5))

    lines = _read_lines(log_path)
    assert len(lines) == 1
    rec = lines[0]
    assert rec["ts"]  # JsonlLog 框架自动前置
    assert rec["request_id"] is None  # 无 HTTP 上下文（预热/脚本直调语义，§5.4）
    assert rec["experiment"] == "struct_v1"
    assert rec["config_hash8"] == "0a7830b7"
    assert rec["index_dirname"] == "struct_bge-m3_0a7830b7"
    assert rec["mode"] == "vector"
    assert rec["top_k"] == 5
    assert rec["question"] == "如何创建 DataWriter？"
    assert isinstance(rec["latency_ms"], (int, float)) and rec["latency_ms"] >= 0
    assert rec["result_count"] == 1
    assert rec["results"] == [dict(_RICH_RESULT)]  # 富引用原样落盘（text 仅进本地日志）
    assert out == [dict(_RICH_RESULT)]  # 返回值透传，检索行为不受包装影响
    assert "filters" not in rec  # filters 为空时不写字段


def test_request_id_bound_inside_scope(tmp_path):
    log_path = tmp_path / "retrievals.jsonl"
    r = _wrap(log_path, _FakeRetriever([]), mode="bm25")

    async def go():
        with request_log_scope("req_abc123"):
            await r.retrieve("不存在的错误码 E9999", 3)

    asyncio.run(go())
    rec = _read_lines(log_path)[0]
    assert rec["request_id"] == "req_abc123"
    assert rec["result_count"] == 0  # bm25 空结果=无词面证据信号，照常落盘（§5.3）


def test_scope_reset_restores_null(tmp_path):
    log_path = tmp_path / "retrievals.jsonl"
    r = _wrap(log_path, _FakeRetriever([]))

    async def go():
        with request_log_scope("req_1"):
            await r.retrieve("q1", 3)
        await r.retrieve("q2", 3)  # scope 外（如预热）

    asyncio.run(go())
    recs = _read_lines(log_path)
    assert recs[0]["request_id"] == "req_1"
    assert recs[1]["request_id"] is None


def test_filters_recorded_when_nonempty(tmp_path):
    log_path = tmp_path / "retrievals.jsonl"
    r = _wrap(log_path, _FakeRetriever([]), filters={"version": "2.0"})

    asyncio.run(r.retrieve("q", 3))

    assert _read_lines(log_path)[0]["filters"] == {"version": "2.0"}


def test_retriever_failure_writes_no_log_and_propagates(tmp_path):
    log_path = tmp_path / "retrievals.jsonl"
    r = _wrap(log_path, _FakeRetriever(raise_exc=RuntimeError("索引损坏")))

    raised = False
    try:
        asyncio.run(r.retrieve("q", 3))
    except RuntimeError:
        raised = True

    assert raised  # 异常原样传播，不吞
    assert not log_path.exists()  # 异常不落检索日志（会签修改点①：故障归请求级日志）


def test_http_request_id_flows_into_retrieval_log(tmp_path):
    """端到端：/query 的 request_id 经 request_log_scope 注入 pipeline 层包装器。"""
    log_path = tmp_path / "retrievals.jsonl"
    app = create_app(Settings())
    app.state.pipeline.retriever = _wrap(log_path, _FakeRetriever([dict(_RICH_RESULT)]))

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            return await c.post("/query", json={"question": "如何创建 DataWriter？", "top_k": 2})

    r = asyncio.run(go())
    assert r.status_code == 200
    assert r.headers["x-request-id"]

    lines = _read_lines(log_path)
    assert len(lines) == 1
    rec = lines[0]
    assert rec["request_id"] == r.headers["x-request-id"]
    assert rec["top_k"] == 2
    assert rec["result_count"] == 1
