"""GET /nodes/{node_id} —— 单节点详情回查（F3，docs/week4-delivery-review.md §4.1）。

正文出网范围说明：SSE wire 仍为 SourceRef 7 字段不变，chunk 原文不进
sources 事件与 sources.jsonl；本端点按需返回单个 Node 的原文与元数据，
供前端"节点详情"展示。属既有"正文不下发"立场的定向放宽，待 B/C/E 会签
追认（api.md v0.14）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, request: Request) -> dict:
    pipeline = request.app.state.pipeline
    kb = getattr(pipeline, "kb_stats", None)
    details = getattr(pipeline, "node_details", None) or {}
    if kb is None:
        raise HTTPException(
            status_code=404,
            detail="mock 模式无 Node 产物可查；切换 RAG_MODE=live 后可查询节点详情。",
        )
    rec = details.get(node_id)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"node_id {node_id!r} 不在当前实验（{kb.get('experiment')}）的 Node 产物中；"
                   f"可先经 /query 的 sources 事件获取有效 node_id。",
        )
    return {"node_id": node_id, **rec}
