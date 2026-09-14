"""scripts/run_regression.py 单元测试（指南 §10 回归机制）。

只测判定逻辑（可比性闸门 / 明细通道 / 指标闸门 / 变更→范围映射 / 实验发现），
不跑真实索引与 embedding；端到端由 `make regression` 实测覆盖。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402
import run_experiment as rx  # noqa: E402
import run_regression as rr  # noqa: E402


def _artifacts(nodes="nodefp", questions="qfp", expected="efp") -> dict:
    return {
        "nodes_file_sha12": nodes,
        "questions_sha12": questions,
        "expected_sources_sha12": expected,
    }


def _report(*, hash8="aaaa1111", artifacts=None, pages=None, metrics=None,
            dirname="struct_bge-m3_aaaa1112", top_k=5, total=2, duration=10.0,
            schema=rx.REPORT_SCHEMA) -> dict:
    """两题的极小报告；pages = {"Q001": ["n1", "n2"], ...}。"""
    pages = pages if pages is not None else {"Q001": ["n1", "n2"], "Q002": ["n3", "n4"]}
    return {
        "schema": schema,
        "experiment": "demo",
        "config_hash8": hash8,
        "artifacts": _artifacts() if artifacts is None else artifacts,
        "duration_seconds": duration,
        "index": {"dirname": dirname},
        "retrieval": {"mode": "vector", "top_k": top_k},
        "dataset": {"questions": "q.jsonl", "expected_sources": "e.jsonl",
                    "total": total, "evaluated": total},
        "metrics": metrics if metrics is not None else {"hit_rate@5": 0.6, "mrr@5": 0.4},
        "per_question": [
            {"id": qid, "retrieved": [{"node_id": n} for n in ids]}
            for qid, ids in sorted(pages.items())
        ],
    }


# ---------------------------------------------------------------- 可比性闸门


class TestComparabilityGate:
    def test_identical_inputs_are_comparable(self):
        assert rr.compare_reports(_report(), _report())["verdict"] == "pass"

    def test_node_artifact_change_blocks_verdict_even_with_same_config(self):
        """R1/R4 防线：配置 hash8 未变但磁盘产物被换 → 判不可比，不判回归。"""
        prev = _report()
        cur = _report(artifacts=_artifacts(nodes="OTHER"))
        out = rr.compare_reports(prev, cur, min_overlap=0.99)
        assert out["verdict"] == "incomparable"
        assert any("Node 集产物指纹变了" in r for r in out["incomparable_reasons"])

    def test_annotation_change_blocks_verdict(self):
        """标注换版会让指标跳变，但那不是检索回归。"""
        cur = _report(artifacts=_artifacts(expected="NEW"),
                      metrics={"hit_rate@5": 0.05, "mrr@5": 0.02})
        out = rr.compare_reports(_report(), cur, with_metrics=True)
        assert out["verdict"] == "incomparable"
        assert any("标注集指纹变了" in r for r in out["incomparable_reasons"])

    def test_config_hash_change_detected(self):
        out = rr.compare_reports(_report(), _report(hash8="bbbb2222"))
        assert out["verdict"] == "incomparable"
        assert any("配置 hash8" in r for r in out["incomparable_reasons"])

    def test_legacy_v1_report_without_artifacts_is_incomparable(self):
        prev = _report(schema="rag4zrdds.report/v1")
        prev["artifacts"] = {}
        out = rr.compare_reports(prev, _report())
        assert out["verdict"] == "incomparable"
        assert any("无 artifacts 指纹" in r for r in out["incomparable_reasons"])

    def test_topk_or_dataset_change_detected(self):
        out = rr.compare_reports(_report(), _report(top_k=3))
        assert out["verdict"] == "incomparable"
        assert any("retrieval.top_k" in r for r in out["incomparable_reasons"])


# ---------------------------------------------------------------- 明细通道


class TestDetailChannel:
    def test_perfect_repeat_passes(self):
        out = rr.compare_reports(_report(), _report())
        assert out["detail"]["mean_overlap"] == 1.0
        assert out["detail"]["rank1_agreement"] == 1.0
        assert out["verdict"] == "pass"

    def test_total_ranking_flip_is_regression(self):
        cur = _report(pages={"Q001": ["x1", "x2"], "Q002": ["x3", "x4"]})
        out = rr.compare_reports(_report(), cur)
        assert out["detail"]["mean_overlap"] == 0.0
        assert out["verdict"] == "regression"

    def test_single_swap_of_five_sits_on_threshold_and_passes(self):
        """重合系数 = 交集 / 较长列表；top_k=5 换 1 条 = 0.8，恰好等于阈值 → 不误报。"""
        prev = _report(pages={"Q001": ["n1", "n2", "n3", "n4", "n5"]})
        cur = _report(pages={"Q001": ["n1", "n2", "n3", "n4", "x9"]})
        out = rr.compare_reports(prev, cur)
        assert out["detail"]["mean_overlap"] == 0.8
        assert out["verdict"] == "pass"

    def test_two_swaps_of_five_break_threshold(self):
        prev = _report(pages={"Q001": ["n1", "n2", "n3", "n4", "n5"]})
        cur = _report(pages={"Q001": ["n1", "n2", "n3", "x8", "x9"]})
        out = rr.compare_reports(prev, cur)
        assert out["detail"]["mean_overlap"] == 0.6
        assert out["verdict"] == "regression"

    def test_new_empty_results_are_flagged(self):
        cur = _report(pages={"Q001": [], "Q002": ["n3", "n4"]})
        out = rr.compare_reports(_report(), cur)
        assert out["verdict"] == "regression"
        assert any("空结果题数增加" in r for r in out["reasons"])

    def test_missing_previous_report_is_no_baseline(self):
        assert rr.compare_reports(None, _report())["verdict"] == "no_baseline"

    def test_missing_current_report_is_failure(self):
        assert rr.compare_reports(_report(), None)["verdict"] == "failed"

    def test_slowdown_warns_without_failing(self):
        out = rr.compare_reports(_report(duration=10.0), _report(duration=90.0))
        assert out["verdict"] == "warn"
        assert any("耗时增长" in r for r in out["reasons"])


# ---------------------------------------------------------------- 指标闸门


class TestMetricGate:
    def test_metric_drop_is_muted_by_default(self):
        """标注未定版：指标只记录不判定（宁缺毋滥）。"""
        cur = _report(metrics={"hit_rate@5": 0.1, "mrr@5": 0.05})
        out = rr.compare_reports(_report(), cur)
        assert out["metric_channel"] == "muted"
        assert out["metrics"]["hit_rate@5"] == pytest.approx(-0.5)
        assert out["verdict"] == "pass"

    def test_metric_drop_flags_when_enabled(self):
        cur = _report(metrics={"hit_rate@5": 0.55, "mrr@5": 0.4})
        out = rr.compare_reports(_report(), cur, with_metrics=True, metric_tol=0.02)
        assert out["verdict"] == "regression"
        assert any("hit_rate@5 下跌" in r for r in out["reasons"])

    def test_within_tolerance_passes_when_enabled(self):
        cur = _report(metrics={"hit_rate@5": 0.59, "mrr@5": 0.4})
        assert rr.compare_reports(_report(), cur, with_metrics=True)["verdict"] == "pass"

    def test_null_metrics_are_skipped(self):
        cur = _report(metrics={"hit_rate@5": None})
        assert rr.compare_reports(_report(), cur, with_metrics=True)["metrics"] == {}


# ---------------------------------------------------------------- 变更 → 范围


class TestScopeFromChanges:
    def test_chunking_change_forces_full(self):
        scope, names, notes = rr.scope_from_changes(["data_pipeline/chunkers/semantic.py"])
        assert scope == "all" and names == [] and notes

    def test_retrieval_change_forces_full(self):
        assert rr.scope_from_changes(["retrieval/bm25.py"])[0] == "all"

    def test_platform_script_change_forces_full(self):
        assert rr.scope_from_changes(["scripts/build_index.py"])[0] == "all"

    def test_regression_tool_self_change_is_exempt(self):
        scope, _, notes = rr.scope_from_changes(["scripts/run_regression.py"])
        assert scope == "none"
        assert any("无需回归" in n for n in notes)

    def test_config_change_selects_that_experiment(self):
        scope, names, _ = rr.scope_from_changes(
            ["configs/experiments/struct_bm25.yaml"])
        assert (scope, names) == ("selected", ["struct_bm25"])

    def test_template_config_does_not_select_anything(self):
        assert rr.scope_from_changes(["configs/experiments/example_v1.yaml"])[0] == "none"

    def test_generation_only_change_is_reported_not_run(self):
        scope, _, notes = rr.scope_from_changes(["generation/prompts/v2.md"])
        assert scope == "none"
        assert any("生成侧" in n for n in notes)

    def test_unrelated_docs(self):
        assert rr.scope_from_changes(["docs/api.md"])[0] == "none"


# ---------------------------------------------------------------- 实验发现


class TestDiscoverConfigs:
    def test_template_excluded_and_real_experiments_present(self):
        names = {p.stem for p in rr.discover_configs()}
        assert "example_v1" not in names
        assert {"struct_v1", "struct_bm25", "struct_multisrc_v1"} <= names

    def test_only_selection_and_unknown_name_error(self):
        picked = rr.discover_configs(["struct_v1"])
        assert [p.stem for p in picked] == ["struct_v1"]
        with pytest.raises(ValueError, match="未知实验名"):
            rr.discover_configs(["no_such_experiment"])

    def test_cli_rejects_conflicting_selection(self):
        assert rr.main(["--only", "struct_v1", "--changed-only"]) == 2

    def test_cli_unknown_experiment_exits_with_readable_error(self, capsys):
        assert rr.main(["--only", "nope"]) == 2
        assert "未知实验名" in capsys.readouterr().err


# ---------------------------------------------------------------- 报告指纹落盘


class TestReportArtifacts:
    def test_build_report_carries_artifacts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
        cfg = ec.load(REPO_ROOT / "configs" / "experiments" / "struct_v1.yaml")
        report = rx.build_report(
            cfg, {"Q1": []}, [{"id": "Q1", "question": "x"}], {},
            ["hit_rate@5"], 0.1, fake_embed=False,
            artifacts=_artifacts(nodes="deadbeef0000"))
        assert report["schema"] == "rag4zrdds.report/v1.1"
        assert report["artifacts"]["nodes_file_sha12"] == "deadbeef0000"

    def test_artifact_fingerprints_missing_files_give_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(rx, "REPO_ROOT", tmp_path)
        cfg = ec.load(REPO_ROOT / "configs" / "experiments" / "struct_v1.yaml")
        fp = rx._artifact_fingerprints(cfg)
        assert fp == {"nodes_file_sha12": None, "questions_sha12": None,
                      "expected_sources_sha12": None}

    def test_sha12_is_normalized_across_crlf(self, tmp_path):
        import build_index as bi

        crlf = tmp_path / "a.jsonl"
        lf = tmp_path / "b.jsonl"
        crlf.write_bytes(b'{"x": 1}\r\n{"y": 2}\r\n')
        lf.write_bytes(b'{"x": 1}\n{"y": 2}\n')
        assert bi.sha12_file(crlf) == bi.sha12_file(lf)
        assert bi.sha12_file(tmp_path / "missing.jsonl") is None


def test_compact_baseline_stays_comparable():
    """--promote 写的是紧凑锚点，比对必须照常成立（否则基准形同虚设）。"""
    full = _report(pages={"Q001": ["n1", "n2", "n3", "n4", "n5"]})
    compact = rr._compact_report(full)
    assert compact["schema"] == "rag4zrdds.baseline/v1"
    assert compact["per_question"][0]["retrieved"][0] == {"node_id": "n1"}
    assert all(set(e) == {"id", "retrieved"} for e in compact["per_question"])
    full = dict(full, per_question=[dict(e, question="题干原文", expected=[{"page_print": 1}])
                                    for e in full["per_question"]])
    compact = rr._compact_report(full)
    assert all("question" not in e and "expected" not in e
               for e in compact["per_question"])
    cur = _report(pages={"Q001": ["n1", "n2", "n3", "n4", "x9"]})
    assert rr.compare_reports(compact, cur)["verdict"] == "pass"


def test_main_flags_regression_and_writes_matrix(tmp_path, monkeypatch):
    cfg_path = rr.CONFIG_DIR / "struct_bm25.yaml"
    monkeypatch.setattr(rr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    reports_dir = tmp_path / "evaluation" / "reports"
    reports_dir.mkdir(parents=True)
    monkeypatch.setattr(rr, "discover_configs", lambda only=None: [cfg_path])
    prev = _report(pages={"Q001": ["a1", "a2", "a3", "a4", "a5"]})
    cur = _report(pages={"Q001": ["b1", "b2", "b3", "b4", "b5"]})
    reads = iter([prev, cur, None])
    monkeypatch.setattr(rr, "load_report", lambda path: next(reads, None))

    assert rr.main(["--only", "struct_bm25", "--no-run"]) == 1
    summary = json.loads((reports_dir / "regression_latest.json").read_text(encoding="utf-8"))
    assert summary["overall"] == "FAIL"
    assert summary["counts"] == {"regression": 1}
    assert summary["results"][0]["detail"]["mean_overlap"] == 0.0
    assert (reports_dir / "regression_latest.md").exists()


def test_regression_markdown_renders():
    summary = {
        "started_at": "2026-09-14T09:00:00+0800",
        "scope_note": "全量",
        "with_metrics": False,
        "thresholds": {"min_overlap": 0.8, "metric_tol": 0.02},
        "counts": {"pass": 1},
        "overall": "PASS",
        "results": [{"experiment": "struct_v1", "verdict": "pass",
                     "detail": {"mean_overlap": 1.0, "rank1_agreement": 1.0},
                     "metrics": {}, "duration_seconds": 9.5, "reasons": []}],
    }
    md = rr.render_markdown(summary)
    assert "struct_v1" in md and "PASS" in md and "| 实验 | 判定 |" in md
