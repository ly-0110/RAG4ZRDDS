"""scripts/audit_annotations.py 单测（标注真值核对）。

真值来源是"假产物"（本文件内构造的小样本），因此这里锁的是判定逻辑本身：
哪些标注必须回炉、哪些能开指标闸门——与本机 data/processed 的实际内容无关。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import audit_annotations as aa  # noqa: E402


def _node(source, start, end, title, text):
    return {"chunk_id": f"{source}_{start}", "text": text,
            "metadata": {"source_id": source, "printed_page_start": start,
                         "printed_page_end": end, "title": title,
                         "section_path": f"第1章 概述 / {title}"}}


def _html_node(chunk_id, title, url, text):
    """A 的 HTML 产物形态：无印刷页（双页码 null）+ source_url 必填。"""
    return {"chunk_id": chunk_id, "text": text,
            "metadata": {"source_id": "zrdds_dev_guide", "printed_page_start": None,
                         "printed_page_end": None, "title": title,
                         "section_path": title, "source_url": url}}


@pytest.fixture()
def truth():
    nodes = [
        _node("user_manual", 10, 12, "1.1 分布式系统",
              "ZRDDS 是数据分发服务，DomainParticipant 负责创建域。"),
        _node("user_manual", 127, 129, "10.7 DurabilityQosPolicy",
              "DurabilityQosPolicy 的 kind 取 VOLATILE_DURABILITY_QOS 为默认。"),
        _html_node("html_pub_0", "发布模块 / DDS_Publisher_create_datawriter",
                   "https://docs.example/pub.html",
                   "DDS_Publisher_create_datawriter 创建 DataWriter。"),
    ]
    tree = [{"title": "10.7 DurabilityQosPolicy", "printed_page_start": 127,
             "printed_page_end": 129, "source_id": "user_manual"},
            {"title": "1.1 分布式系统", "printed_page_start": 10,
             "printed_page_end": 12, "source_id": "user_manual"}]
    t = aa.ProductTruth(nodes, tree)
    t.load_section_index(tree)
    return t


def _ann(**kw):
    base = {"question_id": "Q001", "source_id": "user_manual",
            "page_print": 127, "section_keyword": "10.7 DurabilityQosPolicy"}
    return {**base, **kw}


# ---------------------------------------------------------------- 产物真值层


class TestProductTruth:
    def test_page_bounds_and_coverage(self, truth):
        assert truth.page_bounds("user_manual") == (10, 129)
        assert truth.has_page("user_manual", 11) is True
        assert truth.has_page("user_manual", 60) is False        # 两区间之间的空档
        assert truth.page_bounds("nope") is None

    def test_term_pages_and_section_span(self, truth):
        assert truth.term_pages("user_manual", "DurabilityQosPolicy") == {127, 128, 129}
        assert truth.term_pages("user_manual", "matched_count") == set()
        assert truth.section_span("user_manual", "10.7 DurabilityQosPolicy") == (127, 129)

    def test_normalized_matching_ignores_case_and_spaces(self, truth):
        assert truth.term_pages("user_manual", "DURABILITYQOSPOLICY") == {127, 128, 129}
        assert truth.section_span("user_manual", "10.7  DURABILITYQOSPOLICY") == (127, 129)


# ---------------------------------------------------------------- token 抽取


class TestQuestionTokens:
    def test_picks_identifiers_and_drops_stopwords(self):
        toks = aa.question_tokens("调用 DataReader 的 read_w_condition() 函数需要哪些参数？")
        assert "read_w_condition" in toks
        assert "zrdds" not in toks and "reader" not in toks       # dds 词干太碎/停用词

    def test_limit_and_dedup(self):
        toks = aa.question_tokens("DurabilityQosPolicy durabilityqospolicy HistoryQosPolicy")
        assert len(toks) <= 3
        assert len(set(toks)) == len(toks)


# ---------------------------------------------------------------- 逐题判定


class TestAuditAnnotation:
    def test_consistent_annotation_has_no_finding(self, truth):
        codes, probe = aa.audit_annotation(
            _ann(), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert codes == [], codes
        assert probe["tokens"] == ["durabilityqospolicy"]

    def test_page_beyond_product_range_blocked(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=300, section_keyword=None), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "PAGE_OUT_OF_RANGE" in codes

    def test_page_in_range_but_uncovered_by_chunk(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=60, section_keyword=None), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "PAGE_NO_CHUNK" in codes

    def test_page_range_is_checked_against_product(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=[127, 129]), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert codes == [], codes

    def test_page_range_outside_product_is_blocked(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=[127, 130], section_keyword=None), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "PAGE_OUT_OF_RANGE" in codes

    def test_invalid_page_value_is_blocked(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=[129, 127], section_keyword=None), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "PAGE_INVALID" in codes

    def test_question_token_elsewhere_is_off_page(self, truth):
        """题干问 DurabilityQosPolicy，标注却给第 11 页（该词只在 127~129 出现）。"""
        codes, probe = aa.audit_annotation(
            _ann(page_print=11, section_keyword="1.1 分布式系统"), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "QUESTION_TOKEN_OFF_PAGE" in codes
        assert probe["unmatched"][0]["appears_on"] == [127, 128, 129]

    def test_absent_token_flagged_separately(self, truth):
        codes, probe = aa.audit_annotation(_ann(), truth, None, {"Q001"},
                                           "回调里的 matched_count 表示什么？")
        assert "QUESTION_TOKEN_ABSENT" in codes
        assert probe["absent"] == ["matched_count"]

    def test_keyword_section_pages_contradict_annotation(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(page_print=10), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "SECTION_PAGE_MISMATCH" in codes

    def test_html_source_should_not_carry_print_page(self, truth):
        codes, _ = aa.audit_annotation(
            _ann(source_id="zrdds_dev_guide", page_print=5, section_keyword="发布模块"),
            truth, None, {"Q001"}, "DDS_Publisher_create_datawriter 怎么用？")
        assert "HTML_PAGE_SHOULD_BE_NULL" in codes

    def test_no_condition_and_unknown_ids(self, truth):
        codes, _ = aa.audit_annotation({"question_id": "Q9"}, truth, None, {"Q001"}, "")
        assert "CONTRACT_NO_CONDITION" in codes
        assert "CONTRACT_UNKNOWN_QUESTION_ID" in codes

    def test_mojibake_question_text_is_blocked(self, truth):
        """实测形态：ASCII 保留、非 ASCII 全变字面 `?`。

        这类损坏骗得过 token 检查——题面里的标识符照旧能在产物里命中，
        故必须由题面转码判定独立拦住（否则已废的题干一路走到闸门开启）。
        """
        garbled = ("DataReader ? on_publication_matched() ???????? "
                   "Listener???????? Status?")
        codes, probe = aa.audit_annotation(_ann(), truth, None, {"Q001"}, garbled)
        assert "QUESTION_TEXT_MOJIBAKE" in codes
        assert "QUESTION_TEXT_MOJIBAKE" in aa.BLOCKING_CODES
        assert probe["mojibake"]["longest"] >= 3

    def test_single_question_mark_is_not_mojibake(self, truth):
        codes, probe = aa.audit_annotation(
            _ann(), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么?")
        assert "QUESTION_TEXT_MOJIBAKE" not in codes
        assert "mojibake" not in probe

    def test_partial_off_page_is_not_blocking(self, truth):
        """双主题题：一个实体在标注页附近、另一个在远处 → 只记非阻断留痕。

        口径定版依据（2026-09-17）：Q018 问 on_data_available() 又追问能否调
        create_datawriter()，Q026 问 on_sample_lost() 又问 SampleStateMask——
        标注落在主实体所在章节是正确的，旧口径按"最长 token"判它们错标。
        """
        codes, probe = aa.audit_annotation(
            _ann(), truth, None, {"Q001"},
            "DurabilityQosPolicy 的 kind 默认值是什么？DomainParticipant 又是什么？")
        assert "TOKEN_PARTIAL_OFF_PAGE" in codes
        assert "QUESTION_TOKEN_OFF_PAGE" not in codes
        assert not (set(codes) & aa.BLOCKING_CODES)
        assert probe["unmatched"][0]["token"] == "domainparticipant"

    def test_all_tokens_off_page_still_blocks(self, truth):
        """题面全部实体都远离标注页 → 仍是硬阻断（这页答不了这题）。"""
        codes, _ = aa.audit_annotation(
            _ann(page_print=10, section_keyword="1.1 分布式系统"), truth, None, {"Q001"},
            "DurabilityQosPolicy 与 VOLATILE_DURABILITY_QOS 有什么关系？")
        assert "QUESTION_TOKEN_OFF_PAGE" in codes

    def test_circular_fingerprint_is_not_blocking(self, truth):
        codes, _ = aa.audit_annotation(_ann(), truth, 127, {"Q001"},
                                       "DurabilityQosPolicy 的 kind 默认值是什么？")
        assert "CIRCULAR_TOP1" in codes
        assert not (set(codes) & aa.BLOCKING_CODES)


# ---------------------------------------------------------------- 汇总与闸门


class TestAuditVerdict:
    QUESTIONS = [{"id": "Q001", "question": "DurabilityQosPolicy 的 kind 默认值是什么？"},
                 {"id": "Q002", "question": "matched_count 是什么？"}]

    def test_clean_set_passes(self, truth):
        res = aa.audit([_ann()], self.QUESTIONS[:1], truth, {}, 0.9)
        assert res["verdict"] == "pass", res["counts"]

    def test_missing_annotation_blocks(self, truth):
        res = aa.audit([_ann()], self.QUESTIONS, truth, {}, 0.9)
        assert res["verdict"] == "blocked"
        assert res["missing_annotations"] == ["Q002"]

    def test_all_top1_echo_is_suspect_circular(self, truth):
        res = aa.audit([_ann()], self.QUESTIONS[:1], truth, {"Q001": 127}, 0.9)
        assert res["verdict"] == "suspect_circular"
        assert res["circularity"]["ratio"] == 1.0

    def test_blocking_wins_over_circularity(self, truth):
        res = aa.audit([_ann(page_print=300, section_keyword=None)], self.QUESTIONS[:1],
                       truth, {"Q001": 300}, 0.9)
        assert res["verdict"] == "blocked"

    def test_mojibake_blocks_gate_despite_clean_annotation(self, truth):
        """标注本身干净、题面已废 → 仍须 blocked（题面污染检索与计分）。"""
        questions = [{"id": "Q001",
                      "question": "DataReader ? x() ???????? Listener?????? Status?"}]
        res = aa.audit([_ann()], questions, truth, {}, 0.9)
        assert res["verdict"] == "blocked"
        assert res["counts"]["QUESTION_TEXT_MOJIBAKE"] == 1


# ---------------------------------------------------------------- CLI


def test_main_returns_one_when_blocked(tmp_path, capsys):
    nodes = tmp_path / "nodes.jsonl"
    with nodes.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_node("user_manual", 127, 129, "10.7 DurabilityQosPolicy",
                                 "DurabilityQosPolicy kind"), ensure_ascii=False) + "\n")
    qs = tmp_path / "questions.jsonl"
    qs.write_text(json.dumps({"id": "Q001",
                              "question": "matched_count 的含义是什么？"},
                             ensure_ascii=False) + "\n", encoding="utf-8")
    ann = tmp_path / "expected.jsonl"
    ann.write_text(json.dumps(_ann(), ensure_ascii=False) + "\n", encoding="utf-8")

    rc = aa.main(["--questions", str(qs), "--expected", str(ann), "--nodes", str(nodes),
                  "--tree", str(tmp_path / "none.jsonl"), "--report", str(tmp_path / "r.json")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "blocked" in out and "QUESTION_TOKEN_ABSENT" in out


def test_main_passes_and_emits_abstention(tmp_path, capsys):
    nodes = tmp_path / "nodes.jsonl"
    with nodes.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_node("user_manual", 127, 129, "10.7 DurabilityQosPolicy",
                                 "DurabilityQosPolicy 的 kind 默认 VOLATILE"),
                           ensure_ascii=False) + "\n")
    qs = tmp_path / "questions.jsonl"
    qs.write_text(json.dumps({"id": "Q001",
                              "question": "DurabilityQosPolicy 的 kind 默认值？"},
                             ensure_ascii=False) + "\n", encoding="utf-8")
    ann = tmp_path / "expected.jsonl"
    ann.write_text(json.dumps(_ann(), ensure_ascii=False) + "\n", encoding="utf-8")
    abstain = tmp_path / "abstain.jsonl"

    rc = aa.main(["--questions", str(qs), "--expected", str(ann), "--nodes", str(nodes),
                  "--tree", str(tmp_path / "none.jsonl"),
                  "--report", str(tmp_path / "r.json"),
                  "--emit-abstention", str(abstain)])
    assert rc == 0, capsys.readouterr().out
    assert abstain.exists() and abstain.read_text(encoding="utf-8").strip() == ""
