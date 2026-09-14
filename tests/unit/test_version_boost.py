"""版本加权（boosts.py）与其在四种检索模式上的接线测试。

纯函数部分不依赖任何 store；接线部分用假 store（原始 hit）与
EphemeralClient 内存向量库，不落盘、不加载模型。
"""
from __future__ import annotations

import asyncio

import pytest

from retrieval.boosts import apply_version_boost


def _h(node_id: str, score: float, version: str | None = None) -> dict:
    md = {} if version is None else {"version": version}
    return {"node_id": node_id, "text": "t", "metadata": md, "score": score}


def test_boost_floats_matched_above_adjacent_higher():
    hits = [_h("n_a", 0.90, "2.0"), _h("n_b", 0.88, "2.4"), _h("n_c", 0.60, "2.0")]

    out = apply_version_boost(hits, "2.4", 0.1)

    assert [r["node_id"] for r in out] == ["n_b", "n_a", "n_c"]
    assert out[0]["score"] == pytest.approx((0.88 - 0.60) / 0.30 + 0.1, abs=1e-6)


def test_unmatched_keep_relative_order_and_scores_normalized():
    hits = [_h("n_a", 10.0), _h("n_b", 5.0)]

    out = apply_version_boost(hits, "9.9", 0.5)   # 无任何命中：仍归一化

    assert [r["node_id"] for r in out] == ["n_a", "n_b"]
    assert out[0]["score"] == pytest.approx(1.0)
    assert out[1]["score"] == pytest.approx(0.0)


def test_inactive_boost_returns_input_untouched():
    hits = [_h("n_a", 0.9, "2.0"), _h("n_b", 0.1, "2.4")]

    assert apply_version_boost(hits, None, 0.5) is hits     # 未配 pref
    assert apply_version_boost(hits, "2.4", 0.0) is hits    # boost=0
    assert apply_version_boost(hits, "2.4", -0.1) is hits   # 负 boost 也是 no-op


def test_ties_break_by_node_id():
    hits = [_h("n_z", 1.0, "2.4"), _h("n_a", 1.0, "2.4")]

    out = apply_version_boost(hits, "2.4", 0.2)

    assert [r["node_id"] for r in out] == ["n_a", "n_z"]
    assert out[0]["score"] == pytest.approx(out[1]["score"])


def test_single_item_pool_and_empty_pool():
    assert apply_version_boost([], "2.4", 0.1) == []

    out = apply_version_boost([_h("n_a", 3.0, "2.4")], "2.4", 0.1)
    assert out[0]["score"] == pytest.approx(0.6)            # max==min → 0.5，命中 +0.1


def test_returns_new_list_input_not_mutated():
    hits = [_h("n_a", 1.0, "2.4"), _h("n_b", 0.5, "2.0")]

    out = apply_version_boost(hits, "2.4", 0.1)

    assert out is not hits
    assert hits[0]["score"] == 1.0                          # 原列表未被改分
