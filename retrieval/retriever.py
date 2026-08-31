"""Top-K 检索器：实现 server/core/pipeline.py 的 Retriever 协议。

retrieve 返回富引用（含 text 正文，供生成侧组装 context）：
node_id / text / source_id / source_name / section / page_print / page_physical / score。

下发/落盘前用 to_source_refs 投影为 SourceRef 7 字段（不含 text，与
server/core/schema.py 的 SourceRef 一致），避免把整段正文塞进 sources 事件与报告。
"""
from __future__ import annotations

from retrieval._bootstrap import experiment_config
from retrieval.nodes import NodeRecord
from retrieval.vector_store import VectorStore, sanitize_collection_name

SOURCE_REF_FIELDS = (
    "node_id",
    "source_id",
    "source_name",
    "section",
    "page_print",
    "page_physical",
    "score",
)


def to_source_refs(chunks: list[dict]) -> list[dict]:
    """把富引用（含 text）投影为 SourceRef 7 字段（下发/落盘用，不含正文）。"""
    return [{k: c[k] for k in SOURCE_REF_FIELDS if k in c} for c in chunks]


class VectorRetriever:
    def __init__(self, store: VectorStore, filters: dict | None = None) -> None:
        self._store = store
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 第一周为同步实现（CPU 推理），直接放在 async 方法内；
        # D 服务端接线时若发现阻塞事件循环，用 anyio.to_thread 包裹。
        results = self._store.query(question, top_k, filters=self._filters)
        return [self._to_source_ref(r) for r in results]

    @staticmethod
    def _to_source_ref(r: dict) -> dict:
        rec = NodeRecord(r["node_id"], r["text"], r["metadata"])
        return {
            "node_id": r["node_id"],
            "text": r["text"],
            "source_id": rec.source_id,
            "source_name": rec.source_name,
            "section": rec.section,
            "page_print": rec.page_print,
            "page_physical": rec.page_physical,
            "score": float(r["score"]),
        }


def build_retriever(cfg, embed_fn=None) -> VectorRetriever:
    """按实验配置组装：索引目录/集合名由 configs 派生命名（D 的约定）。"""
    if cfg.retrieval.mode != "vector":
        raise NotImplementedError(
            f"第一周仅支持 vector 检索，收到 mode={cfg.retrieval.mode!r}"
            "（bm25/hybrid/hybrid_rerank 待后续周次实现）"
        )
    index_path = experiment_config.index_dir(cfg)
    if not index_path.exists():
        raise FileNotFoundError(
            f"索引不存在: {index_path}（请先运行 build_index 建索引，再启动 live 检索）"
        )
    if embed_fn is None:
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(cfg)
    store = VectorStore(
        embed_fn=embed_fn,
        persist_path=str(index_path),
        metric=cfg.index.metric,
        collection_name=sanitize_collection_name(experiment_config.index_dirname(cfg)),
    )
    return VectorRetriever(store, filters=cfg.retrieval.filters or None)
