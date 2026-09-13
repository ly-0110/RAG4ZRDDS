#!/usr/bin/env python3
"""scripts/smoke_cross_source.py — §7.5 A/B/C/D 四场景跨来源冒烟（B 域，PR#27 设计 §4.3）

对指定实验配置跑指南 §7.5 的 4 个样例问题，打印 top-k 的来源/版本/章节分布，
供人工对照「理想结果」表。结果只作开发参考、不进正式报告（正式评测等 E 题集
重新标注 + C 判对口径会签）。

用法:
  python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_bm25.yaml
  python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_hybrid.yaml
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

SCENARIOS = [
    ("A 单一来源即可回答", "产品如何安装？", "理想：user_manual（手册）"),
    ("B HTML 更适合回答", "create_datawriter() 的参数是什么？", "理想：zrdds_dev_guide（开发指南）"),
    ("C 多来源联合", "用户手册里的设备连接功能在 Java SDK 中如何实现？", "理想：两来源同时出现"),
    ("D 冲突/版本问题", "v2.4 的 API 是否仍使用旧参数？", "理想：能区分版本/来源"),
]


def _nodes_of(cfg):
    if cfg.retrieval.mode == "hybrid":
        ref = ec.load(ec.experiment_yaml_path(cfg.retrieval.components["vector"]))
    else:
        ref = cfg
    return load_nodes(ec.nodes_path(ref))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="smoke_cross_source", description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args(argv)

    from retrieval.retriever import build_retriever

    cfg = ec.load(args.config)
    meta = {n.node_id: n.metadata for n in _nodes_of(cfg)}
    retriever = build_retriever(cfg)
    print(f"[smoke] {args.config} mode={cfg.retrieval.mode}（结果仅开发参考，不进正式报告）")
    for title, question, ideal in SCENARIOS:
        refs = asyncio.run(retriever.retrieve(question, top_k=args.top_k))
        print(f"\n== {title} | {question}")
        print(f"   {ideal}")
        for i, r in enumerate(refs, 1):
            m = meta.get(r["node_id"], {})
            print(f"   {i}. [{m.get('source_type', '?')}/{m.get('version', '?')}] "
                  f"{r['source_id']} · {r['section'][:36]} · score={r['score']}")
    print("\n[smoke] 对照 §7.5 理想结果人工判读：来源分布是否符合预期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
