"""RRF 融合纯函数（retrieval/rrf.py）的单元测试。"""
from __future__ import annotations

import pytest

from retrieval.rrf import DEFAULT_RRF_K, fuse_hits


def hit(node_id: str, text: str = "") -> dict:
    return {"node_id": node_id, "text": text or f"{node_id} 正文",
            "metadata": {}, "score": 0.5}


def test_fuse_single_list_keeps_order_and_scores():
    fused = fuse_hits([[hit("a"), hit("b")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["a", "b"]
    assert fused[0]["score"] == pytest.approx(1 / 61, abs=1e-6)
    assert fused[1]["score"] == pytest.approx(1 / 62, abs=1e-6)


def test_fuse_consensus_node_gets_summed_ranks():
    # 两路都第 1 → 2/(k+1)；单路第 2 → 1/(k+2)
    fused = fuse_hits([[hit("a"), hit("b")], [hit("a")]], top_k=5)
    scores = {h["node_id"]: h["score"] for h in fused}
    assert [h["node_id"] for h in fused] == ["a", "b"]
    assert scores["a"] == pytest.approx(2 / 61, abs=1e-6)
    assert scores["b"] == pytest.approx(1 / 62, abs=1e-6)


def test_fuse_consensus_rank2_beats_single_path_rank1():
    # RRF 核心机制：两路第 2（2/62≈0.0323）> 单路第 1（1/61≈0.0164）
    fused = fuse_hits([[hit("solo"), hit("both")], [hit("both")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["both", "solo"]


def test_fuse_dedups_node_across_lists():
    fused = fuse_hits([[hit("a")], [hit("a")]], top_k=5)
    assert len(fused) == 1
    assert fused[0]["score"] == pytest.approx(2 / 61, abs=1e-6)


def test_fuse_top_k_truncates():
    fused = fuse_hits([[hit(str(i)) for i in range(10)]], top_k=3)
    assert [h["node_id"] for h in fused] == ["0", "1", "2"]


def test_fuse_tie_breaks_by_node_id_deterministically():
    # 完全对称（各在一路第 1，同分）→ node_id 升序，结果确定
    fused = fuse_hits([[hit("b")], [hit("a")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["a", "b"]


def test_fuse_prefers_first_list_payload_when_node_in_both():
    # text/metadata 取首路（vector）——两路节点集相同时字段一致，取首路仅为确定性
    a_vec = hit("a", text="vector 路正文")
    a_bm = hit("a", text="bm25 路正文")
    fused = fuse_hits([[a_vec], [a_bm]], top_k=5)
    assert fused[0]["text"] == "vector 路正文"


def test_fuse_empty_inputs_return_empty():
    assert fuse_hits([[], []], top_k=5) == []
    assert fuse_hits([], top_k=5) == []


def test_default_rrf_k_is_60():
    assert DEFAULT_RRF_K == 60.0
