"""精排工厂（rerank.py）与精排通路（HybridRerankRetriever）单元测试。

工厂用假 CrossEncoder 替换（monkeypatch 模块属性——rerank.py 内的
`from sentence_transformers import CrossEncoder` 在调用时解析属性，可被拦截），
不加载真模型。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from retrieval.rerank import build_reranker


class FakeCrossEncoder:
    """替身：分数 = 文本长度，构造可预期的排序。"""

    init_calls = 0
    init_args: tuple = ()
    init_max_length = None

    def __init__(self, model_name, device=None, max_length=None):
        type(self).init_calls += 1
        FakeCrossEncoder.init_args = (model_name, device)
        FakeCrossEncoder.init_max_length = max_length

    def predict(self, pairs):
        return [float(len(t)) for _, t in pairs]


def test_build_reranker_is_lazy_and_resolves_local_model(tmp_path, monkeypatch):
    import sentence_transformers
    from retrieval import embeddings

    monkeypatch.setattr(embeddings, "MODEL_DIR", tmp_path)
    (tmp_path / "bge-reranker-v2-m3").mkdir()
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeCrossEncoder)
    FakeCrossEncoder.init_calls = 0

    cfg = SimpleNamespace(
        retrieval=SimpleNamespace(rerank_model="bge-reranker-v2-m3"),
        embedding=SimpleNamespace(device="cpu"),
    )
    rerank_fn = build_reranker(cfg)
    assert callable(rerank_fn)
    assert FakeCrossEncoder.init_calls == 0          # 构造阶段不加载模型

    scores = rerank_fn("查询", ["ab", "abcd"])
    assert scores == [2.0, 4.0]
    assert FakeCrossEncoder.init_args == (str(tmp_path / "bge-reranker-v2-m3"), "cpu")
    assert FakeCrossEncoder.init_max_length == 512   # 截断参数锁定（默认 8192 慢 3 倍）

    rerank_fn("查询", ["x"])
    assert FakeCrossEncoder.init_calls == 1          # 懒加载只发生一次


class FakeStore:
    """记录调用参数的假 store；返回原始 hit（含 metadata）。"""

    def __init__(self, hits: list[dict]):
        self.hits = hits
        self.calls: list[tuple] = []

    def query(self, question, top_k, filters=None):
        self.calls.append((question, top_k, filters))
        return [dict(h) for h in self.hits[:top_k]]


def _raw_hit(node_id: str, text: str, version: str = "2.0", score: float = 0.5) -> dict:
    return {
        "node_id": node_id,
        "text": text,
        "metadata": {"version": version, "source_id": "user_manual"},
        "score": score,
    }


def test_hybrid_rerank_orders_by_rerank_score_and_replaces_score():
    from retrieval.retriever import HybridRerankRetriever

    vec = FakeStore([_raw_hit("n_a", "短"), _raw_hit("n_b", "很长很长")])
    retriever = HybridRerankRetriever(vec, FakeStore([]), lambda q, texts: [1.5, 9.0])

    out = asyncio.run(retriever.retrieve("q", top_k=2))

    assert [h["node_id"] for h in out] == ["n_b", "n_a"]
    assert out[0]["score"] == 9.0 and out[1]["score"] == 1.5   # score 被精排分替换
    assert out[0]["text"] == "很长很长"
    assert out[0]["source_id"] == "user_manual"                 # 仍投影为富引用


def test_hybrid_rerank_uses_candidate_top_k_as_pool():
    from retrieval.retriever import HybridRerankRetriever

    vec, bm = FakeStore([_raw_hit("n_a", "a")]), FakeStore([_raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, bm, lambda q, texts: [1.0], candidate_top_k=30)

    asyncio.run(retriever.retrieve("q", top_k=2))

    assert vec.calls[0][1] == 30      # 池 = max(top_k, candidate_top_k)
    assert bm.calls[0][1] == 30


def test_hybrid_rerank_empty_candidates_skips_rerank():
    from retrieval.retriever import HybridRerankRetriever

    def boom(q, texts):
        raise AssertionError("空候选不应调用精排")

    retriever = HybridRerankRetriever(FakeStore([]), FakeStore([]), boom)
    assert asyncio.run(retriever.retrieve("q", top_k=5)) == []


def test_hybrid_rerank_tie_breaks_by_node_id():
    from retrieval.retriever import HybridRerankRetriever

    vec = FakeStore([_raw_hit("n_z", "z"), _raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, FakeStore([]), lambda q, texts: [1.0, 1.0])

    out = asyncio.run(retriever.retrieve("q", top_k=5))

    assert [h["node_id"] for h in out] == ["n_a", "n_z"]


def test_hybrid_rerank_pushes_filters_to_both_stores():
    from retrieval.retriever import HybridRerankRetriever

    vec, bm = FakeStore([_raw_hit("n_a", "a")]), FakeStore([_raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, bm, lambda q, texts: [1.0],
                                      filters={"source_type": "html"})

    asyncio.run(retriever.retrieve("q", top_k=1))

    assert vec.calls[0][2] == {"source_type": "html"}
    assert bm.calls[0][2] == {"source_type": "html"}
