"""Top-K 检索器：实现 server/core/pipeline.py 的 Retriever 协议。

retrieve 返回富引用（含 text 正文，供生成侧组装 context）：
node_id / text / source_id / source_name / section / page_print / page_physical / score。

下发/落盘前用 to_source_refs 投影为 SourceRef 7 字段（不含 text，与
server/core/schema.py 的 SourceRef 一致），避免把整段正文塞进 sources 事件与报告。
"""
from __future__ import annotations

from retrieval._bootstrap import experiment_config
from retrieval.bm25 import BM25Store
from retrieval.nodes import NodeRecord
from retrieval.rrf import DEFAULT_RRF_K, fuse_hits
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


class VectorRetriever:
    def __init__(self, store: VectorStore, filters: dict | None = None) -> None:
        self._store = store
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 第一周为同步实现（CPU 推理），直接放在 async 方法内；
        # D 服务端接线时若发现阻塞事件循环，用 anyio.to_thread 包裹。
        results = self._store.query(question, top_k, filters=self._filters)
        return [_to_source_ref(r) for r in results]


class BM25Retriever:
    def __init__(self, store: BM25Store, filters: dict | None = None) -> None:
        self._store = store
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        results = self._store.query(question, top_k, filters=self._filters)
        return [_to_source_ref(r) for r in results]


class HybridRetriever:
    """vector + bm25 两路候选 → RRF 融合（引用制：无自有索引，PR#27 设计 §2）。"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        rrf_k: float = DEFAULT_RRF_K,
        candidate_top_k: int = 30,
        filters: dict | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._rrf_k = rrf_k
        self._candidate_top_k = candidate_top_k
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 子检索各取候选池；top_k 大于池容量时以 top_k 兜底（防融合池不足）
        sub_k = max(top_k, self._candidate_top_k)
        vec_hits = self._vector_store.query(question, sub_k, filters=self._filters)
        bm_hits = self._bm25_store.query(question, sub_k, filters=self._filters)
        fused = fuse_hits([vec_hits, bm_hits], top_k=top_k, k=self._rrf_k)
        return [_to_source_ref(r) for r in fused]


def build_retriever(cfg, embed_fn=None):
    """按实验配置组装：索引目录/集合名由 configs 派生命名（D 的约定）。"""
    index_path = experiment_config.index_dir(cfg)
    if cfg.retrieval.mode == "bm25":
        if not index_path.exists():
            raise FileNotFoundError(
                f"索引不存在: {index_path}（请先运行 build_index 建索引，再启动 live 检索）"
            )
        store = BM25Store.load(index_path)
        return BM25Retriever(store, filters=cfg.retrieval.filters or None)
    if cfg.retrieval.mode == "hybrid":
        comps = cfg.retrieval.components or {}
        missing_roles = [role for role in ("vector", "bm25") if role not in comps]
        if missing_roles:
            raise ValueError(
                f"hybrid components 缺少角色: {missing_roles}"
                "（需要 vector 与 bm25 两类引用，见 configs/experiments/README.md）"
            )
        vec_cfg = experiment_config.load(
            experiment_config.experiment_yaml_path(comps["vector"]))
        bm25_cfg = experiment_config.load(
            experiment_config.experiment_yaml_path(comps["bm25"]))
        vec_nodes = experiment_config.nodes_path(vec_cfg)
        bm25_nodes = experiment_config.nodes_path(bm25_cfg)
        if vec_nodes != bm25_nodes:
            raise ValueError(
                f"hybrid 两路节点集不一致：vector={comps['vector']} → {vec_nodes.name}，"
                f"bm25={comps['bm25']} → {bm25_nodes.name}；"
                "RRF 按 node_id 融合要求 components 产出同一节点集（chunking+sources 相同）"
            )
        vec_path = experiment_config.index_dir(vec_cfg)
        bm25_path = experiment_config.index_dir(bm25_cfg)
        for role, path in (("vector", vec_path), ("bm25", bm25_path)):
            if not path.exists():
                raise FileNotFoundError(
                    f"子索引不存在: {path}（role={role}，请先运行 "
                    f"make index CFG=configs/experiments/{comps[role]}.yaml）"
                )
        if embed_fn is None:
            from retrieval.embeddings import build_embedding

            embed_fn = build_embedding(vec_cfg)
        vector_store = VectorStore(
            embed_fn=embed_fn,
            persist_path=str(vec_path),
            metric=vec_cfg.index.metric,
            collection_name=sanitize_collection_name(
                experiment_config.index_dirname(vec_cfg)),
        )
        bm25_store = BM25Store.load(bm25_path)
        rrf_k = float((cfg.retrieval.params or {}).get("rrf_k", DEFAULT_RRF_K))
        return HybridRetriever(
            vector_store,
            bm25_store,
            rrf_k=rrf_k,
            candidate_top_k=cfg.retrieval.candidate_top_k,
            filters=cfg.retrieval.filters or None,
        )
    if cfg.retrieval.mode != "vector":
        raise NotImplementedError(
            f"当前支持 vector/bm25/hybrid 检索，收到 mode={cfg.retrieval.mode!r}"
            "（hybrid_rerank 待第四周实现）"
        )
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
