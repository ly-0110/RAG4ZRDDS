"""live 模式启动预热（_warmup_retriever）单测。

目的：模型加载应从首个请求提前到服务启动阶段。用假检索器验证：
  1. 预热会真正调用一次 retrieve（触发 embedding 冷加载 + Chroma 查询）；
  2. 预热失败时抛出可读 RuntimeError（拒绝启动，而非留到首问报错）。
不触碰真实 bge-m3 / 索引。
"""

from __future__ import annotations

import pytest

from server.core.pipeline import _warmup_retriever


class _RecordingRetriever:
    def __init__(self, raise_exc: Exception | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self._raise = raise_exc

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        self.calls.append((question, top_k))
        if self._raise is not None:
            raise self._raise
        return []


def test_warmup_calls_retrieve_once():
    r = _RecordingRetriever()
    _warmup_retriever(r)
    assert len(r.calls) == 1
    question, top_k = r.calls[0]
    assert isinstance(question, str) and question
    assert top_k >= 1


def test_warmup_wraps_failure_into_readable_runtimeerror():
    r = _RecordingRetriever(raise_exc=FileNotFoundError("索引不存在"))
    with pytest.raises(RuntimeError, match="预热失败"):
        _warmup_retriever(r)
    # 失败前确实尝试过加载
    assert len(r.calls) == 1
