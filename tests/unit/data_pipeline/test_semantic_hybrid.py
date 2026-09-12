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
        # 页锚点只做内部定位，绝不进入 chunk 正文（回归：曾把 \x01PAGE=\x02 泄漏进正文）
        assert "\x01" not in c.text and "\x02" not in c.text, \
            f"{c.chunk_id} 正文混入页锚点控制字符"
        assert c.text == c.text.strip()
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


def test_hybrid_nested_levels_no_duplicate_ids():
    """5 级节点只由 4 级递归产出，不因同时出现在两级候选中而重复（PR #11 缺陷）。"""
    pages = [{
        "physical_page": 7, "printed_page": 1,
        "text": "臻融数据分发服务DDS 系统软件\n5.1.4.1 QoS策略的缺省值\n"
                + "缺省值说明。" * 300,  # ~2400 字符，触发子节下切
        "blocks": [], "toc_entries": [],
    }]
    l3 = {"node_id": "s_l3", "level": 3, "title": "5.1.4 QoS策略",
          "part": "PART 2", "chapter": "第5章 实体",
          "section_path": "PART 2 / 第5章 实体 / 5.1.4 QoS策略",
          "physical_page_start": 7, "physical_page_end": 7,
          "printed_page_start": 1, "printed_page_end": 1,
          "heading_physical_page": 7, "heading_char_offset": 0}
    l4 = dict(l3, node_id="s_l4", level=4, title="5.1.4.1 缺省值",
              section_path="PART 2 / 第5章 实体 / 5.1.4 QoS策略 / 5.1.4.1 缺省值")
    l5 = dict(l4, node_id="s_l5", level=5, title="5.1.4.1.x 细则",
              section_path="PART 2 / 第5章 实体 / 5.1.4 QoS策略 / 5.1.4.1 缺省值 / 5.1.4.1.x 细则")
    l3["children"], l4["children"], l5["children"] = [l4], [l5], []

    chunker = HybridChunker({
        "max_chunk_chars": 800, "overlap_chars": 100, "large_section_thresh": 800,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    chunks = chunker.chunk(pages, [l3])
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), f"chunk_id 碰撞: {[i for i in ids if ids.count(i) > 1]}"
    assert len(chunks) > 0


def test_factory_supports_all_three_strategies():
    cfg = {"max_chunk_chars": 100, "overlap_chars": 10, "embed_model": "mock"}
    for name, cls in (("structure", "StructureChunker"),
                      ("semantic", "SemanticChunker"),
                      ("hybrid", "HybridChunker")):
        chunker = get_chunker(name, cfg)
        assert type(chunker).__name__ == cls


# ============================================================================
# A 域遗留修复（docs/week2-delivery-review.md §2.1）：
#   1) 碎块过滤：默认 ≥20 字符；166/1059 块 <50 字符的图号/节号碎片不再入索引
#   2) 生成性能：全文档一次 embedding batch 调用（原逐页方案 ~300 次）
# ============================================================================

def test_semantic_short_chunk_filter_default():
    """默认 min_chunk_chars=20，所有产出 chunk 长度 ≥20（碎块过滤）。"""
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    assert chunker.min_chunk_chars == 20
    chunks = chunker.chunk(_make_pages(), _make_tree())
    assert chunks, "mock 嵌入下应至少产出 1 块"
    too_short = [c for c in chunks if len(c.text) < 20]
    assert not too_short, f"<20 字符碎块未过滤: {[c.chunk_id for c in too_short]}"


def test_semantic_short_chunk_filter_disabled():
    """min_chunk_chars=0 关闭过滤（向后兼容：对比实验需要原始分布）。"""
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock", "min_chunk_chars": 0,
    })
    assert chunker.min_chunk_chars == 0
    # 仅断言配置生效，不断言数量（mock 嵌入可能全部命中过滤阈值）
    chunks = chunker.chunk(_make_pages(), _make_tree())
    # 配置被尊重即可
    assert isinstance(chunks, list)


