#!/usr/bin/env python
"""
scripts/audit_annotations.py — 标注真值核对（成员 D · 第四周，指南 §6.1 / §9.3 / §10）

为什么存在：评测指标的有效性完全取决于 expected_sources 是不是**逐题对 PDF 核对过**的
真值。第二、三周两次事故（E 的 PR#13 / PR#22）都是"标注 = 检索 top-1 回显"，用检索结果
给检索打分，hit_rate=1.0 属构造产物，评测因此丧失发现缺陷的能力。
本工具的判定一律来自 **A 的产物与章节树**（分块正文、printed_page_start/end、章节标题），
不调用任何检索器——因此它无法被"从检索结果反推"的标注蒙过去。

E（标注 Owner）在提交前自查、D 在开指标闸门前验收，都用同一份证据。
用法:
  python scripts/audit_annotations.py                       # 默认集，打印摘要
  python scripts/audit_annotations.py --out-prefix evaluation/reports/annotation_audit
  make audit

判定与退出码：
  0  无阻断项且未见循环论证指纹 → 可以开 `run_regression --with-metrics`
  1  存在阻断项（格式违约 / 页码越界 / 页码无承载块 / 术语零命中 / 章节-页码矛盾 /
     题干全部 token 离页）
     或 循环论证指纹 ≥ --circular-threshold
  另外，题干"部分 token 离页"记为 `QUESTION_TOKEN_CROSS_CHAPTER`：跨章节 API 的正常
  形态，记录但不阻断（判定语义见 QUESTION_TOKEN_REVIEW_CODES 的注释）。
  2  参数或文件缺失

依赖: 仅标准库；产物路径全部可参数化（单测用 tmp_path 喂小样本）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# 页码/章节判定的宽容度：印刷页允许 ±2（跨页小节、页眉归属歧义）
PAGE_TOLERANCE = 2

# 判定码 → 是否阻断指标闸门（阻断=该标注不可信，必须回炉）
BLOCKING_CODES = {
    "CONTRACT_MISSING",           # 题没有标注
    "CONTRACT_NO_CONDITION",      # 标注没给任何可用匹配条件
    "CONTRACT_UNKNOWN_SOURCE",    # source_id 不在产物里
    "PAGE_OUT_OF_RANGE",          # 页码越出该来源真实页区间（如手册最大印刷页 289）
    "PAGE_NO_CHUNK",              # 标注页在该来源里没有任何块承载 → 页码不来自产物
    "TERM_NOT_FOUND",             # 关键词在章节树与全部正文里零命中 → 疑似编造
    "TERM_PAGE_MISMATCH",         # 术语只出现在与标注页相距很远的页 → 页码与语义矛盾
    "SECTION_PAGE_MISMATCH",      # 关键词命中的章节页区间不含标注页
    "HTML_PAGE_SHOULD_BE_NULL",   # HTML 来源无页码概念却标了页码
    "PAGE_INVALID",               # 页码不是整数或合法闭区间
    "QUESTION_TOKEN_OFF_PAGE",    # 题干的**全部** token 都不在被标注页附近 → 这页回答不了这题
    "QUESTION_TOKEN_ABSENT",      # 题面技术 token 在该来源全书零命中 → 实体不存在，应转拒答集
}

# 非阻断但需人工确认：题干只有**部分** token 离页。这是跨章节 API 的正常形态
# （回调在 Listener 章节、字段类型在 IDL/类型章节；手册按 QoS 策略分章列字段名），
# 用它把"标注页选错"与"题目天然跨章"区分开：
#   - 全部 token 离页 → QUESTION_TOKEN_OFF_PAGE（阻断：这页确实答不了这题）
#   - 至少一个 token 落在标注页附近 → QUESTION_TOKEN_CROSS_CHAPTER（记录，不阻断）
# 2026-09-16 实测：Q018/Q026/Q065/Q066 都属后者（如 Q065 标注 Policy 章节 160-161，
# `writer_data_lifecycle` 字段名只在该策略的 IDL 字段表 81-84 出现）。
QUESTION_TOKEN_REVIEW_CODES = {"QUESTION_TOKEN_CROSS_CHAPTER"}

# 题干 token 抽取：太通用的词不算"问题主体"
TOKEN_STOP = {
    "zrdds", "what", "when", "which", "where", "while", "how", "why", "does", "done",
    "can", "the", "and", "for", "with", "api", "dds", "int", "void", "true", "false",
    "please", "need", "must", "should", "used", "using", "user", "manual",
}
TOKEN_RE = None      # 延迟编译（见 question_tokens）


def question_tokens(text: str, limit: int = 3) -> list[str]:
    """从题干取技术 token（ASCII 标识符，长度 ≥5，按长度优先，最多 limit 个）。

    开发者问题必然带精确 token（指南 §8.1：DomainParticipant / create_datawriter() /
    v2.4），这类 token 出现在哪一页是产物里可查的硬事实——因此"标注页答不对题"
    能在不依赖检索、也不依赖 LLM 的情况下被发现。中文题干的实体现也含在标识符里
    （如 `DurabilityQosPolicy`），无标识符的纯中文题记 NO_TOKEN_PROBE 交人工。
    """
    import re

    global TOKEN_RE
    if TOKEN_RE is None:
        TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{4,}")
    seen: list[str] = []
    for tok in TOKEN_RE.findall(text or ""):
        low = tok.lower()
        if low in TOKEN_STOP or low in seen:
            continue
        seen.append(low)
    return sorted(seen, key=lambda t: (-len(t), t))[:limit]


# ---------------------------------------------------------------- 读入


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm(text: str | None) -> str:
    """归一化：去空白 + 小写。中文关键词与 C 标识符大小写/空格差异不该影响命中。"""
    return "".join((text or "").split()).lower()


def annotation_pages(page: Any) -> tuple[int, int] | None:
    """Normalize a single page or an inclusive [start, end] page range."""
    if isinstance(page, bool):
        return None
    if isinstance(page, int):
        return page, page
    if (isinstance(page, list) and len(page) == 2
            and all(isinstance(value, int) and not isinstance(value, bool) for value in page)
            and page[0] <= page[1]):
        return page[0], page[1]
    return None


class ProductTruth:
    """A 的产物 = 页码与章节的唯一真值来源（不经过检索器）。"""

    def __init__(self, nodes: Iterable[dict], tree: Iterable[dict] | None = None) -> None:
        self.pages: dict[str, list[tuple[int, int]]] = {}      # source_id → 块页区间
        self.title_norm: dict[str, set[str]] = {}              # source_id → 归一化章节/标题集合
        self._term_cache: dict[str, dict[str, set[int]]] = {}  # source_id → 术语 → 出现页集合
        self._raw: dict[str, list[tuple[str, tuple[int, int]]]] = {}
        self._section_index: dict[str, list[tuple[str, tuple[int, int]]]] = {}
        for node in nodes:
            self._absorb_node(node)
        for sec in tree or []:
            self._absorb_section(sec)

    # 产物字段解析 ----------------------------------------------------
    @staticmethod
    def _source_and_pages(node: dict) -> tuple[str | None, int | None, int | None]:
        meta = node.get("metadata") or {}
        source = meta.get("source_id")
        start = meta.get("printed_page_start")
        end = meta.get("printed_page_end", start)
        if start is None:
            start = meta.get("page_print")
            end = meta.get("page_print_end", start)
        return source, start, end

    def _absorb_node(self, node: dict) -> None:
        source, start, end = self._source_and_pages(node)
        if not source:
            return
        meta = node.get("metadata") or {}
        if start is not None:
            span = (start, end if end is not None else start)
            self.pages.setdefault(source, []).append(span)
            self._raw.setdefault(source, []).append(
                (_norm(node.get("text")), (start, end if end is not None else start)))
        for title in (meta.get("title"), meta.get("section_path")):
            if title:
                self.title_norm.setdefault(source, set()).add(_norm(title))

    def _absorb_section(self, sec: dict) -> None:
        source = sec.get("source_id") or "user_manual"
        title, path = sec.get("title"), sec.get("section_path")
        bucket = self.title_norm.setdefault(source, set())
        if title:
            bucket.add(_norm(title))
        if path:
            bucket.add(_norm(path))

    # 查询接口 --------------------------------------------------------
    @property
    def sources(self) -> set[str]:
        return set(self.pages) | set(self.title_norm)

    def page_bounds(self, source_id: str) -> tuple[int, int] | None:
        spans = self.pages.get(source_id)
        if not spans:
            return None
        return min(s for s, _ in spans), max(e for _, e in spans)

    def has_page(self, source_id: str, page: int) -> bool:
        """该页是否落在某个块的 printed_page 区间内（含 ±PAGE_TOLERANCE 宽容）。"""
        return any(s - PAGE_TOLERANCE <= page <= e + PAGE_TOLERANCE
                   for s, e in self.pages.get(source_id, []))

    def term_pages(self, source_id: str, term: str) -> set[int]:
        """术语在正文里出现过的印刷页集合；完全没出现返回空集。"""
        nt = _norm(term)
        if not nt:
            return set()
        cache = self._term_cache.setdefault(source_id, {})
        if nt in cache:
            return cache[nt]
        found: set[int] = set()
        for text, span in self._raw.get(source_id, []):
            if nt in text:
                found.update(range(span[0], span[1] + 1))
        cache[nt] = found
        return found

    def section_span(self, source_id: str, term: str) -> tuple[int, int] | None:
        """关键词若命中某章节标题，返回该章节页区间（用于章节-页码一致性判定）。"""
        nt = _norm(term)
        if not nt:
            return None
        for key, span in self._section_index.get(source_id, []):
            if nt == key or nt in key:
                return span
        return None

    def title_matches(self, source_id: str, term: str) -> bool:
        """关键词是否是某块标题/节路径（metadata.title / section_path）。

        章节树可能缺失（HTML 来源没有，或只跑过 --nodes），但块标题还在——不认它
        就会把正常标注误判成 TERM_NOT_FOUND。
        """
        nt = _norm(term)
        if not nt:
            return False
        return any(nt in title for title in self.title_norm.get(source_id, set()))

    def load_section_index(self, rows: list[dict]) -> None:
        for sec in rows:
            source = sec.get("source_id") or "user_manual"
            start, end = sec.get("printed_page_start"), sec.get("printed_page_end")
            if start is None:
                continue
            self._section_index.setdefault(source, []).append(
                (_norm(sec.get("title")), (start, end if end is not None else start)))


# ---------------------------------------------------------------- 逐题判定


def audit_annotation(ann: dict, truth: ProductTruth, top1_page: int | None,
                     questions_ids: set[str],
                     question_text: str = "",
                     check_question_tokens: bool = True) -> tuple[list[str], dict]:
    """返回 (判定码列表, token 探查明细)。判据只来自产物，绝不查检索器。"""
    findings: list[str] = []
    qid = ann.get("question_id")
    if not qid or qid not in questions_ids:
        findings.append("CONTRACT_UNKNOWN_QUESTION_ID")

    source = ann.get("source_id")
    page = ann.get("page_print")
    keyword = ann.get("section_keyword")

    if not any(v is not None and v != "" for v in (source, page, keyword)):
        findings.append("CONTRACT_NO_CONDITION")
        return findings, {}

    bounds = truth.page_bounds(source) if source else None
    if source and source not in truth.sources:
        findings.append("CONTRACT_UNKNOWN_SOURCE")
    if source and bounds is None and page is not None:
        # 该来源在产物里根本没有页码（HTML 来源）→ 不该标印刷页
        findings.append("HTML_PAGE_SHOULD_BE_NULL")

    page_span = annotation_pages(page)
    if page_span and bounds:
        lo, hi = bounds
        page_lo, page_hi = page_span
        if page_lo < lo or page_hi > hi:
            findings.append("PAGE_OUT_OF_RANGE")
        elif not any(truth.has_page(source, candidate)
                     for candidate in range(page_lo, page_hi + 1)):
            findings.append("PAGE_NO_CHUNK")
    elif page is not None and page_span is None:
        findings.append("PAGE_INVALID")

    if keyword:
        span = truth.section_span(source, keyword)
        in_title = span is not None or truth.title_matches(source, keyword)
        pages_with_term = truth.term_pages(source, keyword) if source else set()
        if not in_title and not pages_with_term:
            findings.append("TERM_NOT_FOUND")               # 标题与正文都找不到 → 疑似编造
        if span and page_span \
                and (page_span[1] < span[0] - PAGE_TOLERANCE
                     or page_span[0] > span[1] + PAGE_TOLERANCE):
            findings.append("SECTION_PAGE_MISMATCH")        # 关键词章节的页区间不含标注页
        if pages_with_term and page_span \
                and all(p < page_span[0] - PAGE_TOLERANCE
                        or p > page_span[1] + PAGE_TOLERANCE
                        for p in pages_with_term):
            findings.append("TERM_PAGE_MISMATCH")           # 术语只出现在远处的页

    # 题干 token 必须落在被标注页附近——否则"这页回答不了这题"
    probe: dict[str, Any] = {}
    tokens = question_tokens(question_text) if check_question_tokens else []
    probe["tokens"] = tokens
    if not check_question_tokens:
        probe["tokens"] = []
    elif not tokens:
        findings.append("NO_TOKEN_PROBE")        # 纯中文题干，交人工核对
    elif page_span and source:
        absent, off_page, on_page = [], [], []
        page_lo, page_hi = page_span
        for tok in tokens:
            pages = truth.term_pages(source, tok)
            if not pages:
                absent.append(tok)
            elif any(page_lo - PAGE_TOLERANCE <= p <= page_hi + PAGE_TOLERANCE
                     for p in pages):
                on_page.append(tok)
            else:
                off_page.append({"token": tok, "appears_on": sorted(pages)[:8]})
        if absent:
            probe["absent"] = absent
            findings.append("QUESTION_TOKEN_ABSENT")
        if off_page:
            probe["unmatched"] = off_page
            # 只有"全部 token 都离页"才是这页答不了这题；部分离页是跨章节引用
            findings.append("QUESTION_TOKEN_OFF_PAGE" if not on_page
                            else "QUESTION_TOKEN_CROSS_CHAPTER")

    # A range is intentionally excluded: broad, source-backed ranges commonly
    # contain the retrieved top-1 by chance and are not evidence of circularity.
    if top1_page is not None and isinstance(page, int) and page == top1_page:
        findings.append("CIRCULAR_TOP1")         # 指纹项：聚合后看比例，不单独阻断
    return findings, probe


def audit(expected: list[dict], questions: list[dict], truth: ProductTruth,
          report_top1: dict[str, int], circular_threshold: float = 0.9) -> dict:
    """逐题判定 → 汇总。blocking>0 或循环指纹比例超阈值即判不通过。"""
    qids = {q.get("id") for q in questions}
    qtexts = {q.get("id"): (q.get("question") or "") for q in questions}
    per_question: list[dict] = []
    counts: dict[str, int] = {}
    annotated_ids = {a.get("question_id") for a in expected}

    source_counts: dict[str, int] = {}
    for ann in expected:
        source_counts[ann.get("question_id")] = source_counts.get(ann.get("question_id"), 0) + 1

    for ann in expected:
        codes, probe = audit_annotation(
            ann, truth, report_top1.get(ann.get("question_id")), qids,
            qtexts.get(ann.get("question_id"), ""),
            check_question_tokens=source_counts.get(ann.get("question_id"), 0) <= 1)
        for c in codes:
            counts[c] = counts.get(c, 0) + 1
        per_question.append({
            "question_id": ann.get("question_id"),
            "question": (qtexts.get(ann.get("question_id")) or "")[:80],
            "source_id": ann.get("source_id"),
            "page_print": ann.get("page_print"),
            "section_keyword": ann.get("section_keyword"),
            "findings": codes,
            "blocking": sorted(set(codes) & BLOCKING_CODES),
            "probe": probe,
        })

    missing = sorted(q for q in qids if q and q not in annotated_ids)
    for _ in missing:
        counts["CONTRACT_MISSING"] = counts.get("CONTRACT_MISSING", 0) + 1
    extra = sorted(a for a in annotated_ids if a and a not in qids)

    blocking_total = sum(counts.get(c, 0) for c in BLOCKING_CODES) + len(missing)
    matched = sum(1 for r in per_question if "CIRCULAR_TOP1" in r["findings"])
    comparable = sum(1 for r in per_question
                     if r["question_id"] in report_top1 and r["page_print"] is not None)
    circular_ratio = round(matched / comparable, 4) if comparable else None
    circular_suspect = circular_ratio is not None and circular_ratio >= circular_threshold

    verdict = "pass"
    if blocking_total or missing or extra:
        verdict = "blocked"
    if circular_suspect:
        verdict = "suspect_circular" if verdict == "pass" else verdict
    return {
        "schema": "rag4zrdds.annotation_audit/v1",
        "verdict": verdict,
        "counts": counts,
        "blocking_total": blocking_total,
        "questions_total": len(qids),
        "annotations_total": len(expected),
        "missing_annotations": missing,
        "unknown_question_ids": extra,
        "circularity": {
            "compared_with": "报告 top-1 页码（仅作反推指纹，不作真值判据）",
            "matched": matched,
            "comparable": comparable,
            "ratio": circular_ratio,
            "threshold": circular_threshold,
            "suspect": circular_suspect,
        },
        "per_question": per_question,
    }


def render_markdown(result: dict, sources: dict[str, str]) -> str:
    lines = [
        "# 标注真值核对报告",
        "",
        f"- 结论: **{result['verdict']}**"
        f"（阻断项 {result['blocking_total']}，缺标注 {len(result['missing_annotations'])}，"
        f"多余 {len(result['unknown_question_ids'])}）",
        f"- 题量: 问题集 {result['questions_total']} / 标注 {result['annotations_total']}",
        f"- 循环论证指纹: 与 {sources.get('report', '-')}"
        f" top-1 页码吻合 {result['circularity']['matched']}"
        f"/{result['circularity']['comparable']}"
        f"（比例 {result['circularity']['ratio']}，阈值 {result['circularity']['threshold']}）"
        f" → {'疑似反推' if result['circularity']['suspect'] else '未见异常'}",
        "",
        "> 判据全部来自 A 的产物与章节树（分块正文、printed_page_start/end、章节标题），"
        "**不调用检索器**——所以从检索结果反推的标注骗不过它。top-1 比对只用来抓"
        "\"标注=检索回显\"的指纹，不当真值用。",
        "",
        "## 逐题判定（仅列有问题的题）",
        "",
        "| 题号 | 页码 | 关键词 | 判定 | token 实况 |",
        "|---|---|---|---|---|",
    ]
    bad = [r for r in result["per_question"] if r["findings"]]
    for r in bad[:60]:
        kw = (r["section_keyword"] or "")[:28]
        probe = r.get("probe") or {}
        detail = "; ".join(
            [f"{t}→全书零命中" for t in (probe.get("absent") or [])[:1]]
            + [f"{u['token']}→实际在 {u['appears_on'][:4]}"
               for u in (probe.get("unmatched") or [])[:1]]) or "—"
        lines.append(f"| {r['question_id']} | {r['page_print']} | {kw} "
                     f"| {', '.join(r['findings'])} | {detail} |")
    if len(bad) > 60:
        lines.append("| … | | | | 另有 {0} 题同类问题 |".format(len(bad) - 60))
    lines += ["", "## 判定码计数", ""]
    for code, n in sorted(result["counts"].items(), key=lambda kv: -kv[1]):
        if code in BLOCKING_CODES or code in {"CONTRACT_MISSING",
                                              "CONTRACT_UNKNOWN_QUESTION_ID"}:
            tag = "阻断"
        elif code in QUESTION_TOKEN_REVIEW_CODES:
            tag = "非阻断（需人工确认：题目是否天然跨章节）"
        else:
            tag = "指纹"
        lines.append(f"- `{code}` = {n}（{tag}）")
    if result["missing_annotations"]:
        lines += ["", f"缺标注题号: {', '.join(result['missing_annotations'][:40])}"]
    lines += ["", "## 闸门含义",
              "",
              "- `blocked` / `suspect_circular` → **不得**开 `make regression "
              "REG_ARGS=--with-metrics`，指标只记不判（宁缺毋滥）。",
              "- `pass` → 指标通道方可启用，六份 void 报告才能刷新为可引用数字。"]
    return "\n".join(lines) + "\n"


def _disp(path: Path) -> str:
    """仓库相对路径展示；路径在仓库外（如单测 tmp_path）时退回绝对路径。"""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def report_top1_pages(report_path: Path) -> dict[str, int]:
    """从既有实验报告取每题 top-1 印刷页——只用于\"标注是否反推自检索\"的指纹比对。"""
    if not report_path.exists():
        return {}
    data = json.loads(report_path.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for entry in data.get("per_question") or []:
        refs = entry.get("retrieved") or []
        page = (refs[0] or {}).get("page_print") if refs else None
        if entry.get("id") and isinstance(page, int):
            out[entry["id"]] = page
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):      # Windows GBK 控制台
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="audit_annotations", description=__doc__)
    p.add_argument("--questions", default="evaluation/datasets/questions.jsonl")
    p.add_argument("--expected", default="evaluation/datasets/expected_sources.jsonl")
    p.add_argument("--nodes", default="data/processed/struct_v1.jsonl",
                   help="真值来源：A 的 Node 产物（含 printed_page_start/end 与正文）")
    p.add_argument("--tree", default="data/processed/section_tree_v1.jsonl",
                   help="真值来源：章节树（章节标题与页区间）")
    p.add_argument("--report", default="evaluation/reports/struct_v1.json",
                   help="仅用于\"标注=检索回显\"指纹比对的报告（不作真值）")
    p.add_argument("--circular-threshold", type=float, default=0.9)
    p.add_argument("--out-prefix", default=None,
                   help="同时写 <prefix>.json 与 <prefix>.md")
    p.add_argument("--emit-abstention", default=None,
                   help="把\"题面实体零命中\"的题导出为拒答案例候选 jsonl（供成员 C 专项集）")
    args = p.parse_args(argv)

    paths = {k: REPO_ROOT / getattr(args, k) for k in
             ("questions", "expected", "nodes", "tree", "report")}
    required = ["questions", "expected", "nodes"]
    missing = [_disp(paths[k]) for k in required if not paths[k].exists()]
    if missing:
        print(f"[audit] 错误: 缺少必需输入 {missing}（章节树/报告可选，缺失则相应判据跳过）",
              file=sys.stderr)
        return 2

    questions = load_jsonl(paths["questions"])
    expected = load_jsonl(paths["expected"])
    tree_rows = load_jsonl(paths["tree"]) if paths["tree"].exists() else []
    truth = ProductTruth(load_jsonl(paths["nodes"]), tree_rows)
    truth.load_section_index(tree_rows)
    top1 = report_top1_pages(paths["report"])

    result = audit(expected, questions, truth, top1, args.circular_threshold)
    result["inputs"] = {k: _disp(v) for k, v in paths.items()}

    print(f"[audit] 题量 {result['questions_total']} / 标注 {result['annotations_total']}"
          f"；判定 {result['verdict']}")
    for code, n in sorted(result["counts"].items(), key=lambda kv: -kv[1]):
        print(f"[audit]   {code:<26} {n}")
    circ = result["circularity"]
    print(f"[audit]   循环论证指纹: {circ['matched']}/{circ['comparable']} = {circ['ratio']}"
          f"（阈值 {circ['threshold']}）")
    bad = [r["question_id"] for r in result["per_question"] if r["blocking"]]
    if bad:
        print(f"[audit] 需回炉的题（前 20）: {bad[:20]}")

    if args.out_prefix:
        prefix = REPO_ROOT / args.out_prefix
        prefix.parent.mkdir(parents=True, exist_ok=True)
        prefix.with_suffix(".json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prefix.with_suffix(".md").write_text(
            render_markdown(result, {"report": _disp(paths["report"])}),
            encoding="utf-8")
        print(f"[audit] 明细 → {_disp(prefix.with_suffix('.md'))}")

    if args.emit_abstention:
        out = REPO_ROOT / args.emit_abstention
        out.parent.mkdir(parents=True, exist_ok=True)
        q_full = {q.get("id"): (q.get("question") or "") for q in questions}
        rows = [{
            "question_id": r["question_id"],
            "question": q_full.get(r["question_id"], ""),
            "absent_tokens": (r.get("probe") or {}).get("absent", []),
            "why": "题面技术 token 在该来源全库零命中（产物=唯一真值），应为无证据题",
            "detected_by": "scripts/audit_annotations.py",
        } for r in result["per_question"] if "QUESTION_TOKEN_ABSENT" in r["findings"]]
        with out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[audit] 拒答案例候选 {len(rows)} 题 → {_disp(out)}")

    if result["verdict"] == "pass":
        print("[audit] ✓ 标注达到开指标闸门的条件（run_regression --with-metrics）")
        return 0
    print("[audit] ✗ 标注未达标准：指标通道保持静默（宁缺毋滥）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
