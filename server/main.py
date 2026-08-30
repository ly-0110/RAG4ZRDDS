"""FastAPI 入口：make serve → uvicorn server.main:app。

骨架阶段职责：组装管线（mock/live）、挂路由、CORS、每请求 request_id。
真实检索（B）与生成（C）经 server/core/pipeline.py 的协议接入。
第二周日志设施：请求级 JSONL 日志 + /sources 引用回查持久化（见
server/core/request_log.py；检索/回答级字段待 B/C 会签后接线）。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.api import query, sources
from server.core.pipeline import build_pipeline
from server.core.request_log import JsonlLog, PersistentSourcesStore
from server.core.settings import REPO_ROOT, Settings, settings as app_settings

# FastAPI/Starlette 在请求体无法解码（典型：中文 Windows 终端按 GBK 发送）时的原始报错
_BODY_PARSE_MSG = "There was an error parsing the body"
_BODY_PARSE_HINT = (
    "请求体解析失败：请确认发送的是合法 JSON 且以 UTF-8 编码。"
    "中文 Windows 终端常以 GBK 编码发出中文导致此错——"
    "可改用 Git Bash / Swagger UI，先执行 chcp 65001，"
    "或把请求体存为 UTF-8 文件后用 curl --data-binary @文件.json 发送。"
)


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or app_settings
    pipeline = build_pipeline(cfg.rag_mode, cfg.rag_experiment_config)  # 配置非法时在此处给出可读错误并拒绝启动

    app = FastAPI(
        title="RAG4ZRDDS API",
        version="0.4.0",
        description="ZRDDS 产品知识库问答服务（第一阶段骨架）",
    )

    log_dir = Path(cfg.log_dir)
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    request_log = JsonlLog(log_dir / "requests.jsonl")
    sources_store = PersistentSourcesStore(log_dir / "sources.jsonl", cfg.sources_cache_size)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        request_log.append({
            "type": "request",
            "request_id": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        })
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """把字段校验/JSON 解析错误翻译为中文可读信息（验收：失败返回可读错误）。"""
        rid = getattr(request.state, "request_id", "-")
        errors = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(status_code=400, content={"error": _BODY_PARSE_HINT, "request_id": rid})
        short = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in errors[:5]
        )
        return JSONResponse(status_code=422, content={"error": f"请求参数不合法：{short}", "request_id": rid})

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """统一 HTTPException 输出形状；特别翻译"体解析失败"这一英文原始报错。

        注意必须挂在 starlette 的基类上：fastapi.routing 对体解析的兜底
        （routing.py "There was an error parsing the body"）抛出的是基类实例，
        挂在 fastapi.HTTPException 子类上按 MRO 查不到。
        """
        rid = getattr(request.state, "request_id", "-")
        detail = exc.detail
        if detail == _BODY_PARSE_MSG:
            detail = _BODY_PARSE_HINT
        content = {"error": detail} if isinstance(detail, str) else {"detail": detail}
        content["request_id"] = rid
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "-")
        return JSONResponse(
            status_code=500,
            content={"error": f"服务内部错误：{type(exc).__name__}: {exc}", "request_id": rid},
        )

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict:
        return {"status": "ok", "mode": cfg.rag_mode}

    app.include_router(query.router, tags=["qa"])
    app.include_router(sources.router, tags=["qa"])

    app.state.settings = cfg
    app.state.pipeline = pipeline
    app.state.request_log = request_log
    app.state.sources_cache = sources_store
    return app


try:
    app = create_app()
except RuntimeError as e:
    # 配置/接线问题（如 RAG_MODE=live 但真实实现未合入）：先给一行可读原因，再保留堆栈。
    import sys

    print(f"[server.main] 服务无法启动：{e}", file=sys.stderr)
    raise
