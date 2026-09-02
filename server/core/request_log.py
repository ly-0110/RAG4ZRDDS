"""请求日志与来源持久化。

职责：
1. JsonlLog: 记录每个请求的元数据（request_id、方法、状态码、耗时）
2. PersistentSourcesStore: 按 request_id 持久化来源引用卡片
"""

import json
from pathlib import Path
from typing import Any


class JsonlLog:
    """JSONL 日志写入器。"""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def append(self, record: dict[str, Any]) -> None:
        """追加一条日志记录。"""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class PersistentSourcesStore:
    """来源引用持久化存储。"""
    
    def __init__(self, path: str, max_size: int = 100):
        self.path = Path(path)
        self.max_size = max_size
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[dict[str, Any]] = []
        self._load()
    
    def _load(self) -> None:
        """加载已持久化的来源记录。"""
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._records.append(json.loads(line))
    
    def save(self, request_id: str, sources: list[dict[str, Any]]) -> None:
        """保存一批来源引用。"""
        record = {
            "request_id": request_id,
            "sources": sources,
        }
        self._records.append(record)
        if len(self._records) > self.max_size:
            self._records.pop(0)
        
        # 定期落盘（简化版：每次保存都写入）
        with open(self.path, "w", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    def get_by_request_id(self, request_id: str) -> list[dict[str, Any]] | None:
        """按 request_id 查找来源引用。"""
        for record in self._records:
            if record["request_id"] == request_id:
                return record.get("sources", [])
        return None
