"""页码地面真值回归（2026-08-29 用户报告修复）。

用户报告：查询 DurabilityQosPolicy 得到引用“第 139 页（物理页 132）”，
而手册中该节实际位于印刷页 127（页眉印刷数字）。逐页核对页眉后确认：
  * 真值：印刷页码 = 物理页码 − 6（前 6 页为封面/罗马数字前言不编页码，
    印刷第 1 页 = 物理第 7 页；末页物理 295 = 印刷 289）
  * 旧代码 PAGE_OFFSET=+7 方向取反，且产物物理页码为书签 0 基索引泄漏
  * 10.7 DurabilityQosPolicy 标题真值位置：物理页 133 / 印刷页 127
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_pipeline.pdf_loader import PAGE_OFFSET, _parse_printed_page
from data_pipeline.section_tree import build_toc_tree

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------- 偏移常量与页眉解析 ----------

def test_page_offset_is_minus_six():
    """印刷页码 = 物理页码 + PAGE_OFFSET，真值偏移为 −6。"""
    assert PAGE_OFFSET == -6


def test_parse_printed_page_from_header():
    text = "臻融数据分发服务DDS 系统软件\n127\n10.7 DurabilityQosPolicy\n正文"
    assert _parse_printed_page(text) == 127


def test_parse_printed_page_front_matter_is_none():
    """前言页为罗马数字页码（I~V）或无页码，解析应为 None。"""
    assert _parse_printed_page("臻融数据分发服务DDS 系统软件\nI") is None
    assert _parse_printed_page("（版本号：V2.0）") is None
    assert _parse_printed_page("") is None


# ---------- 章节树：1 基物理页 + 印刷页换算 ----------

def test_toc_tree_pages_are_1based_and_offset_minus_six():
    pages = [
        *[
            {"physical_page": i, "printed_page": None, "text": "", "toc_entries": []}
            for i in range(1, 7)
        ],
        {
            "physical_page": 7,
            "printed_page": 1,
            "text": "1.1 分布式系统\n正文甲。",
            "toc_entries": [
                {"level": 3, "title": "1.1 分布式系统", "physical_page": 7},
                {"level": 3, "title": "1.2 中间件", "physical_page": 7},
            ],
        },
    ]
    tree = build_toc_tree(pages)
    node = tree[0]
    assert node.title == "1.1 分布式系统"
    # 产物页码 = 阅读器可见的 1 基物理页；印刷页 = 物理页 − 6
    assert node.physical_page_start == 7
    assert node.printed_page_start == 1


# ---------- 真实产物回归：用户报告的 10.7 节 ----------

def test_real_artifact_durability_qos_policy_pages():
    nodes_path = REPO_ROOT / "data/processed/struct_v1.jsonl"
    if not nodes_path.exists():
        pytest.skip("struct_v1.jsonl 不存在（先运行 make ingest）")

    rec = None
    with nodes_path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if "10_7_DurabilityQosPolicy" in d["chunk_id"]:
                rec = d
                break
    assert rec is not None, "未找到 10.7 DurabilityQosPolicy 的分块"

    md = rec["metadata"]
    # 地面真值：标题在物理页 133，页眉印刷页码 127
    assert md["physical_page_start"] == 133, (
        f"物理页码应为 1 基真值 133，实际 {md['physical_page_start']}"
    )
    assert md["printed_page_start"] == 127, (
        f"印刷页码应为页眉真值 127，实际 {md['printed_page_start']}"
    )