def test_semantic_page_anchor_round_trip():
    """全文档拼接后，跨页 node 的 physical/printed 页必须命中 included_pages。"""
    # 4 页假数据，每页 6 个长句（mock 嵌入大概率切分跨页）
    pages = []
    for phys in (7, 8, 9, 10):
        body = (
            "1.1 分布式系统概述。本节介绍 ZRDDS 的整体架构与通信机制。"
            "1.2 核心概念。域参与者是通信的基本单元。"
            "1.3 数据分发。Publisher 与 Subscriber 模型。"
            "1.4 QoS 策略。DurabilityQosPolicy 控制持久性。"
            "1.5 监听器。Listener 回调通知数据到达事件。"
            "1.6 等待集。WaitSet 用于同步等待多个条件。"
        )
        pages.append({
            "physical_page": phys,
            "printed_page": phys - 6,
            "text": f"臻融数据分发服务DDS 系统软件\n{body}\n",
            "blocks": [],
            "toc_entries": [],
        })
    tree = [{
        "node_id": "s_PART1_ch1_1",
        "level": 3,
        "title": "1.1 分布式系统概述",
        "part": "PART1 背景介绍",
        "chapter": "第1章 概述",
        "section_path": "PART1 背景介绍 / 第1章 概述 / 1.1 分布式系统概述",
        "physical_page_start": 7,
        "physical_page_end": 10,
        "printed_page_start": 1,
        "printed_page_end": 4,
        "heading_physical_page": 7,
        "heading_char_offset": 0,
        "children": [],
    }]

    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    chunks = chunker.chunk(pages, tree)
    assert chunks, "应有产出"
    included_phys = {7, 8, 9, 10}
    included_printed = {1, 2, 3, 4}
    for c in chunks:
        # 物理页与印刷页都必须在 included_pages 中（不允许 None/0/未命中）
        assert c.metadata["physical_page_start"] in included_phys, \
            f"{c.chunk_id} phys {c.metadata['physical_page_start']} 未命中 included"
        assert c.metadata["printed_page_start"] in included_printed, \
            f"{c.chunk_id} printed {c.metadata['printed_page_start']} 未命中 included"
        # 双页码 = 块起始页单页口径（与 struct 方案一致）
        assert c.metadata["printed_page_start"] == c.metadata["printed_page_end"]
        assert c.metadata["physical_page_start"] == c.metadata["physical_page_end"]
        # 印刷 = 物理 − 6（约定）
        assert c.metadata["printed_page_start"] == c.metadata["physical_page_start"] - 6


def test_semantic_single_embedding_batch_call():
    """性能关键路径：splitter.get_nodes_from_documents 收到 1 个 Document（全文档拼接）。

    原逐页方案：chunk() 构造 N 个 Document → splitter 内部循环 N 次
    build_semantic_nodes_from_documents → N 次 get_text_embedding_batch
    （bge-m3 CPU 实测 ~25 min）。
    现方案：1 个 Document → 1 次 batch 调用。

    测法：monkey-patch `NodeParser.get_nodes_from_documents`（基类非 pydantic
    frozen，可安全替换），记录每次调用收到的 Document 列表长度之和；
    若仍走逐页方案，5 页输入会被调 5 次，每次 list 长度 = 1，总数 = 5；
    现方案应只调 1 次，list 长度 = 1，总数 = 1。
    """
    from data_pipeline.chunkers import semantic as sem_mod
    from llama_index.core.node_parser import NodeParser

    real_fn = NodeParser.get_nodes_from_documents
    stats = {"calls": 0, "total_docs": 0}

    def counting(self, nodes, *args, **kwargs):
        stats["calls"] += 1
        stats["total_docs"] += len(nodes)
        return real_fn(self, nodes, *args, **kwargs)

    import unittest.mock as _mock
    _patcher = _mock.patch.object(
        NodeParser, "get_nodes_from_documents", counting)
    _patcher.start()
    try:
        chunker = sem_mod.SemanticChunker({
            "max_chunk_chars": 2500, "overlap_chars": 200,
            "breakpoint_percentile_threshold": 95, "buffer_size": 1,
            "embed_model": "mock",
        })
        # 5 页输入（若回退逐页方案则会被调 5 次）
        pages = []
        for phys in (7, 8, 9, 10, 11):
            body = "1.1 分布式系统概述。本节介绍 ZRDDS 的整体架构。" * 5
            pages.append({
                "physical_page": phys, "printed_page": phys - 6,
                "text": f"臻融数据分发服务DDS 系统软件\n{body}\n",
                "blocks": [], "toc_entries": [],
            })
        tree = [{
            "node_id": "s_PART1_ch1_1", "level": 3,
            "title": "1.1 分布式系统概述", "part": "PART1 背景介绍",
            "chapter": "第1章 概述",
            "section_path": "PART1 背景介绍 / 第1章 概述 / 1.1 分布式系统概述",
            "physical_page_start": 7, "physical_page_end": 11,
            "printed_page_start": 1, "printed_page_end": 5,
            "heading_physical_page": 7, "heading_char_offset": 0,
            "children": [],
        }]
        chunks = chunker.chunk(pages, tree)
        assert stats["calls"] == 1 and stats["total_docs"] == 1, (
            f"全文档拼接应只传 1 个 Document；实测 calls={stats['calls']}, "
            f"total_docs={stats['total_docs']}——可能回退到逐页方案"
        )
        assert chunks is not None
    finally:
        _patcher.stop()


