#!/usr/bin/env python3
"""collect_real_error_cases.py —— 从真实实验报告提取错误案例（D · 验收项 5 补采）。

背景（2026-09-07 会签决议）：验收项 5 要求「≥20 个真实错误案例」。C 在 PR#19 交付的
error_cases.jsonl（20 例）经真值核对全部为手写虚构场景（引用未接入的 dev_guide 源、
印刷页 300 超界、正文在产物中零命中），按「宁缺毋滥」先例不计入验收，保留为第三周
多来源通路的测试夹具。本脚本补采「真实」案例：

数据来源（全部为已落盘的真实产物，无任何手写证据）：
  * evaluation/reports/{struct_v1,semantic_v1,hybrid_v1,struct_bm25}.json 的逐题检索明细
    （对真实产物、真实索引跑出的引用与分数）
  * evaluation/datasets/audit-2026-08-30.md 的人工核对真值（15 题逐题研判，2026-08-30 定稿）

案例类别（只收可辩护的，不凑数）：
  no_evidence_signal_missing  审计判定「知识库中不存在答案」的题，检索层仍返回 top_k 条
                              中高自信度证据——系统层缺陷：无校准的无证据信号，
                              这类证据喂给生成侧易诱发虚构（对应验收项 7 的风险）。
  verified_wrong_top1         有真值页码区间的题，某配置的 top1 落在真值区间之外——
                              人工真值对照下的已验证错误命中。
  cross_config_disagreement   同一题在不同配置下 top1 印刷页不一致——真实可复现的
                              检索稳定性问题（同一问题四个答案）。

用法：
  python evaluation/datasets/collect_real_error_cases.py            # 生成/覆盖 jsonl
  python evaluation/datasets/collect_real_error_cases.py --dry-run  # 只打印统计

输出：evaluation/datasets/error_cases_real.jsonl（入库，验收项 5 载体）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# 四份报告 → 各自索引的产物文件（node_id 归属校验用）
REPORTS = {
    "struct_v1": ("evaluation/reports/struct_v1.json", "data/processed/struct_v1.jsonl"),
    "semantic_v1": ("evaluation/reports/semantic_v1.json", "data/processed/semantic_v1.jsonl"),
    "hybrid_v1": ("evaluation/reports/hybrid_v1.json", "data/processed/hybrid_v1.jsonl"),
    "struct_bm25": ("evaluation/reports/struct_bm25.json", "data/processed/struct_v1.jsonl"),
}

# 人工审计真值（唯一事实源：evaluation/datasets/audit-2026-08-30.md，2026-08-30 定稿）。
# "absent" = 审计判定知识库中不存在该题的答案（API/错误码/章节系虚构或指向第三周 HTML 源）。
TRUTHS: dict[str, dict] = {
    "Q001": {"absent": True, "note": "全库无 connect()（审计：API 系虚构）"},
    "Q002": {"ranges": [(168, 171), (276, 277)], "note": "11.2 软件安装指南 p168-171；Docker 另见 p276-277"},
    "Q003": {"absent": True, "note": "全库无 E1003（审计：错误码系虚构）"},
    "Q004": {"absent": True, "note": "无 DomainParticipant.connect()（审计：API 系虚构）"},
    "Q005": {"ranges": [(168, 171)], "note": "11.2 软件安装指南（图 11-5 在其中）"},
    "Q006": {"ranges": [(248, 255)], "note": "第 20 章 XML 配置实体 QoS p248-255"},
    "Q007": {"ranges": [(247, 248)], "note": "第 19 章 简化接口 SUSTAIN p247-248"},
    "Q008": {"ranges": [(57, 58)], "note": "6.3.11 域信息查询 p57-58"},
    "Q009": {"ranges": [(248, 255)], "note": "20.1 XML 配置说明 p248 起"},
    "Q010": {"absent": True, "note": "全库无产品版本对比章节（审计：不存在信息）"},
    "Q011": {"ranges": [(278, 289)], "note": "PART 11 日志使用 p278-289（无独立故障排查章）"},
    "Q012": {"ranges": [(57, 57), (219, 225)], "note": "6.3.10 通信管理 p57；C 接口映射 p219-225"},
    "Q013": {"ranges": [(168, 168)], "note": "11.1 运行环境要求 p168"},
    "Q014": {"ranges": [(242, 246)], "note": "第 18 章 简化接口 p242-246"},
    "Q015": {"absent": True, "note": "指向的「开发指南」为 HTML 源（第三周才接入）"},
}


def _in_ranges(page: int | None, ranges: list[tuple[int, int]]) -> bool:
    return page is not None and any(lo <= page <= hi for lo, hi in ranges)


# 章节边界容差：审计文档自身的口径是「差 1 页 = 基本准确」，故真值区间向两侧各扩 1 页；
# 容差内的相邻命中不计入已验证错误（宁可少算，不做边界争议判定）。
PAGE_TOLERANCE = 1


def _clearly_misses(page: int | None, ranges: list[tuple[int, int]]) -> bool:
    if page is None:
        return False
    return not any(lo - PAGE_TOLERANCE <= page <= hi + PAGE_TOLERANCE
                   for lo, hi in ranges)


def _load_nodes_index(product_rel: str) -> dict[str, dict]:
    """product jsonl → {node_id: 记录}，供证据存在性校验。"""
    path = REPO_ROOT / product_rel
    if not path.exists():
        raise FileNotFoundError(f"产物不存在（先 make ingest）：{path}")
    index: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            # 产物顶层键是 chunk_id（A 的 Chunk 契约）；node_id 走 B 的 load_nodes 同款回退链
            nid = rec.get("node_id") or rec.get("chunk_id") \
                or rec.get("metadata", {}).get("chunk_id")
            if nid:
                index[nid] = rec
    return index


def collect() -> list[dict]:
    reports = {
        name: json.loads((REPO_ROOT / rep).read_text(encoding="utf-8"))["per_question"]
        for name, (rep, _) in REPORTS.items()
    }
    cases: list[dict] = []
    qids = [d["id"] for d in reports["struct_v1"]]
    for qid in qids:
        question = next(d["question"] for d in reports["struct_v1"] if d["id"] == qid)
        top1 = {}
        for name, pq in reports.items():
            d = next(x for x in pq if x["id"] == qid)
            top1[name] = d["retrieved"][0] if d["retrieved"] else None

        truth = TRUTHS[qid]
        if truth.get("absent"):
            for name, rec in top1.items():
                if rec is None:
                    continue
                cases.append({
                    "id": f"REAL-NE-{qid}-{name}",
                    "category": "no_evidence_signal_missing",
                    "question": question,
                    "mode": name,
                    "top1": {k: rec[k] for k in
                             ("node_id", "source_id", "source_name", "section",
                              "page_print", "page_physical", "score")},
                    "observation": (
                        f"审计已判定该题在知识库中不存在答案（{truth['note']}），"
                        f"但 {name} 检索仍返回 top1（score={rec['score']:.4f}，"
                        f"印刷页 {rec['page_print']}）——无校准的无证据信号，"
                        "此类证据喂给生成侧易诱发虚构"
                    ),
                    "truth": truth["note"],
                    "provenance": {"report": REPORTS[name][0], "truth_source":
                                   "evaluation/datasets/audit-2026-08-30.md"},
                })
            continue

        ranges = truth["ranges"]
        wrong = {n: r for n, r in top1.items()
                 if r is not None and _clearly_misses(r["page_print"], ranges)}
        for name, rec in wrong.items():
            cases.append({
                "id": f"REAL-WT-{qid}-{name}",
                "category": "verified_wrong_top1",
                "question": question,
                "mode": name,
                "top1": {k: rec[k] for k in
                         ("node_id", "source_id", "source_name", "section",
                          "page_print", "page_physical", "score")},
                "observation": (
                    f"{name} 的 top1 命中印刷页 {rec['page_print']}"
                    f"（{rec['section']}），超出人工核对真值区间 {ranges}"
                    f" ±{PAGE_TOLERANCE} 页容差——已验证的错误命中"
                ),
                "truth": truth["note"],
                "provenance": {"report": REPORTS[name][0], "truth_source":
                               "evaluation/datasets/audit-2026-08-30.md"},
            })

        pages = {r["page_print"] for r in top1.values() if r is not None}
        if len(pages) > 1:
            cases.append({
                "id": f"REAL-CD-{qid}",
                "category": "cross_config_disagreement",
                "question": question,
                "mode": "cross",
                "top1_all": {n: ({"page_print": r["page_print"], "score": round(r["score"], 4),
                                  "section": r["section"]}
                                 if r else None) for n, r in top1.items()},
                "observation": (
                    f"同一问题在 4 个配置下 top1 印刷页不一致：{sorted(p for p in pages if p)}"
                    "——检索稳定性问题，同一问题多个答案"
                ),
                "truth": truth["note"],
                "provenance": {"report": "全部四份", "truth_source":
                               "evaluation/datasets/audit-2026-08-30.md"},
            })
    return cases


def validate(cases: list[dict]) -> list[str]:
    """机器校验「真实」承诺：证据 node_id 必须存在于对应产物，双页码差恒为 6。"""
    problems: list[str] = []
    node_indexes = {name: _load_nodes_index(prod) for name, (_, prod) in REPORTS.items()}
    for c in cases:
        mode = c.get("mode")
        if mode in node_indexes and "top1" in c:
            rec = c["top1"]
            if rec["node_id"] not in node_indexes[mode]:
                problems.append(f"{c['id']}: node_id 不在 {mode} 的产物中（证据非真实）")
            if rec["page_physical"] - rec["page_print"] != 6:
                problems.append(f"{c['id']}: 双页码差 != 6（页码真值契约破坏）")
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        problems.append("案例 id 重复")
    return problems


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
    args = parser.parse_args(argv)

    cases = collect()
    problems = validate(cases)
    from collections import Counter
    by_cat = Counter(c["category"] for c in cases)
    print(f"[real-error-cases] 共 {len(cases)} 例：{dict(by_cat)}")
    if problems:
        print("[real-error-cases] 校验失败：", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("[real-error-cases] 校验通过：证据 node_id 均存在于对应产物，双页码差恒为 6")
    if args.dry_run:
        return 0
    out = HERE / "error_cases_real.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[real-error-cases] 已写入 {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
