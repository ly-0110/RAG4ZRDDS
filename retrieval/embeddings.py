"""Embedding 工厂：实验配置 → 文本嵌入函数。

第一周仅实现本地模型（bge-m3，经 LlamaIndex HuggingFaceEmbedding，底层
sentence-transformers）；provider=api 留待后续周次。
模型采用懒加载：build_embedding 只返回闭包，首次调用才加载模型。
模型已下载到 models/{model} 时优先用本地目录（免联网）；
否则按 HuggingFace repo id 下载（国内可设 HF_ENDPOINT=https://hf-mirror.com）。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


def _resolve_model(name: str) -> str:
    local = MODEL_DIR / name
    return str(local) if local.exists() else name


def build_embedding(cfg) -> Callable[[list[str]], list[list[float]]]:
    if cfg.embedding.provider == "api":
        raise NotImplementedError(
            "第一周仅支持本地 embedding（provider: local）；api 方案待后续接入"
        )
    _model = None
    # 注：懒加载闭包非线程安全，并发首次调用可能重复加载模型；
    # 当前 CLI 单线程使用无影响，服务端接入时需加锁或改为一次性初始化。

    def embed(texts: list[str]) -> list[list[float]]:
        nonlocal _model
        if _model is None:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            _model = HuggingFaceEmbedding(
                model_name=_resolve_model(cfg.embedding.model),
                device=cfg.embedding.device,
                embed_batch_size=cfg.embedding.batch_size,
            )
        return _model.get_text_embedding_batch(texts)

    return embed
