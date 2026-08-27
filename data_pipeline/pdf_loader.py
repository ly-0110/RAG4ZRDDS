# G:\DSH workspace\data_pipeline\pdf_loader.py
"""
PyMuPDF 逐页加载器：
- 提取每页纯文本
- 提取书签 (TOC) 树：level, title, page(物理页码 0-based)
- 记录物理页码 (0-based) 与印刷页码 (1-based, 物理页码+7) 的映射
产物：返回 list[PageRecord] 供 cleaner 使用
"""
from __future__ import annotations
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
import json


@dataclass
class PageRecord:
    """单页记录（原始提取，未清洗）"""
    physical_page: int          # 0-based
    printed_page: int           # 1-based，约定 printed = physical + 7
    text: str                   # 页全文（含页眉页脚）
    blocks: List[dict]          # PyMuPDF blocks 原始结构
    toc_entries: List[dict]     # 本页对应的书签条目


@dataclass
class PDFExtractResult:
    """整份 PDF 提取结果"""
    doc_path: str
    total_pages: int
    pages: List[PageRecord]
    toc: List[dict]             # 完整书签树：[{level, title, page(0-based), ...}]


HEADER_PATTERN = "臻融数据分发服务DDS 系统软件"
PAGE_OFFSET = 7  # 印刷页码 = 物理页码 + 7（文档第 16 节已确认相差 6，这里按 7 计，后续可配置化）


def extract_pdf(pdf_path: str | Path) -> PDFExtractResult:
    """
    核心入口：逐页提取文本、blocks、书签，返回结构化结果。
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    try:
        # 1. 整份书签
        toc = doc.get_toc(simple=False)  # [[level, title, page, ...], ...]
        toc_entries = [
            {"level": level, "title": title, "physical_page": page - 1}
            for level, title, page, *_ in toc
        ]

        # 2. 逐页提取
        pages: List[PageRecord] = []
        for physical_page in range(doc.page_count):
            page = doc[physical_page]

            # 2.1 纯文本（保留换行）
            text = page.get_text("text")

            # 2.2 blocks 结构（含 bbox、字体、大小等，供后续结构化用）
            blocks = page.get_text("dict")["blocks"]

            # 2.3 本页对应的书签条目
            page_toc = [e for e in toc_entries if e["physical_page"] == physical_page]

            printed_page = physical_page + PAGE_OFFSET
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