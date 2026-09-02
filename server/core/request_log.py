"""三级日志设施骨架（第二周，指南 §6 成员 D）。

日志统一为 JSONL，落在配置的 log_dir（默认 logs/，不入 Git）：
  * 请求级  requests.jsonl —— 每 HTTP 请求一条：request_id / method / path /
    status / 耗时（已接线，见 server.main 中间件）
  * 检索级  字段待成员 B 的检索日志字段定义（第一周遗留项）会签后接线
  * 回答级  字段待成员 C 定（生成合入后）

PersistentSourcesStore —— /sources 引用回查的持久化存储：
  替换第一周的内存环形缓存（当时约定"第二周日志设施落地后替换"）。
  记录持久化到 logs/sources.jsonl，服务重启后仍可回查；
  内存中仅保留最近 capacity 条（sources_cache_size）作为读取窗口。
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock


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
