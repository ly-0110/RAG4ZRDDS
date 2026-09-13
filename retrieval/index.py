"""建索引入口：节点 jsonl → 索引目录（按 retrieval.mode 分派）。

vector → Chroma 向量索引；bm25 → bm25.json 词袋索引（不碰 embedding 模型）。
供 D 的 scripts/build_index.py 与 B 的 CLI 共用；产物路径由
configs/experiments 派生命名决定（scripts/experiment_config.py）。
同一配置重复构建 = 覆盖重建（保证幂等）。
"""
from __future__ import annotations

from pathlib import Path

from retrieval._bootstrap import experiment_config
from retrieval.bm25 import BM25Store
from retrieval.nodes import load_nodes
from retrieval.vector_store import VectorStore, sanitize_collection_name


def build_index(cfg, embed_fn=None) -> Path:
    if cfg.retrieval.mode == "hybrid":
        # 引用制无自有索引（PR#27 设计 §2.2）：子索引由各自配置管；
        # scripts/build_index.py 已提前短路，此处拦程序化误用
        raise ValueError(
            "hybrid 为引用制、无自有索引：请分别构建 components 引用的子配置"
            "（make index CFG=configs/experiments/<子实验>.yaml）"
        )
    nodes_file = experiment_config.nodes_path(cfg)
    if not nodes_file.exists():
        raise FileNotFoundError(
            f"节点文件不存在: {nodes_file}（请先运行 ingest 生成分块产物）"
        )
    if cfg.retrieval.mode == "bm25":
        params = cfg.retrieval.params or {}
        store = BM25Store(
            k1=params.get("k1", 1.5),
            b=params.get("b", 0.75),
        )
        store.add_nodes(load_nodes(nodes_file))
        store.save(experiment_config.index_dir(cfg))
        return experiment_config.index_dir(cfg)
    if cfg.index.backend != "chroma":
        raise NotImplementedError(
            f"第一周仅支持 chroma 向量库，收到 backend={cfg.index.backend!r}"
            "（faiss 等后端待后续接入）"
        )
    nodes = load_nodes(nodes_file)
    if embed_fn is None:
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(cfg)
    # 先编码后建客户端（防御性排序）：chroma 1.5.9 段 flush 为后台异步，
    # 落盘完整性由 close() 的轮询兜底；编码先行可避免客户端在长编码
    # （十几分钟）期间长期空闲（semantic 1059 节点事故的残余教训）。
    docs = [n.text for n in nodes if n.text and n.text.strip()]
    vectors = embed_fn(docs)
    store = VectorStore(
        embed_fn=embed_fn,
        persist_path=str(experiment_config.index_dir(cfg)),
        metric=cfg.index.metric,
        collection_name=sanitize_collection_name(experiment_config.index_dirname(cfg)),
        reset=True,
    )
    store.add_nodes(nodes, embeddings=vectors)
    # 等待 chroma 异步段 flush 落盘（见 VectorStore.close 的说明）
    store.close()
    return experiment_config.index_dir(cfg)
