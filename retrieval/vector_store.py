"""Chroma 向量存储封装：建库、写入节点、相似度检索。

embed_fn 依赖注入（文本列表 → 向量列表）：单元测试注入确定性假向量，
生产环境由 retrieval.embeddings.build_embedding 提供 bge-m3。

第一周仅支持 cosine 度量；score 约定「越高越相关」（cosine 相似度）。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from retrieval.nodes import NodeRecord


def _sanitize_metadata(metadata: dict) -> dict:
    """Chroma 元数据只接受 str/int/float/bool；剥离其余类型。"""
    return {
        k: v
        for k, v in metadata.items()
        if v is not None and isinstance(v, (str, int, float, bool))
    }


def _to_chroma_where(filters: dict) -> dict:
    """第一周仅支持等值过滤：{version: "2.4"} → {"version": "2.4"}。"""
    return dict(filters)


def sanitize_collection_name(name: str) -> str:
    """Chroma 集合名只允许 [a-zA-Z0-9._-]；其余字符（如模型名中的 /）替换为 _。"""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


class VectorStore:
    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        persist_path: str | Path | None = None,
        metric: str = "cosine",
        collection_name: str = "nodes",
        reset: bool = False,
    ) -> None:
        if metric != "cosine":
            raise ValueError(f"第一周仅支持 cosine 度量，收到 {metric!r}")
        import chromadb

        if persist_path is None:
            self._client = chromadb.EphemeralClient()
        else:
            Path(persist_path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(persist_path))
        if reset:
            # 幂等重建：先删后建。注意——删除后其他仍持有旧句柄的 VectorStore
            # 会失效，因此约定「重建期间不可服务，重建后需重建 retriever 实例」。
            try:
                self._client.delete_collection(name=collection_name)
            except chromadb.errors.NotFoundError:
                pass
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": metric}
        )
        self._embed_fn = embed_fn

    def add_nodes(self, nodes: list[NodeRecord]) -> None:
        """写入节点；空白文本跳过，空元数据置 None（Chroma 不接受空 dict）。"""
        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict | None] = []
        for n in nodes:
            if not n.text or not n.text.strip():
                continue
            ids.append(n.node_id)
            docs.append(n.text)
            metas.append(_sanitize_metadata(n.metadata) or None)
        if not ids:
            if self._collection.count() == 0:
                import warnings

                warnings.warn("所有节点均为空白文本，索引将为空——请检查上游分块产物")
            return
        vectors = self._embed_fn(docs)
        self._collection.add(ids=ids, documents=docs, embeddings=vectors, metadatas=metas)

    def query(
        self, question: str, top_k: int, filters: dict | None = None
    ) -> list[dict]:
        """返回 [{"node_id","text","metadata","score"}]，按 score 降序。"""
        if self._collection.count() == 0:
            return []
        query_vector = self._embed_fn([question])[0]
        where = _to_chroma_where(filters) if filters else None
        res = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["distances", "metadatas", "documents"],
        )
        out: list[dict] = []
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        for i in range(len(ids)):
            out.append(
                {
                    "node_id": ids[i],
                    "text": docs[i],
                    "metadata": metas[i] or {},
                    "score": round(1.0 - dists[i], 4),
                }
            )
        return out
