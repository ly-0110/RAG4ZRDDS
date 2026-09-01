"""A 第二周交付（semantic/hybrid chunker）集成冒烟测试。

背景：PR #11 合入时未携带任何测试；本文件补最小管道验收——
mock 嵌入下三链路可跑、冻结 Schema 完整（含会签字段 source_id）、
块页码为块级口径、超长兜底不破 2500 上限、metadata 无 Schema 外字段。
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.chunkers.base import get_chunker
from data_pipeline.chunkers.semantic import SemanticChunker
from data_pipeline.chunkers.hybrid import HybridChunker
from data_pipeline.metadata import REQUIRED_FIELDS, OPTIONAL_FIELDS, validate_metadata


def _make_pages():
    """3 页假数据：物理页 1 基，印刷页 = 物理页 − 6。"""
    pages = []
    for phys in (7, 8, 9):
        body = (
            "1.1 分布式系统概述。本节介绍 ZRDDS 的整体架构。"
            "1.2 核心概念。域参与者是通信的基本单元。"
        ) * 3
        pages.append({
            "physical_page": phys,
            "printed_page": phys - 6,
            "text": f"臻融数据分发服务DDS 系统软件\n{body}\n",
            "blocks": [],
            "toc_entries": [],
        })
    return pages


def _make_tree():
    """单三级节树（含 heading 字段，semantic/hybrid 不消费但结构须兼容）。"""
    return [{
        "node_id": "s_PART1_ch1_1",
        "level": 3,
        "title": "1.1 分布式系统概述",
        "part": "PART1 背景介绍",
        "chapter": "第1章 概述",
        "section_path": "PART1 背景介绍 / 第1章 概述 / 1.1 分布式系统概述",
        "physical_page_start": 7,
        "physical_page_end": 9,
        "printed_page_start": 1,
        "printed_page_end": 3,
        "heading_physical_page": 7,
        "heading_char_offset": 0,
        "children": [],
    }]


def _assert_schema(chunk):
    missing = validate_metadata(chunk.metadata)
    assert missing == [], f"{chunk.chunk_id} 元数据缺失: {missing}"
    assert chunk.metadata["source_id"] == "user_manual"
    extra = set(chunk.metadata) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    assert not extra, f"{chunk.chunk_id} 携带 Schema 外字段: {extra}"


def test_semantic_mock_smoke():
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    chunks = chunker.chunk(_make_pages(), _make_tree())
    assert chunks, "semantic mock 冒烟应产出至少 1 块"
    for c in chunks:
        _assert_schema(c)
        assert c.chunk_id.startswith("semantic_v1_")
        # 块级页码：双页码 = 块起始页，不再用整节区间
        assert c.metadata["printed_page_start"] == c.metadata["printed_page_end"]
        assert c.metadata["physical_page_start"] == c.metadata["physical_page_end"]
        assert c.metadata["printed_page_start"] == c.metadata["physical_page_start"] - 6


def test_hybrid_mock_smoke_and_cap():
    long_text = "超长段落测试。" * 900  # 6300 字符，无子节 → 语义切分 → 字符兜底
    pages = [{
        "physical_page": 7, "printed_page": 1,
        "text": "臻融数据分发服务DDS 系统软件\n1.1 分布式系统概述\n" + long_text,
        "blocks": [], "toc_entries": [],
    }]
    tree = _make_tree()
    tree[0]["physical_page_end"] = 7
    tree[0]["printed_page_end"] = 1

    chunker = HybridChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "large_section_thresh": 2500,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    chunks = chunker.chunk(pages, tree)
    assert chunks, "hybrid mock 冒烟应产出至少 1 块"
    for c in chunks:
        _assert_schema(c)
        assert c.chunk_id.startswith("hybrid_v1_")
        assert len(c.text) <= chunker.max_chars, \
            f"{c.chunk_id} 超上限: {len(c.text)} > {chunker.max_chars}"
        assert "chunk_prefix" not in c.metadata


def test_factory_supports_all_three_strategies():
    cfg = {"max_chunk_chars": 100, "overlap_chars": 10, "embed_model": "mock"}
    for name, cls in (("structure", "StructureChunker"),
                      ("semantic", "SemanticChunker"),
                      ("hybrid", "HybridChunker")):
        chunker = get_chunker(name, cfg)
        assert type(chunker).__name__ == cls
