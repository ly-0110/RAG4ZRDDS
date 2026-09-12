"""MCP Server 打底（指南 §7 任务 2 无条件部分）—— stdio 传输，两个工具。

工具（面向 IDE/Agent 客户端的开发调试问答入口）：
  query_knowledge_base(question, top_k=0)
      → {request_id, answer, sources[SourceRef 7 字段], error?}
      检索与生成复用与 HTTP /query 完全相同的 pipeline 装配（build_pipeline）；
      引用一经检索返回即持久化（X3 同款语义），生成侧失败不丢引用，
      以 error 字段可读透传而非静默降级。
  get_sources(request_id)
      → 引用回查，与 HTTP /sources/{rid} 同源（PersistentSourcesStore）。

身份与日志约定：
  * MCP 侧 request_id 前缀 `mcp-`（12 hex），与 HTTP 的 X-Request-ID 空间区分；
  * 检索日志经 request_log_scope 关联——retrievals.jsonl 中 MCP 调用的
    request_id 为 mcp rid（区别于 HTTP 请求与非 HTTP 直调的 null）；
  * sources 记录与 HTTP 服务共用 {LOG_DIR}/sources.jsonl（两边都写）。

启动（管线/存储为进程级单例，live 模式沿用 build_pipeline 的启动预热）：
  python -m server.mcp_server                 # RAG_MODE 默认 mock，冒烟/联调
  RAG_MODE=live python -m server.mcp_server   # 真实检索+生成（需先 make index）
客户端接入（如 Claude Desktop / IDE MCP 配置）：
  command: python  args: [-m, server.mcp_server]  cwd: 仓库根
  环境变量透传 RAG_MODE / RAG_EXPERIMENT_CONFIG / LLM_*。
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp.server.mcpserver import MCPServer

from retrieval.retriever import to_source_refs
from server.core.pipeline import Pipeline, build_pipeline
from server.core.request_log import PersistentSourcesStore, request_log_scope
from server.core.settings import settings

mcp = MCPServer(
    "zrdds-kb",
    instructions=(
        "ZRDDS 产品知识库问答：query_knowledge_base 提问并取回带页码/章节/URL "
        "引用的回答；get_sources 按 request_id 回查引用明细。"
    ),
)

_state: dict = {"pipeline": None, "store": None}


def init_state(pipeline: Pipeline, store: PersistentSourcesStore) -> None:
    """装配入口（main 用真实装配；测试注入 mock 管线与临时存储）。"""
    _state["pipeline"] = pipeline
    _state["store"] = store


def _ensure_state() -> tuple[Pipeline, PersistentSourcesStore]:
    if _state["pipeline"] is None or _state["store"] is None:
        raise RuntimeError(
            "MCP 服务未初始化：请以 `python -m server.mcp_server` 启动"
            "（或测试中先调用 init_state）"
        )
    return _state["pipeline"], _state["store"]


def _new_rid() -> str:
    return f"mcp-{uuid.uuid4().hex[:12]}"


async def query_knowledge_base_impl(question: str, top_k: Optional[int] = None) -> dict:
    """工具实现层（与 MCP 协议解耦，供单元测试直接驱动）。"""
    pipeline, store = _ensure_state()
    q = (question or "").strip()
    if not q:
        raise ValueError("问题不能是空白内容；请输入要查询的问题后重试。")
    k = top_k if (top_k is not None and top_k > 0) else settings.default_top_k
    rid = _new_rid()

    with request_log_scope(rid):
        chunks = await pipeline.retriever.retrieve(q, k)
        # 富引用投影为 SourceRef 7 字段（与 HTTP /query 同口径，正文不进 wire/存储）
        wire = to_source_refs(chunks)
        # X3 同款：引用先行持久化，之后生成侧失败仍可 get_sources 回查
        store.put(rid, {"question": q, "answer": None, "sources": wire})

        parts: list[str] = []
        try:
            async for token in pipeline.answer_stream.stream(q, chunks):
                parts.append(token)
        except Exception as exc:  # noqa: BLE001 —— 生成失败不丢已取得的引用
            return {
                "request_id": rid,
                "answer": None,
                "sources": wire,
                "error": f"{type(exc).__name__}: {exc}",
            }

    answer = "".join(parts)
    store.put(rid, {"question": q, "answer": answer, "sources": wire})
    return {"request_id": rid, "answer": answer, "sources": wire}


def get_sources_impl(request_id: str) -> dict:
    _, store = _ensure_state()
    rec = store.get((request_id or "").strip())
    if rec is None:
        raise ValueError(
            f"request_id={request_id!r} 无引用记录"
            "（检索失败不落记录 / id 不存在 / 超出内存读取窗口"
            f" {settings.sources_cache_size} 条；全量记录在"
            " {LOG_DIR}/sources.jsonl 可离线回查）"
        )
    return rec


@mcp.tool()
async def query_knowledge_base(question: str, top_k: int = 0) -> dict:
    """在 ZRDDS 知识库（用户手册 + 开发指南）中检索并生成带引用的回答。

    Args:
        question: 开发调试问题（中英文均可，如 "DurabilityQosPolicy 的 kind 字段有哪些取值？"）
        top_k: 引用条数上限（0 表示使用服务端默认值）
    """
    return await query_knowledge_base_impl(question, top_k or None)


@mcp.tool()
def get_sources(request_id: str) -> dict:
    """按 request_id 回查一次问答的完整引用明细（双页码/章节/来源 URL）。

    Args:
        request_id: query_knowledge_base 返回的 request_id
    """
    return get_sources_impl(request_id)


def main() -> int:
    pipeline = build_pipeline(settings.rag_mode, settings.rag_experiment_config)
    store = PersistentSourcesStore(
        REPO_ROOT / settings.log_dir / "sources.jsonl",
        settings.sources_cache_size,
    )
    init_state(pipeline, store)
    # stdio 传输下 stdout 是 JSON-RPC 协议流，任何非协议输出必须走 stderr
    print(
        f"[mcp] mode={settings.rag_mode} "
        f"config={settings.rag_experiment_config} — stdio 传输就绪",
        file=sys.stderr,
        flush=True,
    )
    mcp.run()  # transport 默认 stdio
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
