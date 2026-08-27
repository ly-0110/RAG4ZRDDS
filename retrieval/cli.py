"""B 的检索自测 CLI：build 建索引 / query 提问。

用法：
    python -m retrieval.cli build  --config configs/experiments/struct_v1.yaml
    python -m retrieval.cli query  --config configs/experiments/struct_v1.yaml --question "如何创建 DataWriter？" --top-k 5

A 的分块产物（data/processed/struct_v1.jsonl）就绪前，可用示例节点冒烟：
    python -m retrieval.cli build  --config configs/experiments/struct_v1.yaml
    需先将 tests/fixtures/sample_nodes.jsonl 拷贝到上述产物路径。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from retrieval._bootstrap import experiment_config


def main(argv: list[str] | None = None, *, embed_fn=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，统一按 UTF-8 输出
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="retrieval.cli", description="检索自测工具（成员 B）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="按配置建索引")
    b.add_argument("--config", required=True, help="configs/experiments/*.yaml")
    q = sub.add_parser("query", help="按配置提问")
    q.add_argument("--config", required=True, help="configs/experiments/*.yaml")
    q.add_argument("--question", required=True, help="问题文本")
    q.add_argument("--top-k", type=int, default=5, help="检索条数")
    args = parser.parse_args(argv)

    if args.cmd == "query" and args.top_k < 1:
        parser.error("--top-k 必须 ≥ 1")

    cfg = experiment_config.load(args.config)
    if args.cmd == "build":
        from retrieval.index import build_index

        path = build_index(cfg, embed_fn=embed_fn)
        print(f"[build] 索引已就绪: {path}")
        return 0
    if args.cmd == "query":
        from retrieval.retriever import build_retriever

        retriever = build_retriever(cfg, embed_fn=embed_fn)
        results = asyncio.run(retriever.retrieve(args.question, args.top_k))
        if not results:
            print("[query] 无结果")
        for r in results:
            print(json.dumps(r, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
