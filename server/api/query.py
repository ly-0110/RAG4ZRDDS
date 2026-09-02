"""查询路由：/query POST 接收问题，返回 SSE 流式回答。

协议（docs/api.md）:
  - event: sources → 来源引用卡片
  - event: token   → 流式答案增量
  - event: done    → 收尾 + 最终 answer
  - event: error   → 错误信息
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.core.pipeline import build_pipeline

router = APIRouter()


@router.post("/query")
async def query(question: str) -> StreamingResponse:
    """问答接口：接收问题，返回 SSE 流式回答。"""
    if not question or len(question.strip()) == 0:
        raise HTTPException(status_code=400, detail="问题不能为空")

    # 构建管线（mock 或 live）
    pipeline = build_pipeline("mock", None)  # 第一周用 mock 模式

    async def event_stream() -> AsyncIterator[str]:
        # Mock 模式：直接返回示例回答
        sources = [
            {
                "node_id": "mock_node_001",
                "source_id": "user_manual",
                "source_name": "ZRDDS 用户手册.pdf",
                "section": "第 18 章 简化接口 / 18.1 简化接口的使用",
                "page_print": 68,
                "page_physical": 74,
                "score": 0.95,
            }
        ]
        
        # sources 事件
        yield f"event: sources\n{json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
        
        # 流式答案
        answer = "【Mock 模式回答】ZRDDS 简化接口 connect() 需要提供以下参数：\n\n"
        answer += "- DomainParticipantAttr 属性列表\n- EndpointName 端点名称\n- ProtocolVersion 协议版本\n\n"
        answer += "详细配置请参考 ZRDDS 用户手册第 68 页。"
        
        for chunk in answer:
            yield f"event: token\n{json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        
        # done 事件
        final_answer = answer
        yield f"event: done\n{json.dumps({'answer': final_answer, 'sources': sources}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@router.get("/sources")
async def get_sources() -> dict:
    """获取可用来源列表。"""
    return {
        "sources": [
            {
                "source_id": "user_manual",
                "source_name": "ZRDDS 用户手册.pdf",
                "version": "2.0",
            }
        ]
    }
