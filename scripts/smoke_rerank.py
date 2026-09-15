#!/usr/bin/env python3
"""scripts/smoke_rerank.py — 精排通路真模型冒烟（成员 B · 第四周 §8.2）

真实 bge-m3 向量 + bge-reranker-v2-m3 精排，跑少量探针题打印 top-5。
用于人工核验精排行为、score 量纲与来源漂移；产物记入 docs/evaluation.md。
不进 CI（模型加载占内存、耗时长）。

用法:
  .venv/Scripts/python scripts/smoke_rerank.py
  .venv/Scripts/python scripts/smoke_rerank.py --config configs/experiments/struct_multisrc_hybrid_ver24.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from retrieval._bootstrap import experiment_config as ec  # noqa: E402

PROBES = [
    "create_datawriter() 需要哪些参数？",
    "如何创建一个属于特定域的 DomainParticipant？",
    "v2.4 的 API 是否仍使用旧参数？",
]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="smoke_rerank", description=__doc__)
    parser.add_argument("--config",
                        default="configs/experiments/struct_multisrc_hybrid_rerank.yaml")
    args = parser.parse_args(argv)

    cfg = ec.load(args.config)
    from retrieval.retriever import build_retriever

    print(f"[smoke] 实验={cfg.experiment.name} mode={cfg.retrieval.mode}"
          "（首次加载真模型，请稍候）")
    retriever = build_retriever(cfg)
    for q in PROBES:
        print(f"\n[smoke] Q: {q}")
        hits = asyncio.run(retriever.retrieve(q, cfg.retrieval.top_k))
        for i, h in enumerate(hits, 1):
            print(f"  {i}. {h['node_id']}  score={h['score']:.6f}  "
                  f"source={h.get('source_id')}  section={h.get('section')}")
    print("\n[smoke] 核验点：score 量纲/范围、来源分布、API 类问题是否被拉向 dev guide")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
