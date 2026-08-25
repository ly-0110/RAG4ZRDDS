"""POST /query —— 流式问答（Server-Sent Events）。

事件序列（evidence first：引用先于答案）：
    event: sources  检索完成，推送全部引用明细
    event: token    答案文本增量（多次）
    event: done     完整答案 + 引用汇总（正常结束标志）
    event: error    流中途出错（HTTP 已 200，错误只能走事件通道）

流开始前的失败（如问题为空白）返回普通 HTTP 4xx JSON 错误。
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from server.core.schema import QueryRequest

router = APIRouter()


def _sse(event: str, payload: dict) -> str:
    """编码一条 SSE 帧。ensure_ascii=False 保证中文原样可读。"""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/query")
async def query(req: QueryRequest, request: Request) -> StreamingResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(
            status_code=400,
            detail="问题不能是空白内容；请输入要查询的问题后重试。",
        )

    pipeline = request.app.state.pipeline
    cache = request.app.state.sources_cache
    top_k = req.top_k or request.app.state.settings.default_top_k
    rid: str = request.state.request_id

    async def event_stream() -> AsyncIterator[str]:
        try:
            chunks = await pipeline.retriever.retrieve(question, top_k)
            yield _sse("sources", {"request_id": rid, "sources": chunks})

            parts: list[str] = []
            async for token in pipeline.answer_stream.stream(question, chunks):
                parts.append(token)
                yield _sse("token", {"request_id": rid, "text": token})

            answer = "".join(parts)
            yield _sse("done", {"request_id": rid, "answer": answer, "sources": chunks})
            cache.put(rid, {"question": question, "answer": answer, "sources": chunks})
        except Exception as exc:  # noqa: BLE001 —— 流中任何错误都必须以事件形式告知客户端
            yield _sse("error", {"request_id": rid, "error": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用反向代理缓冲，保证事件即时下发
        },
    )
