"""精排模型工厂：实验配置 → 交叉编码器打分函数。

与 embeddings.py 同款约定：懒加载、models/ 本地目录优先、否则按 HF 别名
拉取（本机直连 huggingface.co，勿设 HF_ENDPOINT——hf-mirror 拉文件必失败）。

rerank_fn(question, texts) -> list[float] 为交叉编码器原始分，与 cosine /
BM25 / RRF 量纲均不可比——任何 score 阈值必须按 retrieval.mode 分别定标。
"""
from __future__ import annotations

from collections.abc import Callable

from retrieval.embeddings import resolve_model


def build_reranker(cfg) -> Callable[[str, list[str]], list[float]]:
    """懒加载 CrossEncoder；返回 (question, texts) -> scores 闭包。"""
    _model = None
    model_name = cfg.retrieval.rerank_model

    def rerank(question: str, texts: list[str]) -> list[float]:
        nonlocal _model
        if _model is None:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(resolve_model(model_name), device=cfg.embedding.device)
        return [float(s) for s in _model.predict([(question, t) for t in texts])]

    return rerank
