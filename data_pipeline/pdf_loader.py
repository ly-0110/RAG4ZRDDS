# G:\DSH workspace\data_pipeline\pdf_loader.py
"""
PyMuPDF 逐页加载器：
- 提取每页纯文本
- 提取书签 (TOC) 树：level, title, page(物理页码 1-based，与阅读器一致)
- 记录物理页码 (1-based) 与印刷页码 (页眉印刷数字；本手册
  printed = physical - 6，前 6 页为封面/罗马数字前言无阿拉伯页码)
产物：返回 list[PageRecord] 供 cleaner 使用
"""
from __future__ import annotations
import re
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
import json


@dataclass
class PageRecord:
    """单页记录（原始提取，未清洗）"""
    physical_page: int          # 1-based，与 PDF 阅读器页码一致
    printed_page: Optional[int] # 页眉印刷页码；前言（罗马数字页）为 None
    text: str                   # 页全文（含页眉页脚）
    blocks: List[dict]          # PyMuPDF blocks 原始结构
    toc_entries: List[dict]     # 本页对应的书签条目


@dataclass
class PDFExtractResult:
    """整份 PDF 提取结果"""
    doc_path: str
    total_pages: int
    pages: List[PageRecord]
    toc: List[dict]             # 完整书签树：[{level, title, page(1-based), ...}]
    printed_page_anomalies: List[int] = None  # 页眉页码偏离公式的物理页清单


HEADER_PATTERN = "臻融数据分发服务DDS 系统软件"
# 印刷页码 = 物理页码 + PAGE_OFFSET。2026-08-29 逐页页眉核对定值：
# 前 6 页（封面+罗马数字前言）不编页码，印刷第 1 页 = 物理第 7 页，
# 末页物理 295 = 印刷 289。旧值 +7 为方向错误（曾致 Citation 页码全错）。
PAGE_OFFSET = -6

# 页眉页码行：固定页眉之后紧跟的独立数字行（前 4 行内）
_HEADER_PAGE_NUM_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def _parse_printed_page(text: str) -> Optional[int]:
    """从页首解析印刷页码；罗马数字前言页/封面返回 None。"""
    for line in text.split("\n")[:4]:
        m = _HEADER_PAGE_NUM_RE.match(line)
        if m:
            return int(m.group(1))
    return None


def extract_pdf(pdf_path: str | Path) -> PDFExtractResult:
    """
    核心入口：逐页提取文本、blocks、书签，返回结构化结果。
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    try:
        # 1. 整份书签（get_toc 页码即 1 基物理页，直接使用）
        toc = doc.get_toc(simple=False)  # [[level, title, page, ...], ...]
        toc_entries = [
            {"level": level, "title": title, "physical_page": page}
            for level, title, page, *_ in toc
        ]

        # 2. 逐页提取
        pages: List[PageRecord] = []
        anomalies: List[int] = []
        for idx in range(doc.page_count):
            page = doc[idx]
            physical_page = idx + 1  # 1-based

            # 2.1 纯文本（保留换行）
            text = page.get_text("text")

            # 2.2 blocks 结构（含 bbox、字体、大小等，供后续结构化用）
            blocks = page.get_text("dict")["blocks"]

            # 2.3 本页对应的书签条目
            page_toc = [e for e in toc_entries if e["physical_page"] == physical_page]

            # 2.4 印刷页码：页眉解析为地面真值；解析不到时按公式兜底
            #     （前言页公式结果为负/零 → None）
            parsed = _parse_printed_page(text)
            if parsed is not None:
                printed_page = parsed
                if parsed != physical_page + PAGE_OFFSET:
                    anomalies.append(physical_page)
            else:
                fallback = physical_page + PAGE_OFFSET
                printed_page = fallback if fallback >= 1 else None

            pages.append(PageRecord(
                physical_page=physical_page,
                printed_page=printed_page,
                text=text,
                blocks=blocks,
                toc_entries=page_toc,
            ))

        return PDFExtractResult(
            doc_path=str(pdf_path),
            total_pages=doc.page_count,
            pages=pages,
            toc=toc_entries,
            printed_page_anomalies=anomalies,
        )
    finally:
        doc.close()


def save_pages_jsonl(result: PDFExtractResult, output_path: str | Path) -> None:
    """
    落盘 pages.jsonl：每行一个 PageRecord（去掉 blocks 以减小体积；
    需要 blocks 时可从 result.pages 直接取）。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for p in result.pages:
            # 写入时不带 blocks，节省空间；需要时从内存对象取
            rec = {
                "physical_page": p.physical_page,
                "printed_page": p.printed_page,
                "text": p.text,
                "toc_entries": p.toc_entries,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_pages_jsonl(input_path: str | Path) -> List[dict]:
    """读回 pages.jsonl"""
    with Path(input_path).open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ============ CLI 入口 ============
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract PDF to pages.jsonl")
    parser.add_argument("--input", default="data/raw/manuals/ZRDDS用户手册.pdf",
                        help="输入 PDF 路径")
    parser.add_argument("--output", default="data/cleaned/pages.jsonl",
                        help="输出 pages.jsonl")
    args = parser.parse_args()

    print(f"[pdf_loader] 正在提取: {args.input}")
    result = extract_pdf(args.input)
    print(f"[pdf_loader] 共 {result.total_pages} 页，书签 {len(result.toc)} 条")
    save_pages_jsonl(result, args.output)
    print(f"[pdf_loader] 已写入: {args.output}")