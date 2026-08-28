"""分块缺陷修复回归单测（D1~D5 · docs/chunking-defect-report.md）。

用合成章节树 + 合成页文本复现五类缺陷场景，验证修复后的行为：
  D1 页内标题偏移切分 —— 同页多节不再串色
  D2 同页兄弟区间颠倒 —— 不再零产出、区间不倒置
  D3 四/五级路径嵌套 —— 超大节沿子节下切、非原子块不超限
  D4 质检页眉正则按行锚定 —— 正文合法提及不误报
  D5 __main__ 自测在 GBK 控制台可运行
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

from data_pipeline.chunkers.base import Chunk, get_chunker
from data_pipeline.metadata import build_chunk_metadata
from data_pipeline.quality_check import HEADER_RE, check_nodes
from data_pipeline.section_tree import (
    attach_heading_offsets,
    build_toc_tree,
    dump_section_tree,
    finalize_page_ranges,
)

# ---------- 合成语料 ----------
# 页 6：1.1 与 1.2 同页（D1 串色 / D2 同页兄弟场景）
# 页 7：1.3 大节开头 + 四级子节 1.3.1（超长文本，D3 场景）
# 页 8：四级子节 1.3.2
# 页码从物理页 6 起，与真实手册口径一致（printed = physical + 7）
_SEC1_BODY = "这是1.1节正文，讲述阿尔法内容。"
_SEC2_BODY = "这是1.2节正文，讲述贝塔内容。"
_SUB1_BODY = "子节X的内容句子。" * 300  # ≈4200 字符 > max_chunk_chars

PAGES = [
    # 页 0–5：正文前的封面/目录占位页（真实文档页码自 0 连续）
    *[
        {"physical_page": i, "printed_page": i + 7, "text": "", "toc_entries": []}
        for i in range(6)
    ],
    {
        "physical_page": 6,
        "printed_page": 13,
        "text": f"1.1 分布式系统\n{_SEC1_BODY}\n1.2 中间件\n{_SEC2_BODY}",
        "toc_entries": [
            {"level": 1, "title": "PART 1 测试", "physical_page": 6},
            {"level": 2, "title": "第1章 概述", "physical_page": 6},
            {"level": 3, "title": "1.1 分布式系统", "physical_page": 6},
            {"level": 3, "title": "1.2 中间件", "physical_page": 6},
            {"level": 3, "title": "1.3 大节", "physical_page": 7},
            {"level": 4, "title": "1.3.1 子节X", "physical_page": 7},
            {"level": 4, "title": "1.3.2 子节Y", "physical_page": 8},
        ],
    },
    {
        "physical_page": 7,
        "printed_page": 14,
        "text": f"1.3 大节\n这是1.3节的引导段文字。\n1.3.1 子节X\n{_SUB1_BODY}",
        "toc_entries": [],
    },
    {
        "physical_page": 8,
        "printed_page": 15,
        "text": "1.3.2 子节Y\n子节Y的收尾内容。",
        "toc_entries": [],
    },
]

MAX_CHARS = 2500


def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", "", s)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """建树 + 偏移定位 + 落盘 + 分块，返回 (tree_records, chunks)"""
    tmp = tmp_path_factory.mktemp("tree")
    pages = json.loads(json.dumps(PAGES))  # 深拷贝，防上游改写

    toc_tree = build_toc_tree(pages)
    finalize_page_ranges(toc_tree, len(pages))
    attach_heading_offsets(toc_tree, pages)

    # 合成语料正文省略了 PART/章标题（真实语料全定位）；分块只消费三级及以下
    from data_pipeline.section_tree import iter_all
    miss = [n.title for n in iter_all(toc_tree)
            if n.level >= 3 and n.heading_char_offset < 0]
    assert not miss, f"三级及以下标题应全部定位成功: {miss}"

    tree_path = tmp / "section_tree_v1.jsonl"
    dump_section_tree(toc_tree, tree_path)
    records = [json.loads(l) for l in tree_path.read_text(encoding="utf-8").splitlines()
               if l.strip()]

    chunker = get_chunker("structure",
                          {"max_chunk_chars": MAX_CHARS, "overlap_chars": 200})
    chunks = chunker.chunk(pages, records)
    return records, chunks


def _chunks_of(chunks, title_suffix):
    return [c for c in chunks
            if _norm(c.metadata["section_path"]).endswith(_norm(title_suffix))]


# ---------- D1：零串色 ----------
def test_d1_same_page_sections_do_not_bleed(built):
    _, chunks = built

    sec2 = _chunks_of(chunks, "1.2 中间件")
    assert sec2, "1.2 中间件 应有产出（与 1.1 同页起始）"
    assert _norm(sec2[0].text).startswith(_norm("1.2 中间件")), \
        "1.2 首个 chunk 应以本节标题开头"
    assert all("阿尔法" not in c.text for c in sec2), "1.2 不得混入 1.1 的内容"

    sec1 = _chunks_of(chunks, "1.1 分布式系统")
    assert sec1 and all("贝塔" not in c.text for c in sec1), \
        "1.1 不得混入 1.2 的内容"


# ---------- D2：同页兄弟不再零产出、区间不倒置 ----------
def test_d2_no_inverted_ranges_and_no_missing_siblings(built):
    records, chunks = built

    for r in records:
        assert r["physical_page_end"] >= r["physical_page_start"], \
            f"区间颠倒: {r['title']}"

    assert _chunks_of(chunks, "1.1 分布式系统"), "同页兄弟 1.1 不应零产出"
    assert _chunks_of(chunks, "1.2 中间件"), "同页兄弟 1.2 不应零产出"


# ---------- D3：路径嵌套 + 超大节下切 ----------
def test_d3_level4_path_nests_parent(built):
    records, _ = built
    sub = next(r for r in records if r["title"] == "1.3.1 子节X")
    parent = next(r for r in records if r["title"] == "1.3 大节")
    assert sub["section_path"].startswith(parent["section_path"] + " / "), \
        "四级路径必须嵌套三级父标题"


def test_d3_large_section_split_along_subsections(built):
    _, chunks = built

    assert _chunks_of(chunks, "1.3.1 子节X"), "超大节应沿四级子节下切"
    assert _chunks_of(chunks, "1.3.2 子节Y"), "超大节应沿四级子节下切"

    lead = _chunks_of(chunks, "1.3 大节")
    assert any("引导段" in c.text for c in lead), "节首引导段文本不得丢失"

    oversize = [c for c in chunks if len(c.text) > MAX_CHARS]
    assert not oversize, f"非原子块不得超过 max_chunk_chars: {oversize}"


# ---------- D4：页眉正则按行锚定 ----------
def test_d4_header_regex_line_anchored():
    assert HEADER_RE.search("臻融数据分发服务DDS 系统软件已经成功安装。") is None, \
        "正文内合法提及不得判为页眉残留"
    assert HEADER_RE.search("正文行\n臻融数据分发服务DDS 系统软件\n后续行") is not None, \
        "整行页眉必须能检出"


def test_d4_quality_check_no_false_positive():
    meta = build_chunk_metadata(
        source_file="t.pdf", source_type="pdf",
        section_path="PART 1 测试 / 第1章 概述 / 1.1 分布式系统",
        section_level=3, printed_page_start=7, printed_page_end=7,
        physical_page_start=0, physical_page_end=0,
        node_ids=["n1"], chunk_id="t_00000",
        part="PART 1 测试", chapter="第1章 概述",
    )
    chunk = Chunk(chunk_id="t_00000",
                  text="臻融数据分发服务DDS 系统软件已经成功安装。" * 3,
                  metadata=meta, token_count=10, char_start=0, char_end=1)
    report = check_nodes([chunk], verbose=False)
    assert report["header_residue_ratio"] == 0.0
    assert report["duplicated_nodes"] == 0


# ---------- D5：GBK 控制台自测可运行 ----------
def _run_cli(args, tmp_path=None):
    env = dict(os.environ, PYTHONIOENCODING="gbk", PYTHONUTF8="0")
    return subprocess.run([sys.executable, *args], capture_output=True,
                          env=env, cwd=str(REPO_ROOT), timeout=120)


def test_d5_metadata_cli_under_gbk():
    r = _run_cli(["-m", "data_pipeline.metadata"])
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")


def test_d5_structure_cli_under_gbk(built, tmp_path):
    records, _ = built
    pages_path = tmp_path / "pages.jsonl"
    tree_path = tmp_path / "tree.jsonl"
    out_path = tmp_path / "out.jsonl"
    pages_path.write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in PAGES),
        encoding="utf-8")
    tree_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8")

    r = _run_cli(["-m", "data_pipeline.chunkers.structure",
                  str(pages_path), str(tree_path), str(out_path)])
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert out_path.exists()