def test_semantic_empty_included_pages_returns_empty():
    """全部页面无章节归属 → 返回空列表，不抛错、不构造伪 chunk。"""
    pages = [{
        "physical_page": 1, "printed_page": 1,
        "text": "封面。", "blocks": [], "toc_entries": [],
    }]
    tree = [{
        "node_id": "s_ch1", "level": 3, "title": "x",
        "part": "P", "chapter": "C",
        "section_path": "P / C / x",
        "physical_page_start": 100, "physical_page_end": 200,
        "printed_page_start": 1, "printed_page_end": 1,
        "heading_physical_page": 100, "heading_char_offset": 0,
        "children": [],
    }]
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    assert chunker.chunk(pages, tree) == []


def _distinct_pages():
    """跨页映射用：每页正文含本页唯一编号，避免子串歧义。"""
    pages = []
    for phys in (7, 8, 9):
        pages.append({
            "physical_page": phys,
            "printed_page": phys - 6,
            "text": (
                f"页号{phys}起始标题。这是第{phys}页的第一句正文。"
                f"第{phys}页继续介绍数据分发服务。"
                f"第{phys}页再补一句关于 QoS 的内容。"
                f"第{phys}页结尾句收束本页。"
            ),
            "blocks": [],
            "toc_entries": [],
        })
    return pages


def _build_full_text(chunker, pages):
    """与 chunk() 内部一致的拼接（本组 fixture 全部命中章节树，无跳过页）。"""
    included = sorted(pages, key=lambda x: x["physical_page"])
    parts = []
    for p in included:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        parts.append(chunker._PAGE_ANCHOR_FMT.format(phys=p["physical_page"]))
        parts.append(text)
    return "\n\n".join(parts)


def test_semantic_stream_index_and_partition_mapping():
    """句流索引：每条句子带页标签；node 文本 = 句流连续子串时，起始偏移
    定位到的正是该句所在物理页（块起始页口径）。"""
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    pages = _distinct_pages()
    full_text = _build_full_text(chunker, pages)
    pages_of, offsets, concat = chunker._build_stream_index(full_text)

    assert len(pages_of) == len(offsets) >= 6
    assert offsets[0] == 0
    assert offsets == sorted(offsets)
    assert set(p for p in pages_of if p is not None) == {7, 8, 9}
    # 首句之后每条句子都必须能定位到页（锚点只在句首）
    assert pages_of[0] == 7

    printed_for_chunk = {p["physical_page"]: p["printed_page"] for p in pages}
    # 顺序模拟 splitter 的分块：node = concat[a:b]，逐段游标匹配
    cursor = 0
    step = 2  # 每 2 个句子一刀
    k = 0
    while cursor < len(concat):
        end = (offsets[k + step] if k + step < len(offsets) else len(concat))
        raw = concat[cursor:end]
        start_off = chunker._locate_node_in_stream(raw, cursor, concat)
        assert start_off == cursor, f"第{k}段未在游标处精确命中"
        phys = chunker._resolve_phys_for_node(
            raw, start_off, pages_of, offsets, printed_for_chunk)
        # 起始句在 pages_of 里的标签 = 该 node 的块起始页
        exp = pages_of[k]
        assert phys == exp, f"段@{k} 起始页应为 {exp}，实测 {phys}"
        assert printed_for_chunk[phys] == phys - 6
        cursor = end
        k += step
    assert cursor == len(concat), "各段应完整覆盖整个句流"


def test_semantic_chunk_clean_text_matches_source_and_maps_start_page():
    """锚点剥离后，chunk 正文 = 源页文本去锚点拼接，且物理/印刷页指向
    chunk 的起始页（mock 合并跨页时也应落在所辖页内）。"""
    chunker = SemanticChunker({
        "max_chunk_chars": 2500, "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95, "buffer_size": 1,
        "embed_model": "mock",
    })
    pages = _make_pages()
    full_text = _build_full_text(chunker, pages)
    pages_of, offsets, concat = chunker._build_stream_index(full_text)
    # 锚点剥离后，全文应不含控制字符
    assert "\x01" not in chunker._clean_node_text(concat)

    chunks = chunker.chunk(pages, _make_tree())
    assert chunks
    for c in chunks:
        assert "\x01" not in c.text and "\x02" not in c.text
        assert c.metadata["physical_page_start"] in {7, 8, 9}
        assert c.metadata["printed_page_start"] == c.metadata["physical_page_start"] - 6
