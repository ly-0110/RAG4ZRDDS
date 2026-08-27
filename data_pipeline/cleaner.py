# G:\DSH workspace\data_pipeline\cleaner.py
"""
清洗器：
- 逐页去除固定页眉 "臻融数据分发服务DDS 系统软件"
- 去除页码行（纯数字行，或 "第 X 页" 形式）
- 保留物理页码 / 印刷页码 双记录
- 输出 data/cleaned/pages.jsonl（每行：physical_page, printed_page, text, toc_entries）
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict
import json


HEADER_TEXT = "臻融数据分发服务DDS 系统软件"
# 页码行正则：单独一行的数字，或 "第 123 页"、"第123页"、"123/295" 等
PAGE_NUM_PATTERN = re.compile(
    r"""^\s*
        (?:
            \d+                    # 纯数字
            |
            第\s*\d+\s*页          # 第 123 页
            |
            \d+\s*/\s*\d+          # 123/295
        )
        \s*$
    """,
    re.VERBOSE | re.IGNORECASE
)


def clean_page_text(raw_text: str) -> str:
    """
    对单页文本做清洗：去页眉、去页码行、压缩多余空行。
    """
    lines = raw_text.splitlines()

    cleaned_lines = []
    for line in lines:
        stripped = line.strip()

        # 1. 去页眉（完全匹配）
        if stripped == HEADER_TEXT:
            continue

        # 2. 去页码行
        if PAGE_NUM_PATTERN.match(stripped):
            continue

        # 3. 保留其它行
        cleaned_lines.append(line)

    # 4. 压缩连续空行（最多保留 1 个空行）
    final_lines = []
    prev_empty = False
    for line in cleaned_lines:
        is_empty = (line.strip() == "")
        if is_empty and prev_empty:
            continue
        final_lines.append(line)
        prev_empty = is_empty

    # 5. 首尾去空行
    while final_lines and final_lines[0].strip() == "":
        final_lines.pop(0)
    while final_lines and final_lines[-1].strip() == "":
        final_lines.pop()

    return "\n".join(final_lines)


def clean_pages(input_path: str | Path, output_path: str | Path) -> List[Dict]:
    """
    读取 pdf_loader 产出的 pages.jsonl，逐页清洗，写出新的 pages.jsonl。
    返回清洗后的记录列表（供后续 chunking 直接用）。
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            cleaned_text = clean_page_text(rec["text"])
            rec["text"] = cleaned_text
            records.append(rec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return records


# ============ CLI 入口 ============
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean pages.jsonl (remove header/footer)")
    parser.add_argument("--input", default="data/cleaned/pages.jsonl",
                        help="输入 pages.jsonl (pdf_loader 产出)")
    parser.add_argument("--output", default="data/cleaned/pages.jsonl",
                        help="输出清洗后 pages.jsonl (默认原地覆盖)")
    args = parser.parse_args()

    print(f"[cleaner] 读取: {args.input}")
    cleaned = clean_pages(args.input, args.output)
    print(f"[cleaner] 处理 {len(cleaned)} 页，已写入: {args.output}")

    # 简单统计
    total_chars = sum(len(r["text"]) for r in cleaned)
    non_empty = sum(1 for r in cleaned if r["text"].strip())
    print(f"[cleaner] 总字符: {total_chars:,}，非空页: {non_empty}/{len(cleaned)}")