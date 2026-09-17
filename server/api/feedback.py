"""POST /feedback —— 回答反馈落库。

前端只负责"点一下"，落库归 D 的日志设施：记录追加到 {log_dir}/feedback.jsonl，
与 requests.jsonl / retrievals.jsonl / sources.jsonl 同目录同格式，可离线聚合。

约定：
  * 反馈必须绑定一个 request_id —— 脱离具体回答的"整体满意度"无法归因，
    因此本接口拒绝未知 request_id（404），而不是照单收下产生孤儿记录。
  * rating 只有两档 up/down；细化原因走 comment 自由文本，不扩枚举。
  * node_ids 可选，用于指出"哪几条引用是多余的/缺失的"；服务端校验其确属
    该次回答的引用集，越界即 400（防止前端把 rid 与 node 配错对）。
  * 只落 question 摘要，不落答案正文——答案已在 sources.jsonl 里，避免重复膨胀。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from server.core.schema import FeedbackRequest

router = APIRouter()


@router.post("/feedback", status_code=201)
async def post_feedback(body: FeedbackRequest, request: Request) -> dict:
    """记录一条"有帮助/无帮助"反馈；成功返回 feedback_id 供前端回执。"""
    record = request.app.state.sources_cache.get(body.request_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(f"未找到请求 {body.request_id} 的回答记录，无法归因反馈。"
                    "请提交 /query 响应头 X-Request-ID（或 SSE 里的 request_id）。"),
        )

    known_nodes = [s.get("node_id") for s in (record.get("sources") or [])]
    if body.node_ids:
        outside = [n for n in body.node_ids if n not in known_nodes]
        if outside:
            raise HTTPException(
                status_code=400,
                detail=(f"node_ids 不属于该次引用: {outside}；"
                        f"本次引用共 {len(known_nodes)} 条。"),
            )

    feedback_id = uuid.uuid4().hex[:12]
    entry = {
        "feedback_id": feedback_id,
        "request_id": body.request_id,
        "rating": body.rating,
        "question": (record.get("question") or "")[:500],
        "answer_present": bool(record.get("answer")),
        "cited_nodes": len(known_nodes),
    }
    if body.comment:
        entry["comment"] = body.comment
    if body.node_ids:
        entry["node_ids"] = body.node_ids
    request.app.state.feedback_log.append(entry)
    return {"status": "recorded", "feedback_id": feedback_id,
            "request_id": body.request_id, "rating": body.rating}
