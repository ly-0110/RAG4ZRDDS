#!/usr/bin/env python3
"""
scripts/inspect_nodes.py — Node 集抽查视图（周五验收与日常调试用）

职责（成员 D）:
  * 质检口径：无空 Node、无重复 ID/文本、长度分布正常、双页码齐全
  * 抽样浏览：随机/区间/grep 三种定位方式，打印章节、页码、长度与正文开头
  * 只读工具：不修改任何产物

用法:
  python scripts/inspect_nodes.py                       # 默认 struct_v1 基线
  python scripts/inspect_nodes.py --config configs/experiments/<实验>.yaml
  python scripts/inspect_nodes.py --sample 5 --seed 42  # 随机抽查
  python scripts/inspect_nodes.py --grep DataWriter     # 全文检索定位
  python scripts/inspect_nodes.py --range 100:110       # 按序号区间浏览
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402
from retrieval.nodes import load_nodes  # noqa: E402


def percentile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def stats_report(nodes) -> int:
    lengths = sorted(len(n.text) for n in nodes)
    n = len(nodes)
    ids = [n_.node_id for n_ in nodes]
    dup_ids = {i for i in ids if ids.count(i) > 1}
    texts = [n_.text for n_ in nodes]
    dup_texts = {t[:40] for t in texts if texts.count(t) > 1}
    empty = sum(1 for t in lengths if t == 0)
    no_page = sum(
        1 for x in nodes if x.page_print is None or x.page_physical is None
    )
    over = sum(1 for t in lengths if t > 2500)

    print(f"节点数        : {n}")
    print(f"字符长度分布  : min={lengths[0] if n else 0} p50={percentile(lengths, 0.5)} "
          f"avg={sum(lengths) // n if n else 0} p95={percentile(lengths, 0.95)} "
          f"max={lengths[-1] if n else 0}")
    print(f"空文本        : {empty}")
    print(f"重复 ID       : {len(dup_ids)}" + (f" 例: {list(dup_ids)[:3]}" if dup_ids else ""))
    print(f"重复文本      : {len(dup_texts)}")
    print(f"缺双页码      : {no_page}")
    print(f">2500 字符块  : {over}（原子保护块表格/代码可超，正常）")
    bad = empty or dup_ids or dup_texts or no_page
    print("结论          : " + ("存在异常，见上" if bad else "通过（无空 Node / 无重复 / 页码齐全）"))
    return 1 if bad else 0


def show(nodes, i: int, head: int = 120) -> None:
    nd = nodes[i]
    meta = nd.metadata
    print(f"[{i:04d}] {nd.node_id}")
    print(f"       {nd.section or '(无章节)'} | 页 印刷{nd.page_print}/物理{nd.page_physical}"
          f" | {len(nd.text)} 字符 | source_id={meta.get('source_id')}")
    preview = nd.text[:head].replace("\n", "⏎")
    print(f"       {preview}{'…' if len(nd.text) > head else ''}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="inspect_nodes", description=__doc__)
    parser.add_argument("--config", default="configs/experiments/struct_v1.yaml")
    parser.add_argument("--sample", type=int, default=0, help="随机抽样条数")
    parser.add_argument("--seed", type=int, default=None, help="抽样随机种子")
    parser.add_argument("--grep", default=None, help="按正文子串定位（最多列 20 条）")
    parser.add_argument("--range", dest="rng", default=None, help="序号区间 a:b（含 a 不含 b）")
    args = parser.parse_args(argv)

    cfg = ec.load(args.config)
    nodes_file = ec.nodes_path(cfg)
    if not nodes_file.exists():
        print(f"[inspect] 错误: Node 集不存在 {nodes_file}（先运行 make ingest）",
              file=sys.stderr)
        return 1

    nodes = load_nodes(nodes_file)
    print(f"[inspect] {nodes_file.relative_to(REPO_ROOT)}  ({len(nodes)} nodes)\n")
    rc = stats_report(nodes)

    if args.grep:
        hits = [i for i, nd in enumerate(nodes) if args.grep in nd.text]
        print(f"\n--- grep '{args.grep}': {len(hits)} 命中 ---")
        for i in hits[:20]:
            show(nodes, i)
    if args.rng:
        a, _, b = args.rng.partition(":")
        lo = int(a)
        hi = int(b) if b else len(nodes)
        print(f"\n--- 区间 [{lo}, {hi}) ---")
        for i in range(max(0, lo), min(hi, len(nodes))):
            show(nodes, i)
    if args.sample:
        rnd = random.Random(args.seed)
        idxs = rnd.sample(range(len(nodes)), min(args.sample, len(nodes)))
        print(f"\n--- 随机抽样 {len(idxs)} 条"
              + (f"（seed={args.seed}）" if args.seed is not None else "") + " ---")
        for i in idxs:
            show(nodes, i)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
