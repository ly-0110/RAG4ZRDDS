#!/usr/bin/env python3
"""人工抽检 30 题（指南 §9.3）——确定性抽题 + 六问检查清单。

LLM-based evaluation 不能替代人工检查：本脚本从正式问题集确定性抽 30 题，
产出 §9.3 六问检查清单 markdown（是否回答 / 技术事实正确 / 有文档依据 /
Citation 准确 / 虚构 API / 混用版本），供成员 C 逐题人工签署。

抽题口径：random.Random(0) 固定种子 → 排序输出，两次运行结果逐字节一致（可复现）。

用法：
  python scripts/sample_manual_review.py                # 用默认问题集
  python scripts/sample_manual_review.py --dataset ... --n 30 --out ...
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SIX_CHECKS = (
    "是否回答了问题",
    "技术事实是否正确",
    "是否有文档依据",
    "Citation 是否准确",
    "是否出现虚构 API",
    "是否混用了版本",
)


def load_questions(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def sample(questions: list[dict], n: int, seed: int = 0) -> list[dict]:
    picked = random.Random(seed).sample(questions, min(n, len(questions)))
    return sorted(picked, key=lambda q: q["id"])


def render(questions: list[dict]) -> str:
    header = "| 题号 | 问题 | " + " | ".join(SIX_CHECKS) + " |"
    sep = "|---|" + "---|" * len(SIX_CHECKS)
    rows = []
    for q in questions:
        cells = [q["id"], q["question"]] + ["" for _ in SIX_CHECKS]
        rows.append("| " + " | ".join(cells) + " |")
    lines = [
        "# 人工抽检 30 题（指南 §9.3）",
        "",
        f"- 抽样：{len(questions)} 题，固定种子 0，确定性可复现",
        f"- 检查人：成员 C　·　日期：待填",
        f"- 六问逐题勾选；任一问题答「否」需在备注说明原因与处置。",
        "",
        header,
        sep,
        *rows,
        "",
        "> 由 `scripts/sample_manual_review.py` 生成。勾选后回填本文件作为人工评测证据。",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="evaluation/datasets/questions.jsonl")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--out", default="evaluation/reports/manual_review.md")
    args = parser.parse_args(argv)

    qpath = REPO_ROOT / args.dataset
    if not qpath.exists():
        print(f"[manual-review] 问题集不存在: {qpath}", file=sys.stderr)
        return 1
    questions = load_questions(qpath)
    if len(questions) < args.n:
        print(f"[manual-review] 问题集 {len(questions)} 题 < 抽样数 {args.n}", file=sys.stderr)
        return 1

    picked = sample(questions, args.n)
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(picked), encoding="utf-8")
    print(f"[manual-review] 抽 {len(picked)} 题 → {out.relative_to(REPO_ROOT)}")
    print(f"[manual-review]   {', '.join(q['id'] for q in picked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
