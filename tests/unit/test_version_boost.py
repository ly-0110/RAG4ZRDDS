"""版本加权（boosts.py）与其在四种检索模式上的接线测试。

纯函数部分不依赖任何 store；接线部分用假 store（原始 hit）与
EphemeralClient 内存向量库，不落盘、不加载模型。
"""
from __future__ import annotations

import asyncio

import pytest

from retrieval.boosts import apply_version_boost
from retrieval.nodes import NodeRecord
from retrieval.retriever import (
    BM25Retriever,
    HybridRerankRetriever,
    HybridRetriever,
    VectorRetriever,
)
from retrieval.vector_store import VectorStore


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


# ---------------------------------------------------------------- 四模式接线


class FakeEmbedder:
    def __init__(self, vectors, dim: int = 4):
        self.vectors = vectors
        self.dim = dim

    def __call__(self, texts):
        return [self.vectors.get(t, [0.0] * self.dim) for t in texts]


class FakeStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def query(self, question, top_k, filters=None):
        self.calls.append((question, top_k, filters))
        return [dict(h) for h in self.hits[:top_k]]


def _raw_hit(node_id: str, text: str, version: str = "2.0", score: float = 0.5) -> dict:
    return {"node_id": node_id, "text": text,
            "metadata": {"version": version, "source_id": "user_manual"},
            "score": score}


def _make_vector_store():
    import uuid

    vecs = {
        "q": [1.0, 0.0, 0.0, 0.0],
        "pdf 手册正文": [1.0, 0.0, 0.0, 0.0],
        "html 指南正文": [0.99, 0.141, 0.0, 0.0],
        "pdf 附录正文": [0.5, 0.866, 0.0, 0.0],
    }
    store = VectorStore(embed_fn=FakeEmbedder(vecs),
                        collection_name=f"boost_{uuid.uuid4().hex}")
    store.add_nodes([
        NodeRecord("n_pdf1", "pdf 手册正文", {"version": "2.0", "source_id": "user_manual"}),
        NodeRecord("n_html", "html 指南正文", {"version": "2.4", "source_id": "zrdds_dev_guide"}),
        NodeRecord("n_pdf2", "pdf 附录正文", {"version": "2.0", "source_id": "user_manual"}),
    ])
    return store


def test_vector_retriever_version_boost_floats_html_to_top():
    store = _make_vector_store()
    base = asyncio.run(VectorRetriever(store).retrieve("q", top_k=3))
    assert [r["node_id"] for r in base] == ["n_pdf1", "n_html", "n_pdf2"]

    boosted = asyncio.run(
        VectorRetriever(store, candidate_top_k=30, version_pref="2.4", version_boost=0.1)
        .retrieve("q", top_k=3))

    assert [r["node_id"] for r in boosted] == ["n_html", "n_pdf1", "n_pdf2"]


def test_vector_retriever_without_version_params_unchanged():
    store = _make_vector_store()
    a = asyncio.run(VectorRetriever(store).retrieve("q", top_k=2))
    b = asyncio.run(VectorRetriever(store, version_pref=None, version_boost=0.0)
                    .retrieve("q", top_k=2))

    assert [r["node_id"] for r in a] == [r["node_id"] for r in b]
    assert [r["score"] for r in a] == [r["score"] for r in b]


def test_bm25_retriever_version_boost_flips_ranking():
    from retrieval.bm25 import BM25Store

    store = BM25Store()
    store.add_nodes([
        NodeRecord("n_a", "alpha alpha alpha", {"version": "2.0", "source_id": "user_manual"}),
        NodeRecord("n_b", "alpha", {"version": "2.4", "source_id": "zrdds_dev_guide"}),
    ])
    base = asyncio.run(BM25Retriever(store).retrieve("alpha", top_k=2))
    assert [r["node_id"] for r in base] == ["n_a", "n_b"]

    boosted = asyncio.run(
        BM25Retriever(store, version_pref="2.4", version_boost=2.0).retrieve("alpha", top_k=2))

    assert [r["node_id"] for r in boosted] == ["n_b", "n_a"]


def test_hybrid_retriever_version_boost_and_pool():
    vec = FakeStore([_raw_hit("n_a", "a"), _raw_hit("n_b", "b", "2.4"),
                     _raw_hit("n_c", "c")])
    retriever = HybridRetriever(vec, FakeStore([]), candidate_top_k=10,
                                version_pref="2.4", version_boost=0.6)

    out = asyncio.run(retriever.retrieve("q", top_k=3))

    assert vec.calls[0][1] == 10                       # 池 = max(top_k, candidate_top_k)
    assert [h["node_id"] for h in out] == ["n_b", "n_a", "n_c"]


def test_hybrid_rerank_version_boost_applied_after_rerank():
    vec = FakeStore([_raw_hit("n_a", "a"), _raw_hit("n_b", "b", "2.4"),
                     _raw_hit("n_c", "c")])
    retriever = HybridRerankRetriever(
        vec, FakeStore([]), lambda q, texts: [9.0, 8.0, 5.0],
        candidate_top_k=10, version_pref="2.4", version_boost=0.3)

    out = asyncio.run(retriever.retrieve("q", top_k=3))

    assert [h["node_id"] for h in out] == ["n_b", "n_a", "n_c"]   # 精排后加权翻转
