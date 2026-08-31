"""最小 query_engine（指南 §4：generation/query_engine）：实现
server/core/pipeline.py 的 AnswerStream 协议。

把「检索片段 → context → prompt → LLM 流式回答」串起来。chunks 为检索器
返回的富引用（含 text 正文，见 retrieval/retriever.py）。空检索给出确定性
拒答文案（第一周只含两条硬规则，不做 LLM 判空）；LLM 调用错误上抛，由
/query 的 SSE error 事件回显。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from generation.context_builder import build_context
from generation.prompts import v0

ChatStream = Callable[[list[dict[str, str]]], AsyncIterator[str]]

_NO_EVIDENCE = "当前知识库没有检索到相关内容，无法给出有依据的回答。请换一种问法或补充更多上下文。"


class AnswerStream:
    """依赖注入 chat_stream（已绑定 LLM 配置），便于单测不联网、不依赖真实模型。"""

    def __init__(self, chat_stream: ChatStream, prompt_version: str = "v0") -> None:
        self._chat_stream = chat_stream
        if prompt_version != "v0":
            raise ValueError(f"未知 prompt_version={prompt_version!r}（第一周仅支持 v0）")
        self._build_messages = v0.build_messages

    async def stream(self, question: str, chunks: list[dict]) -> AsyncIterator[str]:
        if not chunks:
            yield _NO_EVIDENCE
            return
        context = build_context(chunks)
        if not context.strip():
            yield _NO_EVIDENCE
            return
        messages = self._build_messages(question, context)
        async for token in self._chat_stream(messages):
            yield token


def build_answer_stream(cfg, chat_stream: ChatStream | None = None) -> AnswerStream:
    """按实验配置组装 AnswerStream：LLM 配置来自 .env（前缀 generation.llm_env_prefix）。

    chat_stream 缺省时绑定真实 stream_chat，并在此时读取/校验环境变量——
    缺失 LLM 配置会在服务启动阶段（而非首个请求）暴露为可读错误。
    """
    if chat_stream is None:
        from generation.llm import LLMConfig, stream_chat

        llm_cfg = LLMConfig.from_env(cfg.generation.llm_env_prefix)

        async def _stream(messages: list[dict[str, str]]) -> AsyncIterator[str]:
            async for token in stream_chat(llm_cfg, messages):
                yield token

        chat_stream = _stream
    return AnswerStream(chat_stream, prompt_version=cfg.generation.prompt_version)
