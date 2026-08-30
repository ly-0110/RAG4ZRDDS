#!/usr/bin/env python3
"""
scripts/run_experiment.py — 实验流水线门面（成员 D · 第二周核心交付，指南 §6）

职责：读实验配置 → 保障索引就绪 → 跑统一评测集 → 指标计算 → 报告落盘
    evaluation/reports/{experiment.name}.json（§10 回归机制的载体）。

铁律（指南 §6.2 / configs/experiments/README.md）：
  * 实验变量只经由 configs/experiments/*.yaml 切换，禁止改代码换实验
  * 报告落点、索引目录、Node 集路径全部由 experiment_config 派生命名

索引策略：
  * 目标索引（{method}_{embed}_{hash8}）不存在 → 自动构建（等价 make index）
  * 已存在 → 直接复用（hash8 = 配置内容哈希，同目录必然同配置，复用语义安全）
  * --rebuild 强制重建（先删后建，语义同 build_index）

评测口径（占位，待成员 C 会签定版）：
  * 判对 = expected_sources.jsonl 中该题的任一期望记录与检索结果匹配
    （来源 id / 印刷页区间 / 章节关键词，非空条件需同时满足）
  * hit_rate@K / mrr@K / precision@K / recall@K 为经典 IR 定义
  * response_metrics 非空时报可读错误——生成侧评测待 C 的 judges 落地

用法:
  make experiment                                # 默认配置（struct_v1 基线）
  python scripts/run_experiment.py --config configs/experiments/<实验>.yaml
  python scripts/run_experiment.py --config ... --rebuild --sample 10

依赖: scripts/experiment_config.py · scripts/build_index.py · retrieval/*（B）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402

REPORT_SCHEMA = "rag4zrdds.report/v1"


# ---------------------------------------------------------------- 数据集


def load_questions(path: Path, sample_size: int | None) -> list[dict]:
    """读问题集 jsonl（指南 6.1 字段：id / question / type / version / difficulty）。"""
    if not path.exists():
        raise FileNotFoundError(
            f"评测问题集不存在: {path}\n"
            "  正式问题集由成员 E 编写（80~120 题，指南 §6.1）；"
            "占位集见 evaluation/datasets/README.md。"
        )
    questions: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if not rec.get("id") or not rec.get("question"):
                raise ValueError(f"{path} 第 {lineno} 行缺少必填字段 id / question")
            questions.append(rec)
    if sample_size is not None:
        questions = questions[:sample_size]  # 确定性取前 N，冒烟用
    if not questions:
        raise ValueError(f"评测问题集为空: {path}")
    return questions


def load_expected_sources(path: Path) -> dict[str, list[dict]]:
    """读期望来源标注，按 question_id 分组。

    每行格式（占位口径，见 evaluation/datasets/README.md）：
      {"question_id": str, "source_id"?: str,
       "page_print"?: int | [lo, hi], "section_keyword"?: str}
    条件至少给出一个；非空条件需同时满足才算命中。
    """
    if not path.exists():
        return {}
    grouped: dict[str, list[dict]] = {}
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qid = rec.get("question_id")
            if not qid:
                raise ValueError(f"{path} 第 {lineno} 行缺少 question_id")
            if not any(rec.get(k) for k in ("source_id", "page_print", "section_keyword")):
                raise ValueError(
                    f"{path} 第 {lineno} 行（{qid}）未给出任何匹配条件"
                    "（source_id / page_print / section_keyword 至少一个）"
                )
            grouped.setdefault(qid, []).append(rec)
    return grouped


# ---------------------------------------------------------------- 匹配与指标（占位口径）


def _page_in_range(page: int | None, spec) -> bool:
    if page is None:
        return False
    if isinstance(spec, int):
        return page == spec
    lo, hi = spec
    return lo <= page <= hi


def matches_expected(ref: dict, expected: dict) -> bool:
    """单条检索结果是否满足一条期望记录（非空条件全部成立）。"""
    sid = expected.get("source_id")
    if sid and ref.get("source_id") != sid:
        return False
    page_spec = expected.get("page_print")
    if page_spec is not None and not _page_in_range(ref.get("page_print"), page_spec):
        return False
    keyword = expected.get("section_keyword")
    if keyword and keyword not in (ref.get("section") or ""):
        return False
    return True


def parse_metric(name: str) -> tuple[str, int]:
    """'hit_rate@5' → ('hit_rate', 5)。配置层已校验格式，这里只做拆分。"""
    kind, _, k = name.rpartition("@")
    return kind, int(k)


def question_metric_values(retrieved: list[dict], expected_list: list[dict],
                           metric_name: str) -> float:
    """单题单指标取值；经典 IR 定义，K 截断后计算。"""
    kind, k = parse_metric(metric_name)
    topk = retrieved[:k]
    n_exp = len(expected_list)
    if kind == "hit_rate":
        return 1.0 if any(matches_expected(r, e) for r in topk for e in expected_list) else 0.0
    if kind == "mrr":
        for rank, r in enumerate(topk, start=1):
            if any(matches_expected(r, e) for e in expected_list):
                return 1.0 / rank
        return 0.0
    if kind == "precision":
        if not topk:
            return 0.0
        hits = sum(1 for r in topk if any(matches_expected(r, e) for e in expected_list))
        return hits / len(topk)
    if kind == "recall":
        if n_exp == 0:
            return 0.0
        matched = sum(1 for e in expected_list
                      if any(matches_expected(r, e) for r in topk))
        return matched / n_exp
    raise ValueError(f"未实现的检索指标: {kind}（支持 hit_rate / mrr / precision / recall）")


# ---------------------------------------------------------------- 检索执行


async def _run_queries(retriever, questions: list[dict], top_k: int) -> dict[str, list[dict]]:
    """顺序执行（CPU 单用户演示口径）；保持确定性顺序便于复现与排错。"""
    results: dict[str, list[dict]] = {}
    for q in questions:
        refs = await retriever.retrieve(q["question"], top_k)
        results[q["id"]] = refs
        print(f"[experiment]   检索 {q['id']} → {len(refs)} 条引用", flush=True)
    return results


# ---------------------------------------------------------------- 报告


def build_report(cfg, retrievals: dict[str, list[dict]], questions: list[dict],
                 expected: dict[str, list[dict]], metrics: list[str],
                 elapsed: float, fake_embed: bool) -> dict:
    per_question: list[dict] = []
    evaluated: list[str] = []
    skipped: list[str] = []
    for q in questions:
        refs = retrievals[q["id"]]
        exp_list = expected.get(q["id"], [])
        entry = {
            "id": q["id"],
            "question": q["question"],
            "retrieved": refs,
        }
        if exp_list:
            entry["metric_values"] = {
                m: question_metric_values(refs, exp_list, m) for m in metrics
            }
            entry["expected"] = exp_list
            evaluated.append(q["id"])
        else:
            entry["note"] = "无期望来源标注（不计入指标分母）"
            skipped.append(q["id"])
        per_question.append(entry)

    agg = {
        m: (round(sum(e["metric_values"][m] for e in per_question
                      if e["id"] in evaluated) / len(evaluated), 4)
            if evaluated else None)
        for m in metrics
    }

    report = {
        "schema": REPORT_SCHEMA,
        "experiment": cfg.experiment.name,
        "stage": cfg.experiment.stage,
        "config_hash8": ec.config_hash8(cfg),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duration_seconds": round(elapsed, 1),
        "index": {
            "dirname": ec.index_dirname(cfg),
            "backend": cfg.index.backend,
            "metric": cfg.index.metric,
        },
        "retrieval": {"mode": cfg.retrieval.mode, "top_k": cfg.retrieval.top_k},
        "dataset": {
            "questions": cfg.evaluation.dataset,
            "expected_sources": cfg.evaluation.expected_sources,
            "total": len(questions),
            "evaluated": len(evaluated),
            "skipped_no_expected": skipped,
        },
        "metrics": agg,
        "per_question": per_question,
        "compare_baseline": _compare_baseline(cfg, agg),
        "notes": [
            "评测口径为占位：页码按印刷页匹配（印刷页 = 物理页 − 6），"
            "最终判对口径待成员 C 定版（指南 §6 任务分解）。",
        ],
    }
    if fake_embed:
        report["notes"].append("fake-embed 结构冒烟：向量无语义，指标数值无意义。")
    if not expected:
        report["notes"].append(
            "本次无期望来源标注（expected_sources 缺失）：仅记录检索结果，指标为空；"
            "正式标注由成员 E 随问题集交付、成员 C 定口径（见 evaluation/datasets/README.md）。"
        )
    return report


def _compare_baseline(cfg, agg: dict[str, float | None]) -> dict | None:
    """report.compare_baseline 指定基准报告时输出指标差值（回归对比，§10）。"""
    name = cfg.report.compare_baseline
    if not name:
        return None
    base_path = REPO_ROOT / cfg.report.dir / name
    if not base_path.exists():
        print(f"[experiment] 警告：基准报告不存在，跳过对比: {base_path}", file=sys.stderr)
        return None
    try:
        base = json.loads(base_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[experiment] 警告：基准报告损坏（{e}），跳过对比", file=sys.stderr)
        return None
    base_metrics = base.get("metrics", {})
    delta = {}
    for m, v in agg.items():
        bv = base_metrics.get(m)
        if v is not None and bv is not None:
            delta[m] = round(v - bv, 4)
    return {"baseline": name, "delta": delta}


def write_report(cfg, report: dict) -> Path:
    path = ec.report_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------- 主流程


def _read_manifest_fake_flag(target: Path) -> bool | None:
    """既有索引的 manifest 中 fake_embed 标记；无 manifest 返回 None。"""
    m = target / "manifest.json"
    if not m.exists():
        return None
    try:
        return bool(json.loads(m.read_text(encoding="utf-8")).get("fake_embed"))
    except json.JSONDecodeError:
        return None


def _ensure_index(config_path: str, cfg, rebuild: bool, fake_embed: bool) -> int:
    """索引不存在 → 自动构建；已存在 → 复用（hash8 保证同目录同配置）。

    防误毁：fake-embed 冒烟与真实索引共用同一派生目录，
    目标已是真实索引时拒绝 fake 重建（反之：真实构建可覆盖遗留 fake 索引）。
    """
    import build_index as bi

    target = ec.index_dir(cfg)
    if target.exists():
        was_fake = _read_manifest_fake_flag(target)
        if fake_embed and was_fake is False:
            print(
                f"[experiment] 错误: 目标索引 {target.relative_to(REPO_ROOT)} 是真实索引，"
                "--fake-embed 冒烟会将其覆盖为假向量。请改用专门的冒烟实验配置"
                "（另一个文件名 → 另一个派生目录），或手动删除该索引后重试。",
                file=sys.stderr,
            )
            return 1
        if not rebuild and not (fake_embed != (was_fake if was_fake is not None else fake_embed)):
            print(f"[experiment] 索引已存在，复用: {target.relative_to(REPO_ROOT)}"
                  f"（--rebuild 可强制重建）")
            return 0
        reason = "--rebuild 强制重建" if rebuild else "既有索引为 fake/无 manifest，重建为真实索引"
        print(f"[experiment] {reason} → 委托 build_index")
    else:
        print("[experiment] 索引不存在，自动构建 → 委托 build_index")
    argv = ["--config", config_path]
    if fake_embed:
        argv.append("--fake-embed")
    return bi.main(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，统一 UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="run_experiment", description=__doc__)
    parser.add_argument("--config", default="configs/experiments/struct_v1.yaml",
                        help="实验配置 yaml（默认 struct_v1 基线）")
    parser.add_argument("--rebuild", action="store_true",
                        help="强制重建索引（默认：存在即复用，缺失才构建）")
    parser.add_argument("--fake-embed", action="store_true",
                        help="确定性假向量只验结构（无模型环境冒烟，指标无意义）")
    parser.add_argument("--sample", type=int, default=None,
                        help="覆盖 evaluation.sample_size：只评前 N 题（冒烟用）")
    args = parser.parse_args(argv)

    try:
        cfg = ec.load(args.config)
    except ec.ConfigError as e:
        print(f"[experiment] 配置无效：\n{e}", file=sys.stderr)
        return 1

    if cfg.evaluation.response_metrics:
        print(
            "[experiment] response_metrics 评测暂未接入："
            "生成侧判分（Faithfulness / Answer Relevance）待成员 C 的 judges 落地"
            "（指南 §6 任务分解）。请先将 response_metrics 置空。",
            file=sys.stderr,
        )
        return 1

    nodes_file = ec.nodes_path(cfg)
    if not nodes_file.exists():
        print(f"[experiment] 错误: Node 集不存在 {nodes_file}（先运行 make ingest）",
              file=sys.stderr)
        return 1

    try:
        questions = load_questions(REPO_ROOT / cfg.evaluation.dataset, args.sample)
    except (FileNotFoundError, ValueError) as e:
        print(f"[experiment] 错误: {e}", file=sys.stderr)
        return 1
    expected = load_expected_sources(REPO_ROOT / cfg.evaluation.expected_sources)
    if not expected:
        print(f"[experiment] 警告: 期望来源标注不存在 {cfg.evaluation.expected_sources}"
              "——本次只记录检索结果，不计算指标。", file=sys.stderr)

    print(f"[experiment] 实验={cfg.experiment.name} hash8={ec.config_hash8(cfg)}"
          f" 问题={len(questions)} 指标={cfg.evaluation.retrieval_metrics}")

    if _ensure_index(args.config, cfg, args.rebuild, args.fake_embed) != 0:
        return 1

    from retrieval.retriever import build_retriever

    t0 = time.monotonic()
    embed_fn = None
    if args.fake_embed:
        from build_index import _fake_embed
        embed_fn = _fake_embed
    retriever = build_retriever(cfg, embed_fn=embed_fn)

    print(f"[experiment] 开始检索（top_k={cfg.retrieval.top_k}）…")
    retrievals = asyncio.run(_run_queries(retriever, questions, cfg.retrieval.top_k))
    elapsed = time.monotonic() - t0

    metrics = cfg.evaluation.retrieval_metrics
    report = build_report(cfg, retrievals, questions, expected, metrics,
                          elapsed, args.fake_embed)
    path = write_report(cfg, report)

    print(f"[experiment] ✓ 完成，耗时 {elapsed:.1f}s")
    for m, v in report["metrics"].items():
        shown = f"{v:.4f}" if v is not None else "n/a（无标注题）"
        print(f"[experiment]   {m:<14} = {shown}")
    if report["dataset"]["skipped_no_expected"]:
        print(f"[experiment]   跳过（无标注）: {report['dataset']['skipped_no_expected']}")
    if report["compare_baseline"]:
        print(f"[experiment]   基准对比: {report['compare_baseline']}")
    print(f"[experiment] 报告 → {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
