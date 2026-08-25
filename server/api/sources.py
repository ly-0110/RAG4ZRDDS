"""GET /sources/{request_id} —— 引用回查（供前端渲染来源卡片 / 排障）。"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


class SourcesCache:
    """request_id → 引用明细 的有界缓存；满后淘汰最早条目。"""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._data: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def put(self, request_id: str, record: dict) -> None:
        with self._lock:
            self._data[request_id] = record
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def get(self, request_id: str) -> dict | None:
        with self._lock:
            return self._data.get(request_id)


@router.get("/sources/{request_id}")
async def get_sources(request_id: str, request: Request) -> dict:
    record = request.app.state.sources_cache.get(request_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到请求 {request_id} 的引用记录：可能不存在，或已超出服务端缓存范围。",
        )
    return {"request_id": request_id, **record}
