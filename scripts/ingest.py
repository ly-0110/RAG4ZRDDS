#!/usr/bin/env python3
"""
scripts/ingest.py — raw → cleaned → processed 编排

职责（成员 D · 集成与实验平台）:
  * 调用成员 A 交付物：pdf_loader（提取）、cleaner（清洗）、section_tree（章节树）
  * 预留 chunker 调用点（待 A 交付 data_pipeline/chunkers/）
  * 各接缝处执行 pages.jsonl 契约校验
  * 失败即停，给出可读错误

用法:
  make ingest                           # 默认配置
  python scripts/ingest.py --config configs/experiments/<实验>.yaml

产物:
  data/cleaned/pages.jsonl     — 逐页清洗文本（含 blocks/toc_entries，供 section_tree 消费）
  data/processed/section_tree_v1.jsonl — 章节树（A 的 section_tree 产出）

依赖: scripts/experiment_config.py · data_pipeline/*.py（A 交付物）
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, List, Dict

# ─── 路径引导 ────────────────────────────────────────────────────────
# 脚本位于 scripts/，上层即项目根
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # 让 from scripts / data_pipeline import 生效

# ─── 契约校验 ────────────────────────────────────────────────────────


def validate_page_record(rec: dict, line_no: int, errors: list[str]) -> None:
    """校验单条 pages.jsonl 记录的必填字段与类型。"""
    # physical_page: int >= 0
    pp = rec.get("physical_page")
    if not isinstance(pp, int) or pp < 0:
        errors.append(f"第{line_no}行: physical_page 应为非负整数，收到 {pp!r}")

    # printed_page: int >= 1
    pr = rec.get("printed_page")
    if not isinstance(pr, int) or pr < 1:
        errors.append(f"第{line_no}行: printed_page 应为正整数，收到 {pr!r}")

    # text: str
    txt = rec.get("text")
    if not isinstance(txt, str):
        errors.append(f"第{line_no}行: text 应为字符串，收到 {txt!r}")

    # toc_entries: list
    toc = rec.get("toc_entries")
    if not isinstance(toc, list):
        errors.append(f"第{line_no}行: toc_entries 应为列表，收到 {toc!r}")

    # blocks: 可选，存在则必须为 list
    blocks = rec.get("blocks")
    if blocks is not None and not isinstance(blocks, list):
        errors.append(f"第{line_no}行: blocks 应为列表或省略，收到 {blocks!r}")


def validate_pages_jsonl(pages: List[dict], label: str = "") -> None:
    """全局校验 pages.jsonl，失败抛 ValueError。"""
    errors: list[str] = []
    for i, rec in enumerate(pages, start=1):
        validate_page_record(rec, i, errors)

    # 页码连续性检查
    phys_pages = [r["physical_page"] for r in pages
                  if isinstance(r.get("physical_page"), int)]
    if phys_pages:
        expected = set(range(phys_pages[0], phys_pages[-1] + 1))
        missing = expected - set(phys_pages)
        if missing:
            # 只报前 10 个
            sample = sorted(missing)[:10]
            errors.append(f"physical_page 不连续，缺失: {sample}{'…' if len(missing) > 10 else ''}")

    # 印刷页码与物理页码的差值一致性检查
    printed_deviation = None
    for r in pages:
        pp = r.get("physical_page")
        pr = r.get("printed_page")
        if isinstance(pp, int) and isinstance(pr, int):
            d = pr - pp
            if printed_deviation is None:
                printed_deviation = d
            elif d != printed_deviation:
                errors.append(
                    f"physical_page={pp} → printed_page={pr}: 差值 {d} 不一致"
                    f"（之前为 {printed_deviation}）"
                )
                break

    if errors:
        summary = "\n  ".join(errors)
        raise ValueError(f"pages.jsonl 契约校验失败（{label}）:\n  {summary}")


# ─── 核心编排 ────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="raw → cleaned → processed 编排",
    )
    parser.add_argument(
        "--config", "-c",
        default="configs/experiments/example_v1.yaml",
        help="实验配置路径 (configs/experiments/*.yaml)",
    )
    parser.add_argument(
        "--skip-section-tree", action="store_true",
        help="跳过章节树构建（仅产出 pages.jsonl）",
    )
    args = parser.parse_args()

    # ── 0. 加载配置 ──────────────────────────────────────────────
    config_path = REPO_ROOT / args.config
    try:
        from scripts.experiment_config import load, nodes_path
        cfg = load(config_path)
    except Exception as e:
        print(f"[ingest] 配置加载失败: {e}", file=sys.stderr)
        return 1
    print(f"[ingest] 配置: {cfg.experiment.name} ({cfg.experiment.stage})")

    # 确定 PDF 来源
    pdf_src: Path | None = None
    for s in cfg.sources:
        if s.type == "pdf":
            pdf_src = REPO_ROOT / s.path
            break
    if pdf_src is None:
        print("[ingest] 错误: 配置 sources 中未找到 type=pdf 的条目", file=sys.stderr)
        return 1
    if not pdf_src.exists():
        print(f"[ingest] 错误: PDF 不存在: {pdf_src}", file=sys.stderr)
        return 1
    print(f"[ingest] PDF 来源: {pdf_src}")

    # ── 1. PDF 提取 ──────────────────────────────────────────────
    print("[ingest] 步骤 1/5: PDF 逐页提取")
    try:
        from data_pipeline.pdf_loader import extract_pdf
        result = extract_pdf(pdf_src)
    except ImportError:
        print("[ingest] 错误: 缺少 data_pipeline.pdf_loader（A 交付物未就绪）",
              file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ingest] PDF 提取失败: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    print(f"  -> {result.total_pages} 页, 书签 {len(result.toc)} 条")

    # ── 2. 清洗 ──────────────────────────────────────────────────
    print("[ingest] 步骤 2/5: 页眉/页码行清洗")
    try:
        from data_pipeline.cleaner import clean_page_text
        for page in result.pages:
            page.text = clean_page_text(page.text)
    except ImportError:
        print("[ingest] 错误: 缺少 data_pipeline.cleaner（A 交付物未就绪）",
              file=sys.stderr)
        return 1

    total_chars = sum(len(p.text) for p in result.pages)
    non_empty = sum(1 for p in result.pages if p.text.strip())
    print(f"  -> 总字符 {total_chars:,}, 非空页 {non_empty}/{result.total_pages}")

    # ── 3. 构建字典列表 & 落盘 pages.jsonl ──────────────────────
    cleaned_output = REPO_ROOT / cfg.ingest.cleaned_output
    print(f"[ingest] 步骤 3/5: 写入 pages.jsonl → {cleaned_output}")
    cleaned_output.parent.mkdir(parents=True, exist_ok=True)

    # full 版（含 blocks，供 section_tree 在内存中使用） —— 不持久化
    pages_full: List[dict] = []
    for p in result.pages:
        rec = {
            "physical_page": p.physical_page,
            "printed_page": p.printed_page,
            "text": p.text,
            "toc_entries": p.toc_entries,
            "blocks": p.blocks,          # 含 PyMuPDF 图像字节，不可 JSON 序列化
        }
        pages_full.append(rec)

    # 落盘版去掉 blocks（compact + 避免序列化 bytes 报错）
    pages_compact = [
        {k: v for k, v in rec.items() if k != "blocks"}
        for rec in pages_full
    ]
    with cleaned_output.open("w", encoding="utf-8") as f:
        for rec in pages_compact:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"  -> 已写入 {len(pages_compact)} 行（blocks 已剥离）")

    # ── 4. 契约校验 ──────────────────────────────────────────────
    print("[ingest] 步骤 4/5: pages.jsonl 契约校验")
    try:
        validate_pages_jsonl(pages_compact, label=str(cleaned_output))
    except ValueError as e:
        print(f"[ingest] {e}", file=sys.stderr)
        return 1
    print("  -> 校验通过 ✓")

    # ── 5. 章节树构建 ────────────────────────────────────────────
    if args.skip_section_tree:
        print("[ingest] 步骤 5/5: [跳过 --skip-section-tree]")
    else:
        print("[ingest] 步骤 5/5: 双通道章节树构建")
        try:
            from data_pipeline.section_tree import (
                build_toc_tree,
                extract_text_titles,
                match_toc_with_text,
                finalize_page_ranges,
                dump_section_tree,
            )

            # 通道 1：TOC 书签骨架
            toc_tree = build_toc_tree(pages_full)
            # 通道 2：正文标题候选
            text_cands = extract_text_titles(pages_full)
            # 交叉验证
            match_toc_with_text(toc_tree, text_cands)
            # 补全页码范围
            finalize_page_ranges(toc_tree, len(pages_full))

            sec_tree_path = REPO_ROOT / "data/processed" / "section_tree_v1.jsonl"
            dump_section_tree(toc_tree, sec_tree_path)

            # 统计节点数
            def _count(nodes):
                c = 0
                for n in nodes:
                    c += 1
                    c += _count(n.children)
                return c
            total_nodes = _count(toc_tree)
            print(f"  -> 章节树写入 {sec_tree_path} ({total_nodes} 节点)")
        except ImportError:
            print("  -> data_pipeline.section_tree 未就绪（A 交付物缺失），跳过")
        except Exception as e:
            print(f"[ingest] 章节树构建异常: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return 1

    # ── [预留] 6. 分块构建 ────────────────────────────────────────
    chunker_dir = REPO_ROOT / "data_pipeline" / "chunkers"
    if chunker_dir.is_dir():
        print("[ingest] [预留] 检测到 chunkers/ 目录，尝试分块 …")
        try:
            # 动态探查：看 structure.py 是否存在
            if (chunker_dir / "structure.py").exists():
                nodes_out = nodes_path(cfg)
                nodes_out.parent.mkdir(parents=True, exist_ok=True)
                print(f"  -> structure chunker 可用 → 输出 {nodes_out}")
                # TODO: 待 A 会签 chunker 接口签名后取消注释
                # from data_pipeline.chunkers.structure import chunk
                # chunk(pages=pages_full, tree=toc_tree, output=nodes_out)
            else:
                print("  -> chunkers/ 目录存在但未找到 structure.py, 跳过")
        except Exception as e:
            print(f"  -> 分块调用异常: {e}", file=sys.stderr)
            # 不阻断 —— 分块尚在开发
    else:
        print("[ingest] [预留] chunkers/ 未就绪（A 尚未交付），跳过分块")

    # ── 完成 ──────────────────────────────────────────────────────
    print(f"\n[ingest] ✓ 完成。产物:")
    print(f"   pages.jsonl   → {cleaned_output}")
    sec_p = REPO_ROOT / "data/processed/section_tree_v1.jsonl"
    if sec_p.exists():
        print(f"   section_tree  → {sec_p}")
    print(f"   配置          → {args.config}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    raise SystemExit(main())