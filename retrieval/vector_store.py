"""Chroma 向量存储封装：建库、写入节点、相似度检索。

embed_fn 依赖注入（文本列表 → 向量列表）：单元测试注入确定性假向量，
生产环境由 retrieval.embeddings.build_embedding 提供 bge-m3。

第一周仅支持 cosine 度量；score 约定「越高越相关」（cosine 相似度）。
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from retrieval.nodes import NodeRecord


def _wait_segment_flush(persist_path: Path, timeout: float) -> bool:
    """轮询等待 chroma compactor 把 HNSW 数据文件写入段目录。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(
            (d / "data_level0.bin").exists()
            for d in persist_path.iterdir()
            if d.is_dir()
        ):
            return True
        time.sleep(0.2)
    return False


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

        self._persist_path = Path(persist_path) if persist_path else None
        if persist_path is None:
            self._client = chromadb.EphemeralClient()
        else:
            self._persist_path.mkdir(parents=True, exist_ok=True)
            # chroma 1.5.9 本机对绝对 persist 路径有 flush 竞态（段数据文件
            # 写不出、首次加载回填即崩，semantic 1059 节点七连崩实测），
            # 相对路径稳定复现不出——见 test_vector_store_passes_relative_path_to_chroma
            chroma_path = os.path.relpath(self._persist_path, Path.cwd())
            self._client = chromadb.PersistentClient(path=str(chroma_path))
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

    def close(self, flush_timeout: float = 60.0) -> None:
        """显式关闭 chroma 客户端，并等待异步段 flush 落盘（幂等）。

        chroma 1.5.9 的段落盘由后台 compactor 异步执行：本机实测进程
        退出时机不当会中断写入，段目录只剩 index_metadata.pickle、
        HNSW 数据文件缺失，索引首次加载回填即崩（semantic 1059 节点
        十连崩）。close() 触发 flush 后轮询段数据文件直至出现，
        超时抛错——宁可失败也不产出「构建成功但不可加载」的索引。
        build 路径（retrieval.index.build_index）在写入后必须调用。
        """
        if self._client is None:
            return
        has_nodes = self._collection.count() > 0
        client, self._client = self._client, None
        client.close()
        if self._persist_path is not None and has_nodes:
            if not _wait_segment_flush(self._persist_path, flush_timeout):
                raise RuntimeError(
                    f"chroma 段 flush 超时（{flush_timeout}s）：索引目录 "
                    f"{self._persist_path} 未出现 HNSW 数据文件，索引不可用。"
                    "请删除该目录后重新构建。"
                )

    def add_nodes(self, nodes: list[NodeRecord],
                  embeddings: list[list[float]] | None = None) -> None:
        """写入节点；空白文本跳过，空元数据置 None（Chroma 不接受空 dict）。

        embeddings 提供时按预计算向量写入、不调用 embed_fn——build_index
        用它在编码完成后才创建 chroma 客户端：客户端在长 torch 编码期间
        存活会毒死 compactor、flush 永不完成（semantic 1059 节点实测）。
        """
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
        if embeddings is not None:
            if len(embeddings) != len(ids):
                raise ValueError(
                    f"预计算向量数({len(embeddings)})与有效节点数({len(ids)})不一致"
                )
            vectors = embeddings
        else:
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
