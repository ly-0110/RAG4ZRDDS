"""POST /query —— 流式问答（Server-Sent Events）。

事件序列（evidence first：引用先于答案）：
    event: sources  检索完成，推送全部引用明细
    event: token    答案文本增量（多次）
    event: done     完整答案 + 引用汇总（正常结束标志）
    event: error    流中途出错（HTTP 已 200，错误只能走事件通道）

客户端中止（v0.16）：前端"停止生成"直接 abort 请求，服务端生成器被取消、
上游 LLM 流随之关闭；已产出的部分答案以 `…（已终止）` 标注留档，仍可经
/sources/{rid} 回查。

引用一经 sources 事件下发即持久化（answer 暂为 None），此后生成侧失败客户端
已拿到的引用仍可经 /sources/{rid} 回查；成功路径在 done 后二次 put 覆盖为最终
答案（JSONL 保留两条生命周期记录，回读取最后一条）。检索失败时无引用可下发，
不落记录。
流开始前的失败（如问题为空白）返回普通 HTTP 4xx JSON 错误。
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from retrieval.retriever import to_source_refs
from server.core.pipeline import available_experiments
from server.core.request_log import request_log_scope
from server.core.schema import QueryRequest, with_source_urls

router = APIRouter()

# 客户端中止时，部分答案存进回查记录时追加的标注（前端另有"已终止"提示）
PARTIAL_SUFFIX = "…（已终止）"


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

    # F4（review §4.1）：live 模式下可按请求切换检索实验（白名单 =
    # configs/experiments/*.yaml，注册表懒组装并缓存）；mock 忽略该参数。
    mode = request.app.state.settings.rag_mode
    if req.experiment and mode == "live":
        available = available_experiments()
        if req.experiment not in available:
            raise HTTPException(
                status_code=422,
                detail=(f"未知实验 {req.experiment!r}；可用实验："
                        f"{', '.join(available) or '（无）'}"
                        "（白名单 = configs/experiments/*.yaml 文件名）"),
            )
        pipeline = await request.app.state.pipeline_registry.get_or_build(
            req.experiment, f"configs/experiments/{req.experiment}.yaml")
    else:
        pipeline = request.app.state.pipeline
    cache = request.app.state.sources_cache
    top_k = req.top_k or request.app.state.settings.default_top_k
    rid: str = request.state.request_id

    async def event_stream() -> AsyncIterator[str]:
        # 检索日志关联（docs/retrieval-log-schema.md）：本请求的 rid 经 ContextVar
        # 注入 pipeline 层包装器，retrievals.jsonl 的记录据此关联 requests.jsonl。
        with request_log_scope(rid):
            try:
                chunks = await pipeline.retriever.retrieve(question, top_k)
                # 检索器返回富引用（含 text 正文，供生成侧）；下发前端前投影为
                # SourceRef 字段，避免把整段正文塞进 sources 事件与 sources.jsonl。
                wire_sources = to_source_refs(chunks)
                # 第 8 字段 source_url（2026-09-17 会签，W1 闭环）：HTML 来源给本地
                # /documents/… 地址、PDF 为 null。下发与留档用同一份，前端无需再等回查。
                wire_sources = with_source_urls(
                    wire_sources, getattr(pipeline, "source_urls", None) or {})
                yield _sse("sources", {"request_id": rid, "sources": wire_sources})
                recorded = wire_sources
                # X3（2026-09-07 会签）：引用一经下发即持久化——之后生成侧失败
                # （如 LLM 不可达），客户端已拿到的 sources 仍可经 /sources/{rid} 回查。
                # put 每次追加序列化副本且回读取最后一条，成功路径下方二次 put
                # 覆盖为最终答案，JSONL 中保留「引用下发→答案完成」两条生命周期。
                cache.put(rid, {"question": question, "answer": None, "sources": recorded})

                parts: list[str] = []
                try:
                    async for token in pipeline.answer_stream.stream(question, chunks):
                        parts.append(token)
                        yield _sse("token", {"request_id": rid, "text": token})
                except asyncio.CancelledError:
                    # 客户端"停止生成"（前端 abort → 连接断开 → 本生成器被取消）：
                    # 上游 LLM 流随 async 生成器关闭而中断（generation/llm.py 的
                    # finally 会 close 掉 AsyncOpenAI 客户端），这里把已产出的
                    # 部分答案留档，便于 /sources/{rid} 回查与反馈归因。
                    partial = "".join(parts)
                    cache.put(rid, {
                        "question": question,
                        "answer": f"{partial}{PARTIAL_SUFFIX}" if partial else None,
                        "sources": recorded,
                    })
                    raise

                answer = "".join(parts)
                yield _sse("done", {"request_id": rid, "answer": answer, "sources": wire_sources})
                cache.put(rid, {"question": question, "answer": answer, "sources": recorded})
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
