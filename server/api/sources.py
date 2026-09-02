"""来源引用路由：GET /sources/{request_id}。

职责：按 request_id 回查持久化缓存（server/core/request_log.py），返回该请求的所有来源卡片。
Mock 模式：从 server/core/pipeline.py 的 sources_cache 读取。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/sources/{request_id}", tags=["qa"])
async def get_sources(request_id: str) -> dict:
    """获取指定请求的所有来源引用。
    
    Args:
        request_id: 请求 ID（从 X-Request-ID 头或路径参数获取）
    
    Returns:
        JSON 数组，每个元素是一个来源卡片
    
    Raises:
        HTTPException: 404 未找到该请求的来源记录
    """
    # TODO: 从 app.state.sources_cache 读取持久化数据
    # Mock 模式：返回空数组或示例数据
    return {"sources": []}
