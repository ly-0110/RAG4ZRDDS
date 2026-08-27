#!/usr/bin/env python3
"""
scripts/ingest.py — raw → cleaned → processed 编排

职责（成员 D · 集成与实验平台）:
  * 调用成员 A 交付物：pdf_loader（提取）、cleaner（清洗）、section_tree（章节树）
  * 调用成员 A 分块交付物：chunkers.get_chunker 工厂 + Chunk.to_dict 落盘
  * 各接缝处执行契约校验（pages.jsonl / Node 集）
  * 失败即停，给出可读错误

用法:
  make ingest                           # 默认配置
  python scripts/ingest.py --config configs/experiments/<实验>.yaml

产物:
  data/cleaned/pages.jsonl     — 逐页清洗文本（落盘版剥离 blocks）
  data/processed/section_tree_v1.jsonl — 章节树（A 的 section_tree 产出）
  data/processed/{method}_{version}.jsonl — Node 集（A 的 chunker 产出，
      路径由配置派生；配置含 ingest.quality_check: true 时附跑质检报告）

依赖: scripts/experiment_config.py · data_pipeline/*.py（A 交付物）· tiktoken
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


def validate_nodes_jsonl(records: List[dict], label: str = "") -> None:
    """校验 Node 集（chunker 产物）契约，失败抛 ValueError。

    顶层字段与 metadata 白名单以 A 的交付物为单一事实源：
    data_pipeline/chunkers/base.py::Chunk / data_pipeline/metadata.py
    """
    from data_pipeline.metadata import validate_metadata

    top_fields = ("chunk_id", "text", "metadata", "token_count",
                  "char_start", "char_end")
    errors: list[str] = []
    ids: set[str] = set()
    delta = None
    for i, rec in enumerate(records, start=1):
        missing = [f for f in top_fields if f not in rec]
        if missing:
            errors.append(f"第{i}条: 缺顶层字段 {missing}")
            continue
        cid = rec["chunk_id"]
        if not isinstance(cid, str) or not cid:
            errors.append(f"第{i}条: chunk_id 非法: {cid!r}")
        elif cid in ids:
            errors.append(f"第{i}条: chunk_id 重复: {cid}")
        ids.add(cid)
        if not isinstance(rec["text"], str) or not rec["text"].strip():
            errors.append(f"第{i}条 ({cid}): text 为空")
        miss_meta = validate_metadata(rec["metadata"])
        if miss_meta:
            errors.append(f"第{i}条 ({cid}): metadata 缺必填字段 {miss_meta}")
        # 双页码差值全局一致（抓 PAGE_OFFSET 配置错误）
        md = rec["metadata"]
        pp, pr = md.get("physical_page_start"), md.get("printed_page_start")
        if isinstance(pp, int) and isinstance(pr, int):
            d = pr - pp
            if delta is None:
                delta = d
            elif d != delta:
                errors.append(f"第{i}条 ({cid}): 双页码差值 {d} 不一致（之前为 {delta}）")
                break

    if errors:
        summary = "\n  ".join(errors[:20])
        more = f"\n  …（共 {len(errors)} 条，仅显示前 20）" if len(errors) > 20 else ""
        raise ValueError(f"Node 集契约校验失败（{label}）:\n  {summary}{more}")


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
    print("[ingest] 步骤 1/6: PDF 逐页提取")
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
    print("[ingest] 步骤 2/6: 页眉/页码行清洗")
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
    print(f"[ingest] 步骤 3/6: 写入 pages.jsonl → {cleaned_output}")
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
    print("[ingest] 步骤 4/6: pages.jsonl 契约校验")
    try:
        validate_pages_jsonl(pages_compact, label=str(cleaned_output))
    except ValueError as e:
        print(f"[ingest] {e}", file=sys.stderr)
        return 1
    print("  -> 校验通过 ✓")

    # ── 5. 章节树构建 ────────────────────────────────────────────
    sec_tree_path = REPO_ROOT / "data/processed" / "section_tree_v1.jsonl"
    if args.skip_section_tree:
        print("[ingest] 步骤 5/6: [跳过 --skip-section-tree]")
    else:
        print("[ingest] 步骤 5/6: 双通道章节树构建")
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

    # ── 6. 分块构建（A 的 chunkers 交付物）────────────────────────
    print("[ingest] 步骤 6/6: 分块构建")
    STRATEGY_MAP = {"struct": "structure", "semantic": "semantic",
                    "hybrid": "hybrid"}
    method = cfg.chunking.method
    if method not in STRATEGY_MAP:
        print(f"[ingest] 错误: chunking.method={method} 无对应 chunker 实现"
              f"（当前支持: {', '.join(STRATEGY_MAP)}）", file=sys.stderr)
        return 1
    strategy = STRATEGY_MAP[method]

    if not sec_tree_path.exists():
        print(f"[ingest] 错误: 章节树不存在: {sec_tree_path}"
              f"（分块依赖章节树，请去掉 --skip-section-tree 重跑）",
              file=sys.stderr)
        return 1

    try:
        from data_pipeline.chunkers.base import get_chunker
    except ImportError as e:
        print(f"[ingest] 错误: data_pipeline.chunkers 无法导入（{e}）。"
              f"检查 A 交付物是否已合并、tiktoken 是否已安装。",
              file=sys.stderr)
        return 1

    strategy_file = REPO_ROOT / "data_pipeline" / "chunkers" / f"{strategy}.py"
    if not strategy_file.exists():
        print(f"[ingest] 错误: data_pipeline/chunkers/{strategy}.py 尚未交付"
              f"（chunking.method={method}）", file=sys.stderr)
        return 1

    # 章节树扁平 JSONL —— A 的 chunker 消费 List[dict]
    with sec_tree_path.open(encoding="utf-8") as f:
        tree_records = [json.loads(line) for line in f if line.strip()]

    nodes_out = nodes_path(cfg)
    try:
        chunker = get_chunker(strategy, dict(cfg.chunking.params))
        chunks = chunker.chunk(pages_compact, tree_records)
    except Exception as e:
        print(f"[ingest] 分块器运行失败: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    if not chunks:
        print(f"[ingest] 错误: 分块器产出 0 个 chunk"
              f"（输入 {len(pages_compact)} 页 / {len(tree_records)} 个树节点）",
              file=sys.stderr)
        return 1

    node_records = [c.to_dict() for c in chunks]
    nodes_out.parent.mkdir(parents=True, exist_ok=True)
    with nodes_out.open("w", encoding="utf-8") as f:
        for rec in node_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    try:
        validate_nodes_jsonl(node_records, label=str(nodes_out))
    except ValueError as e:
        print(f"[ingest] {e}", file=sys.stderr)
        return 1

    lens = [len(rec["text"]) for rec in node_records]
    print(f"  -> {len(node_records)} 个 chunk → {nodes_out}")
    print(f"  -> 长度: min={min(lens)}, max={max(lens)}, "
          f"avg={sum(lens) // len(lens)}；契约校验通过 ✓")

    # 质检（指南 §16 清单；配置 ingest.quality_check 开关）
    if cfg.ingest.quality_check:
        try:
            from data_pipeline.quality_check import check_nodes
            check_nodes(chunks, verbose=True)
        except Exception as e:
            print(f"[ingest] 警告: 质检未能执行（不影响产物落盘）: {e}",
                  file=sys.stderr)

    # ── 完成 ──────────────────────────────────────────────────────
    print(f"\n[ingest] ✓ 完成。产物:")
    print(f"   pages.jsonl   → {cleaned_output}")
    if sec_tree_path.exists():
        print(f"   section_tree  → {sec_tree_path}")
    print(f"   Node 集       → {nodes_path(cfg)}")
    print(f"   配置          → {args.config}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    raise SystemExit(main())