# G:\DSH workspace\data_pipeline\quality_check.py
"""
第 16 节数据质量检查清单 - 自动化实现
输入：List[Chunk]（已含 metadata）
输出：dict 报告 + 可选控制台打印
"""

from __future__ import annotations
import re
import json
from collections import Counter
from typing import List, Dict, Any
from data_pipeline.chunkers.base import Chunk
from data_pipeline.metadata import validate_metadata, REQUIRED_FIELDS

# ---------- 正则 ----------
HEADER_RE = re.compile(r"臻融数据分发服务DDS 系统软件")
PAGE_NUM_RE = re.compile(r"^\s*(\d+|第\s*\d+\s*页|\d+\s*/\s*\d+)\s*$")
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
TABLE_RE = re.compile(r"\|.*?\|(?:\n\|.*?\|)+")
IMG_PLACEHOLDER_RE = re.compile(r"\[图\s*\d+\]|\[Figure\s*\d+\]|!\[.*?\]\(.*?\)")

# ---------- 阈值（可按需调整） ----------
MIN_CHARS = 50          # 过短判定
MAX_CHARS = 10000       # 过长判定（未切分的超大节）
MAX_TOKENS = 1200       # Embedding 截断参考
DUP_THRESHOLD = 0.95    # 文本相似度去重阈值（简化用前 200 字符 Jaccard）

def check_nodes(chunks: List[Chunk], verbose: bool = True) -> Dict[str, Any]:
    """
    完整质检入口，返回报告 dict。
    """
    report = {
        "total_nodes": len(chunks),
        "empty_nodes": 0,
        "short_nodes": 0,
        "long_nodes": 0,
        "over_token_nodes": 0,
        "duplicated_nodes": 0,
        "header_residue_ratio": 0.0,
        "footer_residue_count": 0,
        "code_block_broken": 0,
        "table_broken": 0,
        "image_loss_recorded": 0,
        "page_mapping_errors": 0,
        "metadata_incomplete": 0,
        "nodes_without_page": 0,
        "len_distribution": {},
        "sample_issues": [],  # 仅记录前 5 个问题样本
    }

    texts = [c.text for c in chunks]
    metas = [c.metadata for c in chunks]

    # 1. 空 / 过短 / 过长 / 超 token
    for i, (c, meta) in enumerate(zip(chunks, metas)):
        t = c.text.strip()
        tc = c.token_count

        if not t:
            report["empty_nodes"] += 1
            _add_sample(report, i, "EMPTY", c.chunk_id)
        elif len(t) < MIN_CHARS:
            report["short_nodes"] += 1
            _add_sample(report, i, "TOO_SHORT", c.chunk_id)
        elif len(t) > MAX_CHARS:
            report["long_nodes"] += 1
            _add_sample(report, i, "TOO_LONG", c.chunk_id)

        if tc > MAX_TOKENS:
            report["over_token_nodes"] += 1

        # 2. Metadata 完整性
        missing = validate_metadata(meta)
        if missing:
            report["metadata_incomplete"] += 1
            _add_sample(report, i, f"META_MISS:{missing}", c.chunk_id)

        # 3. 页码映射
        if not meta.get("printed_page_start") or not meta.get("physical_page_start"):
            report["nodes_without_page"] += 1
            _add_sample(report, i, "NO_PAGE", c.chunk_id)
        else:
            # 印刷页码 = 物理页码 + 7（按项目约定）
            if meta["printed_page_start"] - meta["physical_page_start"] != 7:
                report["page_mapping_errors"] += 1
                _add_sample(report, i, "PAGE_OFFSET_ERR", c.chunk_id)

    # 3. 重复节点（简化：前 200 字符 Jaccard）
    dup_count = 0
    seen = []
    for i, t in enumerate(texts):
        prefix = t[:200]
        is_dup = any(_jaccard(prefix, s) > DUP_THRESHOLD for s in seen)
        if is_dup:
            dup_count += 1
            _add_sample(report, i, "DUPLICATE", chunks[i].chunk_id)
        seen.append(prefix)
    report["duplicated_nodes"] = dup_count

    # 4. 页眉残留比例
    header_hits = sum(1 for t in texts if HEADER_RE.search(t))
    report["header_residue_ratio"] = round(header_hits / len(texts), 4) if texts else 0

    # 5. 页码行残留
    footer_hits = sum(1 for t in texts for line in t.splitlines() if PAGE_NUM_RE.match(line.strip()))
    report["footer_residue_count"] = footer_hits

    # 6. 代码块被切断
    broken_code = 0
    for t in texts:
        blocks = CODE_BLOCK_RE.findall(t)
        for b in blocks:
            if not (b.startswith("```") and b.endswith("```")):
                broken_code += 1
    report["code_block_broken"] = broken_code

    # 7. 表格被切断（简易：|...| 不成对）
    broken_table = 0
    for t in texts:
        tables = TABLE_RE.findall(t)
        for tb in tables:
            rows = tb.strip().split("\n")
            if len(rows) < 2 or not all(r.count("|") >= 2 for r in rows):
                broken_table += 1
    report["table_broken"] = broken_table

    # 8. 图片内容缺失记录（统计有图片占位符但无文字说明的 chunk）
    img_loss = 0
    for t in texts:
        if IMG_PLACEHOLDER_RE.search(t) and len(t.strip()) < 100:
            img_loss += 1
    report["image_loss_recorded"] = img_loss

    # 9. 长度分布统计
    lens = [len(t) for t in texts]
    if lens:
        import numpy as np
        report["len_distribution"] = {
            "min": int(min(lens)),
            "max": int(max(lens)),
            "mean": int(sum(lens) / len(lens)),
            "p50": int(np.percentile(lens, 50)),
            "p95": int(np.percentile(lens, 95)),
        }

    # 打印摘要
    if verbose:
        _print_report(report)

    return report


