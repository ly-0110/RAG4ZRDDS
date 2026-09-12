"""server/mcp_server.py 单元测试（指南 §7 任务 2 · MCP Server 打底）。

只测工具实现层（与 MCP 协议解耦的 *_impl）与工具注册，不起 stdio 子进程；
端到端 stdio 冒烟由 `python -m server.mcp_server`（mock 模式）人工验收。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from server import mcp_server as ms  # noqa: E402
from server.core.pipeline import (  # noqa: E402
    MockAnswerStream,
    MockRetriever,
    Pipeline,
)
from server.core.request_log import (  # noqa: E402
    JsonlLog,
    LoggedRetriever,
    PersistentSourcesStore,
)


@pytest.fixture()
def kb_env(tmp_path):
    """mock 管线 + 临时 sources 存储；每测独立，互不污染全局单例。"""
    store = PersistentSourcesStore(tmp_path / "sources.jsonl", capacity=10)
    ms.init_state(Pipeline(MockRetriever(), MockAnswerStream()), store)
    return tmp_path


def test_tools_registered():
    tools = asyncio.run(ms.mcp.list_tools())
    assert {"query_knowledge_base", "get_sources"} <= {t.name for t in tools}


def test_query_returns_answer_sources_and_persists(kb_env):
    out = asyncio.run(ms.query_knowledge_base_impl("如何创建 DataWriter？", 3))
    assert out["request_id"].startswith("mcp-") and len(out["request_id"]) == 16
    assert out["answer"].strip()
    assert 1 <= len(out["sources"]) <= 3
    src = out["sources"][0]
    # SourceRef 7 字段、无 text 泄漏、双页码真值（mock：print = physical − 6）
    assert "text" not in src
    assert {"node_id", "source_id", "source_name", "section",
            "page_print", "page_physical", "score"} <= set(src)
    assert src["page_physical"] - src["page_print"] == 6
    # 引用先行持久化 + done 后覆盖：回查拿到最终答案
    rec = ms.get_sources_impl(out["request_id"])
    assert rec["answer"] == out["answer"]
    assert rec["sources"] == out["sources"]
    assert rec["question"] == "如何创建 DataWriter？"


def test_query_blank_question_rejected(kb_env):
    with pytest.raises(ValueError, match="空白"):
        asyncio.run(ms.query_knowledge_base_impl("   ", None))


def test_generation_failure_keeps_sources_queryable(kb_env, tmp_path):
    """X3 语义（MCP 侧）：生成侧失败返回 answer=None + error，引用仍可回查。"""

    class BoomStream:
        async def stream(self, question, chunks):
            raise RuntimeError("LLM 不可达")
            yield  # pragma: no cover —— 使其成为 async generator

    ms.init_state(
        Pipeline(MockRetriever(), BoomStream()),
        PersistentSourcesStore(tmp_path / "boom.jsonl", capacity=10),
    )
    out = asyncio.run(ms.query_knowledge_base_impl("任意问题", 2))
    assert out["answer"] is None
    assert "error" in out and "LLM 不可达" in out["error"]
    assert out["sources"]
    rec = ms.get_sources_impl(out["request_id"])
    assert rec["sources"] == out["sources"]


def test_get_sources_unknown_id_readable_error(kb_env):
    with pytest.raises(ValueError, match="无引用记录"):
        ms.get_sources_impl("mcp-000000000000")


def test_retrieval_log_correlates_mcp_request_id(kb_env, tmp_path):
    """retrievals.jsonl 的 request_id = mcp rid（区别于非 HTTP 直调的 null）。"""
    log = JsonlLog(tmp_path / "retrievals.jsonl")
    pipeline = Pipeline(
        LoggedRetriever(
            MockRetriever(), log,
            experiment="t", config_hash8="h", index_dirname="i", mode="mock",
        ),
        MockAnswerStream(),
    )
    ms.init_state(
        pipeline, PersistentSourcesStore(tmp_path / "s3.jsonl", capacity=10),
    )
    out = asyncio.run(ms.query_knowledge_base_impl("预热查询", 1))
    lines = (tmp_path / "retrievals.jsonl").read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    assert rec["request_id"] == out["request_id"]
    assert rec["request_id"].startswith("mcp-")
