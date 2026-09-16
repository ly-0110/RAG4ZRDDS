"""GET /nodes/{node_id} —— 单节点详情回查（F3，docs/week4-delivery-review.md §4.1）。

正文出网范围说明：SSE wire 仍为 SourceRef 7 字段不变，chunk 原文不进
sources 事件与 sources.jsonl；本端点按需返回单个 Node 的原文与元数据，
供前端"节点详情"展示。属既有"正文不下发"立场的定向放宽，待 B/C/E 会签
追认（api.md v0.14）。

2026-09-16（F3 × F4 整合修复）：节点详情不再只认默认实验——经 F4 切到其它
实验后拿到的 node_id，会按需装载该实验的 Node 产物（NodeDetailIndex），
否则"切换检索模式"与"查看节点原文"两个功能无法并存（本机实测复现 404）。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, request: Request) -> dict:
    pipeline = request.app.state.pipeline
    kb = getattr(pipeline, "kb_stats", None)
    if kb is None:
        raise HTTPException(
            status_code=404,
            detail="mock 模式无 Node 产物可查；切换 RAG_MODE=live 后可查询节点详情。",
        )

    index = getattr(request.app.state, "node_detail_index", None)
    if index is not None:
        # 装载在 worker 线程执行：多来源产物解析是同步 IO/CPU，别卡事件循环
        found = await asyncio.to_thread(index.lookup, node_id)
        if found is not None:
            experiment, rec = found
            return {"node_id": node_id, "experiment": experiment, **rec}
    else:  # 兜底：只查默认实验表（未接线 node_detail_index 时的旧行为）
        rec = (getattr(pipeline, "node_details", None) or {}).get(node_id)
        if rec is not None:
            return {"node_id": node_id, **rec}

    raise HTTPException(
        status_code=404,
        detail=f"node_id {node_id!r} 不在已索引实验的 Node 产物中"
               f"（默认实验 {kb.get('experiment')}）；"
               f"可先经 /query 的 sources 事件获取有效 node_id。",
    )