# ---------- 内部工具 ----------
def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0

def _add_sample(report: dict, idx: int, issue: str, chunk_id: str):
    if len(report["sample_issues"]) < 5:
        report["sample_issues"].append({
            "index": idx,
            "chunk_id": chunk_id,
            "issue": issue
        })

def _print_report(r: dict):
    print("\n========== 数据质检报告 ==========")
    print(f"总节点数:          {r['total_nodes']}")
    print(f"空节点:            {r['empty_nodes']}")
    print(f"过短(<{MIN_CHARS}c):   {r['short_nodes']}")
    print(f"过长(>{MAX_CHARS}c):  {r['long_nodes']}")
    print(f"超Token(>{MAX_TOKENS}): {r['over_token_nodes']}")
    print(f"重复节点:          {r['duplicated_nodes']}")
    print(f"页眉残留比例:       {r['header_residue_ratio']*100:.1f}%")
    print(f"页码行残留:         {r['footer_residue_count']}")
    print(f"代码块切断:         {r['code_block_broken']}")
    print(f"表格异常:           {r['table_broken']}")
    print(f"图片内容缺失疑似:    {r['image_loss_recorded']}")
    print(f"页码映射错误:       {r['page_mapping_errors']}")
    print(f"Metadata缺失:       {r['metadata_incomplete']}")
    print(f"无页码节点:         {r['nodes_without_page']}")
    if r["len_distribution"]:
        ld = r["len_distribution"]
        print(f"长度分布: min={ld['min']}, max={ld['max']}, avg={ld['mean']}, p50={ld['p50']}, p95={ld['p95']}")
    if r["sample_issues"]:
        print("问题样本(前5):")
        for s in r["sample_issues"]:
            print(f"  [{s['issue']}] idx={s['index']} id={s['chunk_id']}")
    print("==================================\n")


# ---------- CLI ----------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from data_pipeline.chunkers.base import Chunk

    # 用法: python -m data_pipeline.quality_check data/processed/struct_v1.jsonl
    jsonl_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/struct_v1.jsonl"

    # 反序列化 Chunk
    chunks = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            chunks.append(Chunk(**d))

    check_nodes(chunks)