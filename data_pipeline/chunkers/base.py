# G:\DSH workspace\data_pipeline\chunkers\base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import json, tiktoken

# -------- 统一 Chunk 结构 --------
@dataclass
class Chunk:
    chunk_id: str                 # 全局唯一，如 "struct_v1_00042"
    text: str                     # 正文
    metadata: Dict[str, Any]      # 必含：source_file, part, chapter, section_path, printed_page_start/end, node_ids[]
    token_count: int              # 用于 Embedding 截断判断
    char_start: int               # 在原始清洗文本中的偏移（可选，用于溯源高亮）
    char_end: int

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata,
            "token_count": self.token_count,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }

# -------- 抽象基类 --------
class BaseChunker(ABC):
    """
    所有分块策略的基类。
    子类必须实现 chunk()，输入已清洗的 pages.jsonl + 章节树，
    输出 List[Chunk] 并落盘 processed/{strategy}_v*.jsonl
    """
    def __init__(self, config: Dict[str, Any]):
        self.cfg = config
        self.max_chars = config.get("max_chunk_chars", 2500)
        self.overlap = config.get("overlap_chars", 200)
        self.protect_code = config.get("protect_code_table", True)
        self.encoder = tiktoken.get_encoding("cl100k_base")  # 统一 token 计数

    # ---- 子类必实现 ----
    @abstractmethod
    def chunk(self, pages: List[dict], section_tree: List[dict]) -> List[Chunk]:
        """
        核心分块逻辑。
        :param pages:        清洗后的 pages.jsonl 列表（含 text, physical_page, printed_page, toc_entries）
        :param section_tree: section_tree_v1.jsonl 列表（含层级、页码区间、section_path）
        :return:             List[Chunk]
        """
        pass

    # ---- 通用工具 ----
    def _count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def _split_long_text(self, text: str, metadata: dict) -> List[Chunk]:
        """超长文本的兜底切分（按段落/句子/字符），保留 metadata"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            # 尝试在 overlap 区间找自然边界
            if end < len(text):
                boundary = text.rfind("\n", start, end)
                if boundary == -1:
                    boundary = text.rfind("。", start, end)
                if boundary != -1 and boundary > start + self.max_chars // 2:
                    end = boundary + 1
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=f"{metadata.get('chunk_prefix','unk')}_{len(chunks):05d}",
                    text=chunk_text,
                    metadata=metadata.copy(),
                    token_count=self._count_tokens(chunk_text),
                    char_start=start,
                    char_end=end,
                ))
            # 防死循环：尾部剩余不足 overlap 时直接到末尾，避免 start 不前进
            next_start = end - self.overlap
            start = next_start if next_start > start else end
        return chunks

    def _protect_code_tables(self, text: str) -> List[Tuple[str, bool]]:
        """
        将代码块(```...```)和表格(|...|)标记为 atomic=True，
        返回 [(segment, is_atomic), ...]
        """
        # 简易实现：按 ``` 分割，表格同理
        parts = []
        last = 0
        for m in re.finditer(r'```[\s\S]*?```', text):
            if m.start() > last:
                parts.append((text[last:m.start()], False))
            parts.append((m.group(), True))
            last = m.end()
        if last < len(text):
            parts.append((text[last:], False))
        return parts

# -------- 工厂函数（供 ingest.py / 实验脚本用） --------
def get_chunker(strategy: str, config: Dict[str, Any]) -> BaseChunker:
    if strategy == "structure":
        from .structure import StructureChunker
        return StructureChunker(config)
    elif strategy == "semantic":
        from .semantic import SemanticChunker
        return SemanticChunker(config)
    elif strategy == "hybrid":
        from .hybrid import HybridChunker
        return HybridChunker(config)
    else:
        raise ValueError(f"Unknown chunker: {strategy}")