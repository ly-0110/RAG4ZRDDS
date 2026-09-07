"""scripts/run_experiment.py 单元测试。

只测纯逻辑（匹配口径 / 指标 / 数据集加载 / 报告组装），不触碰
真实索引、embedding 与 chromadb；端到端由 `make experiment` 实测覆盖。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402
import run_experiment as rx  # noqa: E402


def _ref(node_id="n1", page=245, section="18.1 简化接口", sid="user_manual", score=0.9):
    return {
        "node_id": node_id,
        "source_id": sid,
        "source_name": "ZRDDS用户手册.pdf",
        "section": section,
        "page_print": page,
        "page_physical": None if page is None else page + 6,
        "score": score,
    }


# ---------------------------------------------------------------- 匹配口径


class TestMatchesExpected:
    def test_page_range_hit_and_miss(self):
        exp = {"source_id": "user_manual", "page_print": [243, 247]}
        assert rx.matches_expected(_ref(page=245), exp) is True
        assert rx.matches_expected(_ref(page=250), exp) is False

    def test_page_none_retrieved_never_matches_page_condition(self):
        exp = {"page_print": [1, 10]}
        assert rx.matches_expected(_ref(page=None), exp) is False

    def test_single_page_spec(self):
        assert rx.matches_expected(_ref(page=5), {"page_print": 5}) is True
        assert rx.matches_expected(_ref(page=6), {"page_print": 5}) is False

    def test_source_id_mismatch(self):
        exp = {"source_id": "other_doc", "page_print": [243, 247]}
        assert rx.matches_expected(_ref(page=245), exp) is False

    def test_section_keyword(self):
        exp = {"section_keyword": "DataReader"}
        assert rx.matches_expected(_ref(section="9.3 DataReader"), exp) is True
        assert rx.matches_expected(_ref(section="9.3 DataReader"),
                                   {"section_keyword": "NoSuchSection"}) is False

    def test_conditions_must_all_hold(self):
        exp = {"source_id": "user_manual", "page_print": [1, 10],
               "section_keyword": "安装"}
        # 页码不符 → 整体不命中，即使关键词命中
        assert rx.matches_expected(_ref(page=245, section="1.1 安装说明"), exp) is False


# ---------------------------------------------------------------- 指标


class TestQuestionMetrics:
    def test_hit_rate(self):
        retrieved = [_ref(page=10), _ref(node_id="n2", page=245)]
        exp = [{"page_print": [243, 247]}]
        assert rx.question_metric_values(retrieved, exp, "hit_rate@5") == 1.0
        assert rx.question_metric_values([_ref(page=10)], exp, "hit_rate@5") == 0.0

    def test_k_truncation(self):
        retrieved = [_ref(page=10), _ref(node_id="n2", page=11),
                     _ref(node_id="n3", page=245)]
        exp = [{"page_print": [243, 247]}]
        assert rx.question_metric_values(retrieved, exp, "hit_rate@2") == 0.0
        assert rx.question_metric_values(retrieved, exp, "hit_rate@3") == 1.0

    def test_mrr_rank(self):
        exp = [{"page_print": [243, 247]}]
        assert rx.question_metric_values([_ref(page=245)], exp, "mrr@5") == 1.0
        assert rx.question_metric_values(
            [_ref(page=10), _ref(node_id="n2", page=245)], exp, "mrr@5") == 0.5
        assert rx.question_metric_values([_ref(page=10)], exp, "mrr@5") == 0.0

    def test_precision_and_recall(self):
        retrieved = [_ref(page=10), _ref(node_id="n2", page=245)]
        exp = [{"page_print": [243, 247]}]
        assert rx.question_metric_values(retrieved, exp, "precision@2") == 0.5
        # 两条期望记录只命中其一 → recall 0.5
        exp2 = [{"page_print": [243, 247]}, {"page_print": [100, 105]}]
        assert rx.question_metric_values(retrieved, exp2, "recall@5") == 0.5

    def test_unknown_metric_raises(self):
        with pytest.raises(ValueError, match="未实现"):
            rx.question_metric_values([_ref()], [{"page_print": 1}], "ndcg@5")


# ---------------------------------------------------------------- 数据集加载


class TestDatasetLoading:
    def test_questions_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="问题集不存在"):
            rx.load_questions(tmp_path / "nope.jsonl", None)

    def test_questions_requires_id_and_question(self, tmp_path):
        p = tmp_path / "q.jsonl"
        p.write_text(json.dumps({"id": "Q1"}), encoding="utf-8")
        with pytest.raises(ValueError, match="必填字段"):
            rx.load_questions(p, None)

    def test_questions_sample_size_truncates(self, tmp_path):
        p = tmp_path / "q.jsonl"
        lines = [json.dumps({"id": f"Q{i}", "question": f"q{i}"}) for i in range(5)]
        p.write_text("\n".join(lines), encoding="utf-8")
        assert [q["id"] for q in rx.load_questions(p, 2)] == ["Q0", "Q1"]
        assert len(rx.load_questions(p, None)) == 5

    def test_expected_sources_grouping_and_validation(self, tmp_path):
        p = tmp_path / "e.jsonl"
        p.write_text(
            "\n".join([
                json.dumps({"question_id": "Q1", "page_print": [1, 2]}),
                json.dumps({"question_id": "Q1", "page_print": [9, 9]}),
            ]),
            encoding="utf-8",
        )
        grouped = rx.load_expected_sources(p)
        assert len(grouped["Q1"]) == 2
        assert rx.load_expected_sources(tmp_path / "absent.jsonl") == {}

    def test_expected_sources_requires_question_id(self, tmp_path):
        p = tmp_path / "e.jsonl"
        p.write_text(json.dumps({"page_print": [1, 2]}), encoding="utf-8")
        with pytest.raises(ValueError, match="question_id"):
            rx.load_expected_sources(p)

    def test_expected_sources_requires_at_least_one_condition(self, tmp_path):
        p = tmp_path / "e.jsonl"
        p.write_text(json.dumps({"question_id": "Q1"}), encoding="utf-8")
        with pytest.raises(ValueError, match="匹配条件"):
            rx.load_expected_sources(p)


# ---------------------------------------------------------------- 检索执行与报告


class _FakeRetriever:
    def __init__(self, answers: dict[str, list[dict]]) -> None:
        self._answers = answers

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        return self._answers[question][:top_k]


def test_run_queries_maps_by_question_id():
    r = _FakeRetriever({"问题A": [_ref()], "问题B": [_ref(page=10)]})
    out = asyncio.run(rx._run_queries(
        r, [{"id": "Q1", "question": "问题A"}, {"id": "Q2", "question": "问题B"}], 5))
    assert set(out) == {"Q1", "Q2"}
    assert out["Q1"][0]["page_print"] == 245


@pytest.fixture()
def cfg():
    return ec.load(REPO_ROOT / "configs" / "experiments" / "struct_v1.yaml")


class TestReport:
    def test_aggregation_and_skip(self, cfg):
        questions = [
            {"id": "Q1", "question": "问题A"},
            {"id": "Q2", "question": "问题B"},
        ]
        retrievals = {"Q1": [_ref(page=245)], "Q2": [_ref(page=10)]}
        expected = {"Q1": [{"page_print": [243, 247]}]}  # Q2 无标注 → 跳过
        report = rx.build_report(cfg, retrievals, questions, expected,
                                 ["hit_rate@5", "mrr@5"], 1.23, fake_embed=False)
        assert report["schema"] == rx.REPORT_SCHEMA
        assert report["experiment"] == "struct_v1"
        assert report["metrics"] == {"hit_rate@5": 1.0, "mrr@5": 1.0}
        assert report["dataset"]["evaluated"] == 1
        assert report["dataset"]["skipped_no_expected"] == ["Q2"]
        assert report["compare_baseline"] is None
        assert any("占位" in n for n in report["notes"])

    def test_fake_embed_note(self, cfg):
        report = rx.build_report(cfg, {"Q1": []}, [{"id": "Q1", "question": "x"}],
                                 {"Q1": [{"page_print": [1, 2]}]},
                                 ["hit_rate@5"], 0.1, fake_embed=True)
        assert any("fake-embed" in n for n in report["notes"])

    def test_write_report_and_baseline_compare(self, cfg, tmp_path, monkeypatch):
        monkeypatch.setattr(rx, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "base.json").write_text(
            json.dumps({"metrics": {"hit_rate@5": 0.5, "mrr@5": 0.4}}),
            encoding="utf-8")
        cfg.report.compare_baseline = "base.json"
        cfg.report.dir = "reports"

        report = rx.build_report(cfg, {"Q1": [_ref(page=245)]},
                                 [{"id": "Q1", "question": "x"}],
                                 {"Q1": [{"page_print": [243, 247]}]},
                                 ["hit_rate@5", "mrr@5"], 0.5, fake_embed=False)
        assert report["compare_baseline"] == {
            "baseline": "base.json",
            "delta": {"hit_rate@5": 0.5, "mrr@5": 0.6},
        }
        path = rx.write_report(cfg, report)
        assert path == tmp_path / "reports" / "struct_v1.json"
        assert json.loads(path.read_text(encoding="utf-8"))["experiment"] == "struct_v1"


# ------------------------------------------------- R5/R6/D3 回归（2026-09-07）
# 三条修复都必须有测试锁定：R1 事故的教训是「修复会被基于旧基线的 PR 静默覆盖」。


class TestIndexIdentity:
    def test_hash8_ignores_sections_irrelevant_to_index(self, cfg):
        """R5：改生成/评测/报告段不得改变索引目录名，否则真实索引被孤儿化。"""
        before = ec.config_hash8(cfg)
        cfg.generation.enabled = not cfg.generation.enabled
        cfg.generation.prompt_version = "v0" if cfg.generation.prompt_version == "v1" else "v1"
        cfg.evaluation.response_metrics = ["faithfulness"]
        cfg.report.compare_baseline = "anything"
        cfg.experiment.description = "改了描述也不该触发重建"
        assert ec.config_hash8(cfg) == before

    @pytest.mark.parametrize("section,attr,value", [
        ("embedding", "model", "bge-large-zh-v1.5"),
        ("index", "metric", "ip"),
        ("retrieval", "mode", "bm25"),
    ])
    def test_hash8_tracks_index_relevant_sections(self, cfg, section, attr, value):
        before = ec.config_hash8(cfg)
        setattr(getattr(cfg, section), attr, value)
        assert ec.config_hash8(cfg) != before

    def test_hash8_tracks_bm25_params_baked_into_artifact(self, cfg):
        """k1/b 被 BM25Store.save 落进产物，属索引身份的一部分。"""
        cfg.retrieval.mode = "bm25"
        before = ec.config_hash8(cfg)
        cfg.retrieval.params = {"k1": 2.0, "b": 0.5}
        assert ec.config_hash8(cfg) != before

    def test_nodes_fingerprint_ignores_line_endings(self, cfg, tmp_path, monkeypatch):
        """R6：.gitattributes 的 `*.jsonl text eol=lf` 不得让指纹失效。"""
        import build_index as bi

        monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
        nodes_dir = tmp_path / "data" / "processed"
        nodes_dir.mkdir(parents=True)
        p = nodes_dir / "struct_v1.jsonl"
        line = '{"node_id":"n1","text":"连接失败","metadata":{}}\n'

        p.write_bytes(line.encode("utf-8"))
        as_lf = bi._nodes_file_sha12(cfg)
        p.write_bytes(line.replace("\n", "\r\n").encode("utf-8"))
        as_crlf = bi._nodes_file_sha12(cfg)

        assert as_lf is not None
        assert as_lf == as_crlf

    def test_fingerprint_has_single_source_of_truth(self, cfg, tmp_path, monkeypatch):
        """R6 的另一半：写入侧与校验侧必须同值，否则索引复用恒被拒绝。"""
        import build_index as bi

        monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
        nodes_dir = tmp_path / "data" / "processed"
        nodes_dir.mkdir(parents=True)
        (nodes_dir / "struct_v1.jsonl").write_bytes(b'{"node_id":"n1"}\r\n')

        assert rx._nodes_file_sha12(cfg) == bi._nodes_file_sha12(cfg)

    def test_manifest_records_retrieval_mode(self, cfg, tmp_path):
        """D3：bm25 索引的 manifest 不得照抄 embedding=bge-m3 / backend=chroma。"""
        import build_index as bi

        cfg.retrieval.mode = "bm25"
        cfg.retrieval.params = {"k1": 2.0, "b": 0.5}
        m = json.loads(
            bi._write_manifest(tmp_path, cfg, 3, 0.1, fake=False)
            .read_text(encoding="utf-8")
        )
        assert m["retrieval_mode"] == "bm25"
        assert m["embedding"]["model"] is None
        assert m["index"]["backend"] == "bm25-json"
        assert m["index"]["params"] == {"k1": 2.0, "b": 0.5}
