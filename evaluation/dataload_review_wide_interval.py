#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1 宽区间语义复核工具 v0.1
功能：
  1. 导出待复核的 69 题（全书级区间）
  2. 对照 PDF 生成 Excel 复核表
  3. 验证 section_keyword 准确性
"""

import json
import csv
import argparse
from pathlib import Path
from collections import defaultdict

# ========== 配置 =========
# 路径一律走仓库根（脚本可从任意 cwd 调用），并可用命令行覆盖——原先 PDF_PATH 硬编码
# 某成员的下载目录，别人跑必崩，且 questions/expected 用相对路径依赖 cwd。
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = REPO_ROOT / "data" / "raw" / "manuals" / "ZRDDS用户手册.pdf"

PDF_PATH = str(DEFAULT_PDF)
QUESTIONS_FILE = str(REPO_ROOT / "evaluation/datasets/questions.jsonl")
EXPECTED_SOURCES_FILE = str(REPO_ROOT / "evaluation/datasets/expected_sources.jsonl")
OUTPUT_CSV = str(REPO_ROOT / "evaluation/datasets/review_wide_interval.csv")
OUTPUT_MD = str(REPO_ROOT / "evaluation/datasets/review_wide_interval.md")
# =========================

def load_questions():
    """加载问题集（JSONL 格式：每行一个 JSON object）"""
    questions = {}
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  # 跳过空行
                q = json.loads(line)
                questions[q['id']] = q
    return questions

def load_expected_sources():
    """加载标注真值"""
    with open(EXPECTED_SOURCES_FILE, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

def identify_wide_interval_items(sources):
    """识别宽区间标注：印刷页区间跨度>100"""
    wide = []
    for item in sources:
        page_print = item.get('page_print')
        # 如果 page_print 不是列表或长度<2，跳过
        if not isinstance(page_print, list) or len(page_print) < 2:
            continue
        # 取印刷页区间的第一个和最后一个页码
        start_page = page_print[0]
        end_page = page_print[-1]  # 取最后一个（最大）页码
        if end_page - start_page > 100:
            wide.append(item)
    return wide

def export_review_sheet():
    """导出复核表到 CSV"""
    sources = load_expected_sources()
    questions = load_questions()
    
    wide_items = identify_wide_interval_items(sources)
    
    print(f"识别出 {len(wide_items)} 个宽区间标注项")
    print(f"PDF 路径：{PDF_PATH}\n")
    
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        
        # 表头
        writer.writerow([
            'question_id', 
            'question_text',
            'source_id',
            'current_page_range_start',
            'current_page_range_end',
            'current_keyword',
            'suggested_keyword',
            'note'
        ])
        
        # 导出数据（前 30 条预览）
        for i, item in enumerate(wide_items[:30]):
            qid = item['question_id']
            question_text = questions.get(qid, {}).get('question', '')
            
            writer.writerow([
                qid,
                question_text[:100] + '...' if len(question_text) > 100 else question_text,
                item.get('source_id', ''),
                item['page_print'][0],
                item['page_print'][-1],
                repr(item.get('section_keyword', '')) if item.get('section_keyword') else 'N/A',
                '',
                ''
            ])

def generate_review_checklist():
    """生成人工复核清单（Markdown 格式）"""
    sources = load_expected_sources()
    questions = load_questions()
    
    wide_items = identify_wide_interval_items(sources)
    
    # 按页码范围分组
    by_page_range = defaultdict(list)
    for item in wide_items:
        key = f"{item['page_print'][0]}-{item['page_print'][-1]}"
        by_page_range[key].append(item)
    
    markdown_content = "# P1 宽区间语义复核清单\n\n"
    markdown_content += f"总题数：{len(wide_items)}\n"
    markdown_content += f"PDF: {PDF_PATH}\n\n"
    markdown_content += "## 待复核项\n\n"
    
    for page_range, items in sorted(by_page_range.items()):
        markdown_content += f"### {page_range} (共 {len(items)} 题)\n\n"
        
        # 读取 PDF 该页的标题（简化版：从 section_tree.jsonl 获取）
        from data_pipeline.section_tree import SectionNode
        
        markdown_content += "| ID | 题干（前 80 字） | Keyword | 建议复核 |\n"
        markdown_content += "|---|---|---|---|\n"
        
        for item in items[:20]:  # 每组只显示前 20 条
            qid = item['question_id']
            text = questions.get(qid, {}).get('question', '')
            kw = item.get('section_keyword', 'N/A') or '未设'
            
            markdown_content += f"| {qid} | `{text[:80]}...` | {kw} | ⚠️ |\n"
        
        if len(items) > 20:
            markdown_content += f"\n*...还有{len(items)-20}题，见 CSV 文件*\n\n"

    # 早先这里只拼字符串不落盘，而 main() 却打印"已生成清单"——把清单写出来。
    Path(OUTPUT_MD).write_text(markdown_content, encoding="utf-8")
    return len(wide_items)


def main(argv=None):
    """主流程"""
    global PDF_PATH, QUESTIONS_FILE, EXPECTED_SOURCES_FILE, OUTPUT_CSV, OUTPUT_MD
    p = argparse.ArgumentParser(description="P1 宽区间语义复核工具（导出复核表 + 清单）")
    p.add_argument("--pdf", default=PDF_PATH, help="对照用的用户手册 PDF（默认仓库内路径）")
    p.add_argument("--questions", default=QUESTIONS_FILE)
    p.add_argument("--expected", default=EXPECTED_SOURCES_FILE)
    p.add_argument("--out-csv", default=OUTPUT_CSV)
    p.add_argument("--out-md", default=OUTPUT_MD)
    args = p.parse_args(argv)
    PDF_PATH, QUESTIONS_FILE = args.pdf, args.questions
    EXPECTED_SOURCES_FILE, OUTPUT_CSV, OUTPUT_MD = args.expected, args.out_csv, args.out_md

    print("=== P1 宽区间语义复核工具 ===\n")
    
    # 步骤 1：导出 CSV
    export_review_sheet()
    print(f"[OK] 已导出：{OUTPUT_CSV}\n")
    
    # 步骤 2：生成 Markdown 清单
    n = generate_review_checklist()
    print(f"[OK] 已生成复核清单（Markdown，{n} 题）：{OUTPUT_MD}\n")
    
    print("\n=== 下一步操作 ===")
    print("1. 打开 review_wide_interval.csv")
    print("2. 对照用户手册 PDF，逐题核验 keyword 准确性")
    print("3. 将正确 keyword 填入 suggested_keyword 列")
    print("4. 运行 python scripts/audit_annotations.py 验证效果\n")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
