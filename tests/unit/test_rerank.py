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

    def __init__(self, model_name, device=None):
        type(self).init_calls += 1
        FakeCrossEncoder.init_args = (model_name, device)

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

    rerank_fn("查询", ["x"])
    assert FakeCrossEncoder.init_calls == 1          # 懒加载只发生一次
