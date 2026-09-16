"""拒答判定（generation/abstention）与 20 题专项数据集（evaluation/datasets/abstention）单测。"""
from __future__ import annotations

from evaluation.datasets import abstention as ab
from generation.abstention import is_abstention


# ---------------------------------------------------------------- is_abstention


def test_abstention_markers_hit():
    for text in (
        "当前知识库无法确认该功能是否存在。",
        "当前知识库没有检索到相关内容，无法给出有依据的回答。",
        "知识库中没有相关资料，无法可靠判断。",
        "没有找到足够资料确认。",
    ):
        assert is_abstention(text) is True, text


def test_factual_negation_is_not_abstention():
    # 「不支持 X」可能是检索到的真值（正确回答），不是「无法确认」的拒答
    assert is_abstention("ZRDDS 不支持该接口。") is False


def test_empty_and_normal_answer_are_not_abstention():
    assert is_abstention("") is False
    assert is_abstention("DataWriter 通过 create_datawriter() 创建。") is False


# ---------------------------------------------------------------- 数据集


def test_dataset_valid():
    cases = ab.load()
    assert ab.validate(cases) == []
    assert len(cases) == ab.REQUIRED_COUNT == 20


def test_dataset_counts_cover_categories():
    counts = ab.counts(ab.load())
    assert sum(counts.values()) == 20
    assert set(counts) == ab.CATEGORIES


def test_validate_rejects_bad_id_and_category():
    problems = ab.validate([
        {"id": "EC-001", "category": "fabricated_api", "question": "q", "note": "n"},
        {"id": "AB-002", "category": "bogus", "question": "q", "note": "n"},
    ])
    assert any("AB-" in p for p in problems)
    assert any("category 非法" in p for p in problems)


def test_validate_rejects_wrong_count():
    one = {"id": "AB-001", "category": "fabricated_api", "question": "q", "note": "n"}
    problems = ab.validate([one])
    assert any("!= 20" in p for p in problems)
