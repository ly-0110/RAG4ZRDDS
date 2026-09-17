"""三级日志设施（第二周，指南 §6 成员 D）。

日志统一为 JSONL，落在配置的 log_dir（默认 logs/，不入 Git）：
  * 请求级  requests.jsonl —— 每 HTTP 请求一条：request_id / method / path /
    status / 耗时（已接线，见 server.main 中间件）
  * 检索级  retrievals.jsonl —— 每次 retrieve() 一条，字段见
    docs/retrieval-log-schema.md（B v0.1，D 会签落地）：记录点在 pipeline 层
    （LoggedRetriever 包装），预热/脚本直调也入日志（request_id=null）
  * 回答级  answers.jsonl —— 每次生成一条，字段见
    docs/answer-log-schema.md（D 拟稿，2026-09-17 会签定版）：记录点在
    pipeline 层（LoggedAnswerStream 包装），终态 done / error / cancelled 各写一条

PersistentSourcesStore —— /sources 引用回查的持久化存储：
  替换第一周的内存环形缓存（当时约定"第二周日志设施落地后替换"）。
  记录持久化到 logs/sources.jsonl，服务重启后仍可回查；
  内存中仅保留最近 capacity 条（sources_cache_size）作为读取窗口。
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 循环导入：pipeline.py 运行时反向依赖本模块
    from server.core.pipeline import AnswerStream as AnswerStreamLike
    from server.core.pipeline import Retriever


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class JsonlLog:
    """追加式 JSONL 日志；自动建父目录，进程内线程安全。"""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: dict) -> None:
        entry = {"ts": _now_iso(), **record}
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


class PersistentSourcesStore:
    """request_id → 引用明细 的持久化有界存储（接口与旧内存缓存一致）。"""

    def __init__(self, path: str | Path, capacity: int) -> None:
        self._log = JsonlLog(path)
        self._capacity = capacity
        self._data: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()
        self._hydrate()

    def _hydrate(self) -> None:
        """启动时从日志文件恢复读取窗口；损坏行跳过（日志不阻断服务）。"""
        if not self._log.path.exists():
            return
        with self._log.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = entry.get("request_id")
                if rid:
                    self._data[rid] = entry.get("record") or {}
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def put(self, request_id: str, record: dict) -> None:
        self._log.append({"request_id": request_id, "record": record})
        with self._lock:
            self._data[request_id] = record
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def get(self, request_id: str) -> dict | None:
        with self._lock:
            return self._data.get(request_id)


_request_id_ctx: ContextVar[str | None] = ContextVar("current_request_id", default=None)


def current_request_id() -> str | None:
    """当前 HTTP 请求的 request_id；非请求上下文（预热/脚本直调）返回 None。"""
    return _request_id_ctx.get()


@contextmanager
def request_log_scope(request_id: str):
    """请求处理期间绑定 request_id，供 pipeline 层的检索日志关联。

    ContextVar 跨 await 在同一 task 内可见；不进 scope 的检索调用记 null
    （docs/retrieval-log-schema.md §5.4）。
    """
    token = _request_id_ctx.set(request_id)
    try:
        yield
    finally:
        _request_id_ctx.reset(token)


class LoggedRetriever:
    """检索日志接线（docs/retrieval-log-schema.md v0.1，B/D 会签）。

    包装真实检索器，每次 retrieve() 成功返回后写一条记录到
    {LOG_DIR}/retrievals.jsonl。记录点定在 pipeline 层而非 api 层：
    预热与脚本直调等非 HTTP 检索同样入日志（request_id=null）；HTTP 路径
    经 request_log_scope 注入关联 id。检索异常不落日志——服务故障由请求级
    日志与 SSE error 事件覆盖，日志里 result_count=0 才是无证据信号。
    """

    def __init__(
        self,
        inner: "Retriever",
        log: JsonlLog,
        *,
        experiment: str,
        config_hash8: str,
        index_dirname: str,
        mode: str,
        filters: dict | None = None,
    ) -> None:
        self._inner = inner
        self._log = log
        self._base = {
            "experiment": experiment,
            "config_hash8": config_hash8,
            "index_dirname": index_dirname,
            "mode": mode,
        }
        self._filters = filters or None

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        t0 = time.perf_counter()
        results = await self._inner.retrieve(question, top_k)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)  # 不含日志写盘
        record = {
            **self._base,
            "request_id": current_request_id(),
            "top_k": top_k,
            "question": question,
            "latency_ms": latency_ms,
            "result_count": len(results),
            "results": results,
        }
        if self._filters:
            record["filters"] = self._filters
        self._log.append(record)
        return results


class LoggedAnswerStream:
    """回答级日志接线（docs/answer-log-schema.md，2026-09-17 会签定版）。

    包装生成侧 `answer_stream`，**每次生成只写一条**：正常结束（done）、上游报错
    （error）、客户端中止（cancelled）三种终态都落盘，便于回答质量回查与失败归因。
    记录点与检索日志一致定在 pipeline 层——HTTP 与 MCP 两条入口都覆盖。

    字段（除注明外均必填）取自实验配置与本次生成的实测值：
      request_id（ContextVar 注入，非请求上下文为 null）/ experiment / config_hash8 /
      prompt_version / model / question / answer（正文只落本地，不进报告与 wire）/
      abstained（generation.abstention 单一事实源）/ citation_count / source_ids /
      first_token_ms / duration_ms / token_chunks / finish_reason（stop|length|
      cancelled|error）/ error。
    """

    def __init__(
        self,
        inner: "AnswerStreamLike",
        log: JsonlLog,
        *,
        experiment: str,
        config_hash8: str,
        prompt_version: str,
        model: str,
    ) -> None:
        self._inner = inner
        self._log = log
        self._base = {
            "experiment": experiment,
            "config_hash8": config_hash8,
            "prompt_version": prompt_version,
            "model": model,
        }

    def _write(self, record: dict) -> None:
        """日志写盘失败不得影响回答投递（与 PersistentSourcesStore 同原则）。"""
        try:
            self._log.append(record)
        except OSError:  # pragma: no cover —— 磁盘异常下服务继续
            pass

    async def stream(self, question: str, chunks: list[dict]):
        from generation.abstention import is_abstention

        t0 = time.perf_counter()
        first_token_ms: float | None = None
        parts: list[str] = []
        finish_reason = "error"
        error: str | None = None
        try:
            async for token in self._inner.stream(question, chunks):
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - t0) * 1000, 2)
                parts.append(token)
                yield token
            finish_reason = "stop"
        except GeneratorExit:
            # 客户端 abort → 生成器被关闭：已产出的部分答案仍要留档
            finish_reason = "cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 —— 记录后原样抛出，交 SSE error 事件
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            answer = "".join(parts)
            self._write({
                **self._base,
                "request_id": current_request_id(),
                "question": question,
                "answer": answer,
                "abstained": is_abstention(answer) if answer else False,
                "citation_count": len(chunks),
                "source_ids": sorted({c.get("source_id") for c in chunks
                                      if c.get("source_id")}),
                "first_token_ms": first_token_ms,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "token_chunks": len(parts),
                "finish_reason": finish_reason,
                "error": error,
            })
