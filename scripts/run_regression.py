#!/usr/bin/env python3
"""
scripts/run_regression.py — 回归自动化（成员 D · 第四周核心交付，指南 §8 D 任务 1 / §10）

把 §10 的机制从"约定"变成"一条命令"：
  变更 → 一键跑相关实验 → 与历史报告比对 → 给出 pass / warn / regression / incomparable
  判定，并以退出码告知（非 0 = 回归或失败，可直接挂 CI 或 pre-merge）。

两条通道（宁缺毋滥，2026-09-11 结论：现库标注为循环论证版，指标视同 void）：
  * 明细通道（默认，随时可用）：不依赖标注，比对 top-K 命中集合重合率、rank-1 一致率、
    返回条数与耗时。检索实现/产物若发生退化，这里就会亮红。
  * 指标通道（--with-metrics 显式启用）：真值标注定版后才有意义；启用后指标下跌超容差
    即判 regression。

可比性闸门（本次交付的关键点）：
  报告只看 config_hash8 会伪装可比——R1（PR#11）/R4（PR#13）两次事故都是配置未变、
  磁盘产物被旧基线 PR 换掉。故比对前先核 config_hash8 + 三份输入产物指纹
  （nodes/questions/expected_sources）+ 索引目录与检索参数，任一不符判 incomparable，
  绝不把"换了输入"造成的差异记成"性能回归"。

用法:
  make regression                                  # 全部实验（模板 example_v1 除外）
  python scripts/run_regression.py --only struct_v1,struct_bm25
  python scripts/run_regression.py --changed-only  # 按 git 变更推断相关实验
  python scripts/run_regression.py --no-run        # 只比对已入库报告（不跑实验）
  python scripts/run_regression.py --promote       # 当前报告提为基准锚点（人工动作）

依赖: scripts/run_experiment.py · scripts/experiment_config.py（均为 D 域）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402
import run_experiment as rx  # noqa: E402

REGRESSION_SCHEMA = "rag4zrdds.regression/v1"
CONFIG_DIR = REPO_ROOT / "configs" / "experiments"
TEMPLATE_CONFIGS = {"example_v1"}          # 模板不是实验
BASELINE_DIRNAME = "baseline"              # reports/baseline/{name}.json = 人工提定的锚点
RUNS_DIRNAME = "runs"                      # reports/runs/{name}__{ts}.json = 历史归档

# §10 列举的变更类别 → 影响面。data_pipeline / retrieval / 产物目录 / D 的管线脚本
# 的任何改动都可能改变 Node 集、索引或报告口径，无法安全缩小范围，一律全量回归。
FULL_REGRESSION_PATHS = (
    "data_pipeline/", "retrieval/", "data/processed/", "requirements.txt", "scripts/",
)
# 判定器自身不是实验输入：改它不该触发全量回归。
SELF_EXEMPT_FILES = ("scripts/run_regression.py",)
# 只影响生成侧（本周 run_experiment 不产答案），回归矩阵暂不覆盖，提示后跳过。
GENERATION_PATHS = ("generation/",)


# ---------------------------------------------------------------- 实验发现


def discover_configs(only: list[str] | None = None) -> list[Path]:
    """列出参与回归的实验配置（按名字典序，确定性顺序便于比对两次回归运行）。"""
    all_paths = sorted(
        p for p in CONFIG_DIR.glob("*.yaml")
        if p.stem not in TEMPLATE_CONFIGS
    )
    if not only:
        return all_paths
    known = {p.stem: p for p in all_paths}
    picked: list[Path] = []
    unknown: list[str] = []
    for name in only:
        name = name.strip()
        if not name:
            continue
        if name in known:
            picked.append(known[name])
        else:
            unknown.append(name)
    if unknown:
        raise ValueError(
            f"未知实验名: {unknown}；可选 {sorted(known)}"
            "（模板 example_v1 不参与回归）"
        )
    return picked


def changed_paths(base: str = "origin/develop") -> list[str]:
    """工作区未提交改动 + 相对 base 的已提交改动，合并成受影响文件清单（仓库相对路径）。"""
    found: set[str] = set()
    for argv in (
        ["git", "diff", "--name-only", base],
        ["git", "diff", "--name-only", "HEAD"],
    ):
        try:
            out = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return []
        if out.returncode == 0:
            found.update(line.strip() for line in out.stdout.splitlines() if line.strip())
    return sorted(found)


def scope_from_changes(files: list[str]) -> tuple[str, list[str], list[str]]:
    """把变更文件映射成回归范围。

    返回 (scope, 实验名列表, 变更类别说明)；scope ∈ {"all","selected","none"}。
    判定宁可偏全（漏跑比多跑危险）。
    """
    touched_full = [f for f in files if f.startswith(FULL_REGRESSION_PATHS)
                    and f not in SELF_EXEMPT_FILES]
    touched_gen_only = [f for f in files
                        if f.startswith(GENERATION_PATHS) and not f.startswith(FULL_REGRESSION_PATHS)]
    configs = [f for f in files if f.startswith("configs/experiments/")
               and f.endswith(".yaml")]
    names = sorted({Path(c).stem for c in configs if Path(c).stem not in TEMPLATE_CONFIGS})

    notes: list[str] = []
    if touched_full:
        notes.append(f"分块/检索/产物有改动（{len(touched_full)} 文件）→ 全量回归")
    if names:
        notes.append(f"实验配置改动: {names}")
    if touched_gen_only:
        notes.append("生成侧改动不影响检索明细；answer_eval 通路接入前不纳入矩阵")

    if touched_full:
        return "all", [], notes
    if names:
        return "selected", names, notes
    if notes:
        return "none", [], notes
    return "none", [], ["改动文件不涉及任何实验输入（server/web/docs 等）→ 无需回归"]


# ---------------------------------------------------------------- 报告读取与比对


def load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[regression] 警告: 报告损坏 {path}: {e}", file=sys.stderr)
        return None


def _comparability(prev: dict, cur: dict) -> list[str]:
    """两份报告可否直接比较；返回不成立原因列表（空=可比）。"""
    reasons: list[str] = []
    pa, ca = prev.get("artifacts") or {}, cur.get("artifacts") or {}
    if not pa:
        reasons.append("基准报告无 artifacts 指纹（report/v1 旧版），无法证明同输入")
    if prev.get("config_hash8") != cur.get("config_hash8"):
        reasons.append(f"配置 hash8 变了（{prev.get('config_hash8')} → {cur.get('config_hash8')}）")
    if (prev.get("index") or {}).get("dirname") != (cur.get("index") or {}).get("dirname"):
        reasons.append("索引目录变了（重建/改身份段）")
    for section, fields in (
        ("retrieval", ("mode", "top_k")),
        ("dataset", ("questions", "expected_sources", "total")),
    ):
        ps, cs = prev.get(section) or {}, cur.get(section) or {}
        for f in fields:
            if ps.get(f) != cs.get(f):
                reasons.append(f"{section}.{f} 变了（{ps.get(f)} → {cs.get(f)}）")
    for key, label in (
        ("nodes_file_sha12", "Node 集产物"),
        ("questions_sha12", "问题集"),
        ("expected_sources_sha12", "标注集"),
    ):
        if pa and pa.get(key) != (ca.get(key) if ca else None):
            reasons.append(f"{label}指纹变了（{pa.get(key)} → {ca.get(key)}）")
    return reasons


def _topk_ids(entry: dict, k: int) -> list[str]:
    return [r.get("node_id") for r in (entry.get("retrieved") or [])[:k]]


def detail_delta(prev: dict, cur: dict, k: int) -> dict:
    """标注无关的稳定性信号：top-K 集合重合率、rank-1 一致率、空结果题数变化。

    重合率口径 = |A∩B| / max(|A|,|B|)（不是 Jaccard）：top_k=5 时换掉 1 条 = 0.8，
    正好落在默认阈值上不误报；换 2 条 = 0.6 才报警。改这个定义要同步改 --min-overlap。
    """
    prev_by = {e["id"]: e for e in prev.get("per_question") or [] if e.get("id")}
    cur_by = {e["id"]: e for e in cur.get("per_question") or [] if e.get("id")}
    common = sorted(set(prev_by) & set(cur_by))
    if not common:
        return {"comparable_questions": 0, "mean_overlap": None, "rank1_agreement": None,
                "empty_before": 0, "empty_after": 0}
    overlaps: list[float] = []
    rank1_same = 0
    for qid in common:
        a, b = _topk_ids(prev_by[qid], k), _topk_ids(cur_by[qid], k)
        if not a and not b:
            overlaps.append(1.0)
            continue
        overlaps.append(len(set(a) & set(b)) / max(len(a), len(b)))
        if a and b and a[0] == b[0]:
            rank1_same += 1
    return {
        "comparable_questions": len(common),
        "mean_overlap": round(sum(overlaps) / len(overlaps), 4),
        "rank1_agreement": round(rank1_same / len(common), 4),
        "empty_before": sum(1 for qid in common if not _topk_ids(prev_by[qid], k)),
        "empty_after": sum(1 for qid in common if not _topk_ids(cur_by[qid], k)),
    }


def metric_delta(prev: dict, cur: dict) -> dict[str, float]:
    pm, cm = prev.get("metrics") or {}, cur.get("metrics") or {}
    out: dict[str, float] = {}
    for m, v in cm.items():
        bv = pm.get(m)
        if v is not None and bv is not None:
            out[m] = round(v - bv, 4)
    return out


def compare_reports(prev: dict | None, cur: dict | None, *,
                    with_metrics: bool = False, metric_tol: float = 0.02,
                    min_overlap: float = 0.8) -> dict:
    """纯函数：两次报告 → 判定。verdict ∈ pass/warn/regression/incomparable/no_baseline。"""
    if cur is None:
        return {"verdict": "failed", "reasons": ["本轮报告缺失或损坏"]}
    if prev is None:
        return {"verdict": "no_baseline",
                "reasons": ["无历史报告可比对（首次运行，或用 --promote 提基准）"],
                "detail": None, "metrics": {}}

    k = (cur.get("retrieval") or {}).get("top_k") or 5
    reasons = _comparability(prev, cur)
    detail = detail_delta(prev, cur, k)
    deltas = metric_delta(prev, cur)
    result: dict = {
        "detail": detail,
        "metrics": deltas,
        "metric_channel": "on" if with_metrics else "muted",
        "incomparable_reasons": reasons,
    }
    if reasons:
        result["verdict"] = "incomparable"
        result["reasons"] = reasons + [
            "以下差异仅作记录，不判定回归：",
            f"  top-K 重合 {detail['mean_overlap']} / rank-1 一致 {detail['rank1_agreement']}",
        ]
        return result

    problems: list[str] = []
    warns: list[str] = []
    ov = detail["mean_overlap"]
    if ov is not None and ov < min_overlap:
        problems.append(f"top-K 命中集合重合率 {ov} < 阈值 {min_overlap}")
    if detail["empty_after"] > detail["empty_before"]:
        problems.append(
            f"空结果题数增加 {detail['empty_before']} → {detail['empty_after']}")

    if with_metrics:
        for m, d in deltas.items():
            if d < -metric_tol:
                problems.append(f"指标 {m} 下跌 {d}（超容差 {metric_tol}）")

    if detail["empty_after"] and not detail["empty_before"]:
        warns.append("出现新的空结果题")

    dur_p, dur_c = prev.get("duration_seconds"), cur.get("duration_seconds")
    if isinstance(dur_p, (int, float)) and isinstance(dur_c, (int, float)) \
            and dur_p >= 5 and dur_c > dur_p * 2:
        warns.append(f"耗时增长 {dur_p}s → {dur_c}s（>2x）")

    result["verdict"] = "regression" if problems else ("warn" if warns else "pass")
    result["reasons"] = problems or warns
    return result


# ---------------------------------------------------------------- 执行


def archive_prev_report(name: str, report: dict, runs_dir: Path) -> Path | None:
    """跑之前把旧报告归档，避免 run_experiment 覆盖式写入丢历史。"""
    ts = (report.get("generated_at") or "unknown").replace(":", "").replace("+", "")
    runs_dir.mkdir(parents=True, exist_ok=True)
    dst = runs_dir / f"{name}__{ts}.json"
    if dst.exists():
        return None
    dst.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return dst


def _compact_report(report: dict) -> dict:
    """基准锚点只留判定所需字段（整份报告 300KB+，八个实验会把仓库压垮）。"""
    return {
        "schema": "rag4zrdds.baseline/v1",
        "compact_from": report.get("schema"),
        "experiment": report.get("experiment"),
        "config_hash8": report.get("config_hash8"),
        "artifacts": report.get("artifacts") or {},
        "duration_seconds": report.get("duration_seconds"),
        "index": report.get("index") or {},
        "retrieval": report.get("retrieval") or {},
        "dataset": report.get("dataset") or {},
        "metrics": report.get("metrics") or {},
        "per_question": [
            {"id": e.get("id"),
             "retrieved": [{"node_id": r.get("node_id")}
                           for r in (e.get("retrieved") or [])]}
            for e in (report.get("per_question") or [])
        ],
    }


def promote_baseline(names: list[Path]) -> int:
    baseline_dir = REPO_ROOT / ec.load(str(names[0])).report.dir / BASELINE_DIRNAME
    baseline_dir.mkdir(parents=True, exist_ok=True)
    for p in names:
        cfg = ec.load(str(p))
        src = ec.report_path(cfg)
        if not src.exists():
            print(f"[regression] 跳过 {cfg.experiment.name}: 报告不存在，先跑一次再提基准")
            continue
        report = load_report(src)
        dst = baseline_dir / f"{cfg.experiment.name}.json"
        dst.write_text(
            json.dumps(_compact_report(report), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"[regression] 基准已更新 {cfg.experiment.name} → {dst.relative_to(REPO_ROOT)}"
              f"（紧凑锚点 {dst.stat().st_size // 1024}KB）")
    return 0


def _fmt_counts(counts: dict) -> str:
    parts = [f"{n} {verdict}" for verdict, n in
             sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return "，".join(parts) or "无实验"


def render_markdown(summary: dict) -> str:
    lines = [
        f"# 回归矩阵 {summary['started_at']}",
        "",
        f"- 范围: {summary['scope_note']}",
        f"- 通道: 明细（top-K 重合率阈值 {summary['thresholds']['min_overlap']}）"
        f"；指标 {'启用' if summary['with_metrics'] else '静默（标注未定版）'}",
        f"- 结论: **{summary['overall']}**（{_fmt_counts(summary['counts'])}）",
        "",
        "| 实验 | 判定 | top-K 重合 | rank-1 一致 | 指标 delta | 耗时 s | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in summary["results"]:
        d = r.get("detail") or {}
        met = r.get("metrics") or {}
        met_s = " ".join(f"{m}={v:+.4f}" for m, v in met.items()) or "n/a"
        reasons = "; ".join(r.get("reasons") or []) or "—"
        lines.append(
            f"| {r['experiment']} | {r['verdict']} | {d.get('mean_overlap', 'n/a')} "
            f"| {d.get('rank1_agreement', 'n/a')} | {met_s} "
            f"| {r.get('duration_seconds', 'n/a')} | {reasons} |"
        )
    lines += ["", "> 由 `scripts/run_regression.py` 生成（指南 §10）。"
              "incomparable=输入已变，差异不作回归判定；regression/failed 使退出码非 0。"]
    return "\n".join(lines) + "\n"


def _rel(path: Path) -> str:
    """仓库相对路径显示；REPO_ROOT 被重定向（单测 tmp_path）时退回原始路径。"""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):      # Windows GBK 控制台
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="run_regression", description=__doc__)
    parser.add_argument("--only", default=None, help="逗号分隔实验名，默认全部（模板除外）")
    parser.add_argument("--changed-only", action="store_true",
                        help="按 git 变更（相对 origin/develop + 工作区）推断回归范围")
    parser.add_argument("--base", default="origin/develop", help="--changed-only 的对比基线")
    parser.add_argument("--no-run", action="store_true",
                        help="不跑实验，只比对现有报告与历史/基准")
    parser.add_argument("--promote", action="store_true",
                        help="把当前报告提为基准锚点（reports/baseline/）")
    parser.add_argument("--with-metrics", action="store_true",
                        help="启用指标闸门（真值标注定版后再开）")
    parser.add_argument("--metric-tol", type=float, default=0.02,
                        help="指标下跌幅度容差，默认 0.02")
    parser.add_argument("--min-overlap", type=float, default=0.8,
                        help="top-K 集合重合率下限，默认 0.8")
    args = parser.parse_args(argv)

    only = args.only.split(",") if args.only else None

    if args.changed_only and only:
        print("[regression] 错误: --changed-only 与 --only 互斥", file=sys.stderr)
        return 2

    notes: list[str] = []
    if args.changed_only:
        files = changed_paths(args.base)
        scope, names, notes = scope_from_changes(files)
        if scope == "none":
            print("[regression] " + "；".join(notes))
            return 0
        try:
            configs = discover_configs(names if scope == "selected" else None)
        except ValueError as e:
            print(f"[regression] 错误: {e}", file=sys.stderr)
            return 2
        notes.append("按 git 变更推断范围")
    else:
        try:
            configs = discover_configs(only)
        except ValueError as e:
            print(f"[regression] 错误: {e}", file=sys.stderr)
            return 2
        notes.append("全量" if not only else f"指定 {len(configs)} 个实验")

    if not configs:
        print("[regression] 错误: 没有匹配的实验配置", file=sys.stderr)
        return 2

    if args.promote:
        return promote_baseline(configs)

    print(f"[regression] 回归 {len(configs)} 个实验: "
          f"{[p.stem for p in configs]}")
    print(f"[regression] 通道: 明细阈值 top-K 重合 ≥{args.min_overlap}"
          f"；指标闸门 {'开' if args.with_metrics else '关（标注未定版）'}")

    results: list[dict] = []
    for p in configs:
        name = p.stem
        try:
            cfg = ec.load(str(p))
        except ec.ConfigError as e:
            results.append({"experiment": name, "verdict": "failed",
                            "reasons": [f"配置无效: {e}"]})
            continue
        report_path = ec.report_path(cfg)
        baseline_path = report_path.parent / BASELINE_DIRNAME / f"{name}.json"
        runs_dir = report_path.parent / RUNS_DIRNAME

        prev = load_report(report_path)
        if prev and not args.no_run:
            archive_prev_report(name, prev, runs_dir)

        if not args.no_run:
            print(f"[regression] ▶ {name}: 运行实验 …")
            rc = rx.main(["--config", str(p)])
            if rc != 0:
                results.append({"experiment": name, "verdict": "failed",
                                "reasons": [f"run_experiment 退出码 {rc}"]})
                continue
        cur = load_report(report_path)
        if cur is None:
            verdict = "missing" if args.no_run else "failed"
            reason = ("报告不存在（--no-run 模式未跑实验，无历史可比）"
                      if args.no_run else "实验跑完却没有落盘报告")
            results.append({"experiment": name, "verdict": verdict,
                            "config": _rel(p),
                            "detail": None, "metrics": {}, "reasons": [reason]})
            print(f"[regression]   {name} → {verdict}（{reason}）")
            continue
        vs_prev = compare_reports(prev, cur, with_metrics=args.with_metrics,
                                  metric_tol=args.metric_tol,
                                  min_overlap=args.min_overlap)
        base_report = load_report(baseline_path)
        vs_base = compare_reports(base_report, cur, with_metrics=args.with_metrics,
                                  metric_tol=args.metric_tol,
                                  min_overlap=args.min_overlap) \
            if base_report else None

        entry = {
            "experiment": name,
            "config": _rel(p),
            "verdict": _worst(vs_prev["verdict"], (vs_base or {}).get("verdict")),
            "duration_seconds": (cur or {}).get("duration_seconds"),
            "detail": vs_prev.get("detail"),
            "metrics": vs_prev.get("metrics") or {},
            "reasons": (vs_prev.get("reasons") or []),
            "vs_previous": {kk: vs_prev[kk] for kk in
                            ("verdict", "detail", "metrics", "incomparable_reasons")
                            if kk in vs_prev},
            "vs_baseline": ({"verdict": vs_base["verdict"],
                             "detail": vs_base.get("detail"),
                             "metrics": vs_base.get("metrics"),
                             "incomparable_reasons": vs_base.get("incomparable_reasons")}
                            if vs_base else None),
        }
        results.append(entry)
        tail = f" / vs 基准 {vs_base['verdict']}" if vs_base else ""
        print(f"[regression]   {name} → {entry['verdict']}"
              f"（vs 上次 {vs_prev['verdict']}{tail}）")

    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    bad = sum(counts.get(v, 0) for v in ("regression", "failed"))
    if bad:
        overall = "FAIL"
    elif counts.get("incomparable") or counts.get("warn") or counts.get("no_baseline") \
            or counts.get("missing"):
        overall = "REVIEW"
    else:
        overall = "PASS"
    summary = {
        "schema": REGRESSION_SCHEMA,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scope_note": "；".join(notes),
        "with_metrics": args.with_metrics,
        "thresholds": {"min_overlap": args.min_overlap, "metric_tol": args.metric_tol},
        "counts": counts,
        "overall": overall,
        "results": results,
    }

    reports_dir = REPO_ROOT / (ec.load(str(configs[0])).report.dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = summary["started_at"].replace(":", "").replace("+", "")
    (reports_dir / f"regression_{ts}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (reports_dir / "regression_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (reports_dir / "regression_latest.md").write_text(
        render_markdown(summary), encoding="utf-8")

    print(f"[regression] 结论 {overall} {counts}")
    print(f"[regression] 报告 → {_rel(reports_dir / 'regression_latest.md')}")
    return 1 if bad else 0


def _worst(a: str, b: str | None) -> str:
    order = {"failed": 5, "regression": 4, "incomparable": 3, "warn": 2,
             "no_baseline": 1, "missing": 1, "pass": 0, None: 0}
    return a if order.get(a, 0) >= order.get(b, 0) else (b or a)


if __name__ == "__main__":
    raise SystemExit(main())
