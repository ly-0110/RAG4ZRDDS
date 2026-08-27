"""知识节点加载与字段映射 —— B 与 A 的分块产物之间的输入契约。

预期输入 jsonl（data/processed/{method}_{version}.jsonl），每行：
    {"node_id": str, "text": str, "metadata": {...}}

metadata 中 B 依赖的字段（A 的 Metadata Schema 冻结前允许命名差异，宽容映射）：
    source_id      ← source_id
    source_name    ← source_name / source_file
    section        ← section / section_path
    page_print     ← page_print / printed_page / page
    page_physical  ← page_physical / physical_page
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NodeRecord:
    node_id: str
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.metadata.get("source_id") or "unknown"

    @property
    def source_name(self) -> str:
        return (
            self.metadata.get("source_name")
            or self.metadata.get("source_file")
            or "unknown"
        )

    @property
    def section(self) -> str:
        return self.metadata.get("section") or self.metadata.get("section_path") or ""

    @property
    def page_print(self) -> int | None:
        for key in ("page_print", "printed_page", "printed_page_start", "page"):
            v = self.metadata.get(key)
            if v is not None:
                return int(v)
        return None

    @property
    def page_physical(self) -> int | None:
        for key in ("page_physical", "physical_page", "physical_page_start"):
            v = self.metadata.get(key)
            if v is not None:
                return int(v)
        return None


def load_nodes(path: str | Path) -> list[NodeRecord]:
    """逐行读取节点 jsonl；缺字段的行容忍（metadata 缺省为 {}）。"""
    nodes: list[NodeRecord] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} 第 {lineno} 行 JSON 解析失败: {e}") from e
            nodes.append(
                NodeRecord(
                    node_id=rec.get("node_id", ""),
                    text=rec.get("text", ""),
                    metadata=rec.get("metadata") or {},
                )
            )
    return nodes
