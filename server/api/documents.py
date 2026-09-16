"""GET /documents/{source_id}/{filename} —— 本地文档原文（v0.16 新增）。

背景：Node 产物里的 `source_url` 指向配置里的占位外部域名
（`https://docs.zrtechnology.com/cdoc/html/…`，A 试跑占位值，实际不可达），
前端"打开 HTML 原文"点了必然打不开。D 侧把地址改写成指向本端点
（`/documents/{source_id}/{file}`），文件从实验配置 `sources[].path` 声明的
本地根目录读取——即 A 的 ingest 用的同一份 HTML 快照。

安全边界：
  * 只允许读取配置里登记过的来源根目录下的文件（白名单，非任意路径）；
  * 解析后必须仍在根目录内（挡 `..` 越界与符号链接逃逸）；
  * 只读、不列目录。

注意：本端点服务的是**原始 HTML 快照**（含其自带 css/js 相对引用），
与 Node 产物里的分块正文不是同一形态——前者用于"追溯到原文页"。
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/documents/{source_id}/{filename}")
async def get_document(source_id: str, filename: str, request: Request) -> FileResponse:
    # 白名单来源：应用启动期从**全部实验配置**合并（跨实验可用），
    # 兜底取当前管线的 sources（测试夹具/单实验场景）。
    roots: dict[str, Path] = (getattr(request.app.state, "source_roots", None)
                              or getattr(request.app.state.pipeline, "source_roots", None) or {})
    if not roots:
        raise HTTPException(
            status_code=404,
            detail="未登记任何本地文档目录（实验配置的 sources[].path 不存在）。",
        )
    root = roots.get(source_id)
    if root is None:
        raise HTTPException(
            status_code=404,
            detail=f"来源 {source_id!r} 未登记本地文档目录；已登记：{sorted(roots)}。",
        )

    # 只接受单层文件名，杜绝路径穿越（文档目录是平铺的）
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名非法：不接受路径分隔符。")

    target = (root / filename).resolve()
    if root not in target.parents and target.parent != root:
        raise HTTPException(status_code=400, detail="路径越界：只允许读取来源目录内的文件。")
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"文档 {filename!r} 不在来源 {source_id!r} 的目录中（{root.name}/）。",
        )

    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(target, media_type=media_type or "application/octet-stream")
