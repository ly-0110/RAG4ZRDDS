# G:\DSH workspace\data_pipeline\metadata.py
"""
统一 Metadata Schema 定义（单一事实源）。
所有 Chunker、Retriever、Citation、API 必须遵守此 Schema。
版本：v1.0 （Week 2 冻结，Week 3 复用）
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

# ========== 字段白名单 ==========
# 必填字段（缺一不可）
REQUIRED_FIELDS = [
    "source_file",          # 来源文件名
    "source_type",          # "pdf" | "html"
    "part",                 # PART 级标题
    "chapter",              # 章级标题
    "section_path",         # 完整路径 "PART1 / 第1章 / 1.1 节"
    "section_level",        # 1~5
    "printed_page_start",   # 印刷页码起
    "printed_page_end",     # 印刷页码止
    "physical_page_start",  # 物理页码起
    "physical_page_end",    # 物理页码止
    "node_ids",             # List[str] 关联的 SectionNode IDs
    "chunk_id",             # 本 Chunk 唯一 ID
    "version",              # 文档版本 "2.0"
    "product",              # "ZRDDS"
]

# 可选字段（HTML 专用等）
OPTIONAL_FIELDS = [
    "language",             # "java" | "c" | "cpp"
    "platform",             # "linux" | "windows"
    "content_type",         # "api" | "guide" | "faq" | "error" | "tutorial"
    "api_name",             # 具体 API 名（如 "create_datawriter"）
    "error_code",           # 错误码（如 "E1003"）
    "source_url",           # HTML 才有；PDF 留空
]

ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# ========== 构建函数 ==========
def build_chunk_metadata(
    *,
    source_file: str,
    source_type: str,
    section_path: str,
    section_level: int,
    printed_page_start: int,
    printed_page_end: int,
    physical_page_start: int,
    physical_page_end: int,
    node_ids: List[str],
    chunk_id: str,
    part: str = "",
    chapter: str = "",
    source_url: str = "",
    version: str = "2.0",
    product: str = "ZRDDS",
    **optional
) -> Dict[str, Any]:
    """
    统一入口：所有 Chunker / HTML Loader 产出 metadata 时必须调用此函数。
    返回包含 ALL_FIELDS 的 dict，缺失可选字段填 None。
    """
    # 必填校验
    missing = [f for f in REQUIRED_FIELDS if f not in locals() and f not in optional]
    if missing:
        raise ValueError(f"Missing required metadata fields: {missing}")

    meta = {f: locals().get(f, optional.get(f)) for f in REQUIRED_FIELDS}
    # 可选字段补全
    for f in OPTIONAL_FIELDS:
        meta[f] = optional.get(f)
    return meta


def validate_metadata(meta: Dict[str, Any]) -> List[str]:
    """
    质检用：返回缺失的必填字段列表（空列表=通过）。
    """
    return [f for f in REQUIRED_FIELDS if not meta.get(f)]


# ========== CLI 自测 ==========
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    # 示例
    m = build_chunk_metadata(
        source_file="ZRDDS用户手册.pdf",
        source_type="pdf",
        section_path="PART1 背景介绍 / 第1章 概述 / 1.1 分布式系统",
        section_level=3,
        printed_page_start=13,
        printed_page_end=14,
        physical_page_start=6,
        physical_page_end=7,
        node_ids=["s_PART1_ch1_1_1"],
        chunk_id="struct_v1_s_PART1_ch1_1_1_00000",
        part="PART1 背景介绍",
        chapter="第1章 概述",
    )
    print("✅ Metadata 示例：")
    for k, v in m.items():
        print(f"  {k}: {v}")
    print("\n缺失校验:", validate_metadata(m))