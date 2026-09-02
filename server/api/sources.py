"""GET /sources/{request_id} —— 引用回查（供前端渲染来源卡片 / 排障）。

存储实现为 server/core/request_log.py 的 PersistentSourcesStore
（第二周日志设施：持久化到 {log_dir}/sources.jsonl，重启后可回查）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/sources/{request_id}")
async def get_sources(request_id: str, request: Request) -> dict:
    record = request.app.state.sources_cache.get(request_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到请求 {request_id} 的引用记录：可能不存在，或已超出服务端缓存范围。",
        )
    return {"request_id": request_id, **record}
