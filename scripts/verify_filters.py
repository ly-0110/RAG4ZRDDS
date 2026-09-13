#!/usr/bin/env python3
"""scripts/verify_filters.py — 多来源索引 metadata 过滤全量校验（B 域，PR#27 设计 §3.2-2）

对指定实验配置，用内置过滤集 × 探针问题执行检索，校验每条结果的 node_id
属于「按 nodes jsonl 元数据真值过滤后的允许集」——对照真值而非依赖 store
自查。全空命中会单独提示（最常见的失败信号：过滤口径/元数据不对齐）。

用法:
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_bm25.yaml    # 无需模型
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_v1.yaml      # 需 bge-m3
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_hybrid.yaml  # 需 bge-m3

退出码：0=全部通过；1=存在违规。
依赖: retrieval/*（B）· 目标索引已构建
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from retrieval._bootstrap import experiment_config as ec  # noqa: E402
from retrieval.nodes import load_nodes  # noqa: E402
from retrieval.retriever import BM25Retriever, HybridRetriever, VectorRetriever  # noqa: E402

PROBES = [
    "产品如何安装？",
    "create_datawriter() 的参数是什么？",
    "用户手册里的设备连接功能在 Java SDK 中如何实现？",
    "v2.4 的 API 是否仍使用旧参数？",
    "如何配置 QoS 策略？",
]
FILTER_SETS = [
    {"source_type": "pdf"},
    {"source_type": "html"},
    {"version": "2.4"},
    {"source_type": "html", "version": "2.4"},
]


def _nodes_of(cfg):
    """检索器消费的节点集（hybrid 取 vector 组件——两路同节点集已由构建期校验）。"""
    if cfg.retrieval.mode == "hybrid":
        ref = ec.load(ec.experiment_yaml_path(cfg.retrieval.components["vector"]))
    else:
        ref = cfg
    return load_nodes(ec.nodes_path(ref))


def _reroll(retriever, filt: dict):
    """同一批已加载 store 换 filters 重新组包。

    filters 在查询期生效（chroma where / bm25 post-filter），但参与索引身份
    派生（experiment_config._INDEX_IDENTITY_RETRIEVAL_KEYS）——直接改
    cfg.retrieval.filters 会派生出不存在的索引目录，故探测在检索器层换装。
    """
    if isinstance(retriever, HybridRetriever):
        return HybridRetriever(
            retriever._vector_store, retriever._bm25_store,
            rrf_k=retriever._rrf_k, candidate_top_k=retriever._candidate_top_k,
            filters=filt)
    if isinstance(retriever, BM25Retriever):
        return BM25Retriever(retriever._store, filters=filt)
    return VectorRetriever(retriever._store, filters=filt)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="verify_filters", description=__doc__)
    ap.add_argument("--config", required=True, help="实验配置 yaml")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args(argv)

    from retrieval.retriever import build_retriever

    cfg = ec.load(args.config)
    nodes = _nodes_of(cfg)
    embed_fn = None
    if cfg.retrieval.mode == "vector":
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(cfg)
    elif cfg.retrieval.mode == "hybrid":
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(ec.load(
            ec.experiment_yaml_path(cfg.retrieval.components["vector"])))

    print(f"[verify] {args.config} mode={cfg.retrieval.mode} 节点数={len(nodes)}")
    base = build_retriever(cfg, embed_fn=embed_fn)  # 索引按配置原样定位，加载一次
    violations = 0
    for filt in FILTER_SETS:
        allowed = {n.node_id for n in nodes
                   if all(n.metadata.get(k) == v for k, v in filt.items())}
        retriever = _reroll(base, filt)
        print(f"[verify] filters={filt} 真值允许 {len(allowed)} 节点")
        hits_total = 0
        for q in PROBES:
            refs = asyncio.run(retriever.retrieve(q, top_k=args.top_k))
            hits_total += len(refs)
            bad = [r["node_id"] for r in refs if r["node_id"] not in allowed]
            violations += len(bad)
            tag = "OK" if not bad else "违规"
            note = f"  越界: {bad[:3]}" if bad else ""
            print(f"  [{tag}] {q}  命中 {len(refs)} 条{note}")
        if hits_total == 0:
            print("  [警告] 该过滤集全部探针零命中——口径或元数据可能不对齐")
    if violations:
        print(f"[verify] 失败：{violations} 条结果越界")
        return 1
    print("[verify] 通过：全部结果满足过滤约束")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
