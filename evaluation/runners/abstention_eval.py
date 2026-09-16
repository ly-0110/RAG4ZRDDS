"""20 题「不存在信息」拒答专项（成员 C · 第四周 §8 成员 C 第一条）。

逐题：检索 → 生成 → 断言「拒答」（generation.abstention.is_abstention）。
「20 个不存在信息专项题全部不虚构」= 20/20 拒答；任一题未拒答（即模型自信
回答了本不存在的内容）→ 退出码非 0，可直接挂 CI 或 pre-merge。

复用 answer_eval 的生成与检索装配（不重复实现）。真实跑需 LLM env（.env）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation.datasets import abstention as ab  # noqa: E402
from evaluation.runners.answer_eval import _build_retriever, _generate  # noqa: E402
from generation.abstention import is_abstention  # noqa: E402


async def evaluate_abstention(cfg, questions: list[dict], *, chat_stream=None) -> list[dict]:
    retriever = _build_retriever(cfg)
    out: list[dict] = []
    for q in questions:
        chunks = await retriever.retrieve(q["question"], cfg.retrieval.top_k)
        answer = await _generate(cfg, q["question"], chunks, chat_stream)
        out.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "abstained": is_abstention(answer),
            "answer": answer,
            "n_retrieved": len(chunks),
            "top1_score": chunks[0]["score"] if chunks else None,
            "top1_section": (chunks[0].get("section") or "") if chunks else "",
        })
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="abstention_eval", description=__doc__)
    parser.add_argument("--config", default="configs/experiments/final_v1.yaml")
    parser.add_argument("--questions", default=str(ab.DATASET))
    args = parser.parse_args(argv)

    import experiment_config as ec

    try:
        cfg = ec.load(args.config)
    except ec.ConfigError as e:
        print(f"[abstention] 配置无效：\n{e}", file=sys.stderr)
        return 1

    cases = ab.load(args.questions)
    problems = ab.validate(cases)
    if problems:
        print("[abstention] 专项题校验失败：", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1

    results = asyncio.run(evaluate_abstention(cfg, cases))
    abstained = sum(1 for r in results if r["abstained"])

    print(f"[abstention] 拒答 {abstained}/{len(results)}")
    for r in results:
        flag = "✓" if r["abstained"] else "✗ 虚构风险"
        print(f"[abstention]   {flag} {r['id']} [{r['category']}] 检索 {r['n_retrieved']} 条"
              f" top1={r['top1_section'] or '—'}")
        if not r["abstained"]:
            print(f"[abstention]     回答: {r['answer'][:120]}")

    out = ec.report_path(cfg).parent / "abstention_eval.json"
    out.write_text(json.dumps({
        "config": cfg.experiment.name,
        "abstained": abstained,
        "total": len(results),
        "per_question": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[abstention] 明细 → {out.relative_to(REPO_ROOT)}")
    return 0 if abstained == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
