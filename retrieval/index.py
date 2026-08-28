"""建索引入口：节点 jsonl → Chroma 索引目录。

供 D 的 scripts/build_index.py 与 B 的 CLI 共用；产物路径由
configs/experiments 派生命名决定（scripts/experiment_config.py）。
同一配置重复构建 = 覆盖重建（保证幂等）。
"""
from __future__ import annotations

from pathlib import Path

from retrieval._bootstrap import experiment_config
from retrieval.nodes import load_nodes
from retrieval.vector_store import VectorStore, sanitize_collection_name


def build_index(cfg, embed_fn=None) -> Path:
    if cfg.index.backend != "chroma":
        raise NotImplementedError(
            f"第一周仅支持 chroma 向量库，收到 backend={cfg.index.backend!r}"
            "（faiss 等后端待后续接入）"
        )
    nodes_file = experiment_config.nodes_path(cfg)
    if not nodes_file.exists():
        raise FileNotFoundError(
            f"节点文件不存在: {nodes_file}（请先运行 ingest 生成分块产物）"
        )
    nodes = load_nodes(nodes_file)
    if embed_fn is None:
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(cfg)
    store = VectorStore(
        embed_fn=embed_fn,
        persist_path=str(experiment_config.index_dir(cfg)),
        metric=cfg.index.metric,
        collection_name=sanitize_collection_name(experiment_config.index_dirname(cfg)),
        reset=True,
    )
    store.add_nodes(nodes)
    return experiment_config.index_dir(cfg)
