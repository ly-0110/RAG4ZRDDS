#!/usr/bin/env python3
"""
scripts/ingest.py — raw → cleaned → processed 编排（多来源注册式，指南 §7）

职责（成员 D · 集成与实验平台）:
  * 按实验配置 sources[] 注册表逐来源分派 loader：
      pdf  → A 的 pdf_loader / cleaner / section_tree / chunkers（既有六步链路）
      html → A 的 html_loader.load_html_nodes（第三周接缝，未交付前给可读错误）
  * 各来源独立分块落盘中间产物，合并为统一 Node 集（指南 §7.4 Unified Nodes）
  * 各接缝处执行契约校验（pages.jsonl / 合并 Node 集：按来源分型），失败即停
    给出可读错误；校验通过后才落盘，坏产物不会覆盖既有好产物

来源注册约定（configs/experiments/*.yaml 的 sources）:
  每个来源声明 id / type(pdf|html) / path / version / url(html 必填)。
  合并校验强制跨域一致性：
    * metadata.source_id 必须等于注册 id（抓 loader 错挂来源）
    * 注册声明了 version 时 metadata.version 必须一致（抓 2.0/2.4 错配）
    * 双页码差值按 source_id 分组校验（多 PDF 来源可各有偏移）

html_loader 接缝（成员 A 交付物，期望签名）:
  load_html_nodes(source_path: Path, *, source_id: str, version: str,
                  base_url: str, chunk_params: dict) -> List[dict]
  每条 = Chunk.to_dict() 同款顶层结构（chunk_id/text/metadata/token_count/
  char_start/char_end），metadata 经 data_pipeline.metadata.build_chunk_metadata
  构建（source_type="html"：双页码 None、source_url 必填、title 必填）。

用法:
  make ingest                           # 默认配置（单来源 struct_v1 基线）
  python scripts/ingest.py --config configs/experiments/<实验>.yaml

产物:
  data/cleaned/pages.jsonl              — 单来源配置的逐页清洗文本；
                                          多来源配置按来源拆分 pages_{source_id}.jsonl
  data/processed/section_tree_v1.jsonl  — 单来源配置的章节树；
                                          多来源配置按来源拆分 section_tree_{source_id}.jsonl
  data/processed/{method}_{version}.jsonl          — 单来源合并 Node 集（既有命名不变）
  data/processed/{method}_{version}__{src8}.jsonl  — 多来源合并 Node 集（见 experiment_config.nodes_path）

依赖: scripts/experiment_config.py · data_pipeline/*.py（A 交付物）· tiktoken
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

# ─── 路径引导 ────────────────────────────────────────────────────────
# 脚本位于 scripts/，上层即项目根
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # 让 from scripts / data_pipeline import 生效

STRATEGY_MAP = {"struct": "structure", "semantic": "semantic",
                "hybrid": "hybrid"}

# ─── 契约校验 ────────────────────────────────────────────────────────


def validate_page_record(rec: dict, line_no: int, errors: list[str]) -> None:
    """校验单条 pages.jsonl 记录的必填字段与类型。"""
    # physical_page: int >= 1（1 基，与 PDF 阅读器一致）
    pp = rec.get("physical_page")
    if not isinstance(pp, int) or pp < 1:
        errors.append(f"第{line_no}行: physical_page 应为 >=1 的整数，收到 {pp!r}")

    # printed_page: int >= 1 或 None（前言罗马数字页无阿拉伯印刷页码）
    pr = rec.get("printed_page")
    if pr is not None and (not isinstance(pr, int) or pr < 1):
        errors.append(f"第{line_no}行: printed_page 应为正整数或 None，收到 {pr!r}")

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


def validate_nodes_jsonl(
    records: List[dict],
    label: str = "",
    registered_sources: Dict[str, Any] | None = None,
) -> None:
    """校验合并 Node 集契约，失败抛 ValueError。

    顶层字段与 metadata 白名单以 A 的交付物为单一事实源：
    data_pipeline/chunkers/base.py::Chunk / data_pipeline/metadata.py
    （validate_metadata 本身按 source_type 分型：pdf 强制双页码 int，
    html 强制 source_url/title 非空、页码可 None）。

    registered_sources 提供时（ingest 主链路）追加跨域注册一致性校验：
      * metadata.source_id 必须是注册 id（抓 loader 错挂来源）
      * 注册声明了 version 时 metadata.version 必须一致（抓 2.0/2.4 错配）
      * 双页码差值按 source_id 分组一致（多 PDF 来源可各有偏移；
        单来源与既有全局差值校验行为等价）
    """
    from data_pipeline.metadata import validate_metadata

    top_fields = ("chunk_id", "text", "metadata", "token_count",
                  "char_start", "char_end")
    errors: list[str] = []
    ids: set[str] = set()
    deltas: Dict[str, int] = {}
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
        md = rec["metadata"]
        miss_meta = validate_metadata(md)
        if miss_meta:
            errors.append(f"第{i}条 ({cid}): metadata 缺必填/非法字段 {miss_meta}")
        sid = md.get("source_id") or ""
        if registered_sources is not None:
            src = registered_sources.get(sid)
            if src is None:
                errors.append(
                    f"第{i}条 ({cid}): source_id={sid!r} 未在配置 sources 注册"
                )
            elif src.version and md.get("version") != src.version:
                errors.append(
                    f"第{i}条 ({cid}): version={md.get('version')!r} 与注册 "
                    f"version={src.version!r} 不一致（来源 {sid}）"
                )
        # 双页码差值按来源分组一致（抓 PAGE_OFFSET 配置错误；HTML 无页码自然跳过）
        pp, pr = md.get("physical_page_start"), md.get("printed_page_start")
        if isinstance(pp, int) and isinstance(pr, int):
            d = pr - pp
            prev = deltas.get(sid)
            if prev is None:
                deltas[sid] = d
            elif d != prev:
                errors.append(
                    f"第{i}条 ({cid}): source_id={sid} 双页码差值 {d} "
                    f"与该来源此前 {prev} 不一致"
                )
                if len(errors) > 20:
                    break

    if errors:
        summary = "\n  ".join(errors[:20])
        more = f"\n  …（共 {len(errors)} 条，仅显示前 20）" if len(errors) > 20 else ""
        raise ValueError(f"Node 集契约校验失败（{label}）:\n  {summary}{more}")


# ─── 来源处理 ────────────────────────────────────────────────────────


def _pdf_artifacts(source, cfg) -> tuple[Path, Path]:
    """单来源配置沿用既有产物名（兼容 Week2 冻结路径）；多来源按来源拆分。"""
    if len(cfg.sources) > 1:
        pages_out = REPO_ROOT / "data" / "cleaned" / f"pages_{source.id}.jsonl"
        sec_tree_path = REPO_ROOT / "data" / "processed" / f"section_tree_{source.id}.jsonl"
    else:
        pages_out = REPO_ROOT / cfg.ingest.cleaned_output
        sec_tree_path = REPO_ROOT / "data" / "processed" / "section_tree_v1.jsonl"
    return pages_out, sec_tree_path


def _process_pdf_source(source, cfg, pages_out: Path,
                        sec_tree_path: Path, skip_section_tree: bool,
                        ) -> tuple[List[dict], List[dict]]:
    """对单个 PDF 来源执行步骤 1~5：提取→清洗→pages.jsonl→校验→章节树。

    返回 (pages_compact, tree_records)；失败抛 RuntimeError（main 统一转退出）。
    """
    print(f"[ingest] 步骤 1/6: PDF 逐页提取（{source.id}）")
    try:
        from data_pipeline.pdf_loader import extract_pdf
        result = extract_pdf(REPO_ROOT / source.path)
    except ImportError:
        raise RuntimeError("缺少 data_pipeline.pdf_loader（A 交付物未就绪）")
    except Exception as e:
        raise RuntimeError(f"PDF 提取失败: {e}") from e
    print(f"  -> {result.total_pages} 页, 书签 {len(result.toc)} 条")
    if getattr(result, "printed_page_anomalies", None):
        anom = result.printed_page_anomalies
        print(f"[ingest] 警告: {len(anom)} 页的页眉印刷页码偏离 "
              f"printed = physical + PAGE_OFFSET 公式: {anom[:10]}"
              f"{'…' if len(anom) > 10 else ''}（以页眉真值为准）",
              file=sys.stderr)

    print("[ingest] 步骤 2/6: 页眉/页码行清洗")
    try:
        from data_pipeline.cleaner import clean_page_text
        for page in result.pages:
            page.text = clean_page_text(page.text)
    except ImportError:
        raise RuntimeError("缺少 data_pipeline.cleaner（A 交付物未就绪）")

    total_chars = sum(len(p.text) for p in result.pages)
    non_empty = sum(1 for p in result.pages if p.text.strip())
    print(f"  -> 总字符 {total_chars:,}, 非空页 {non_empty}/{result.total_pages}")

    print(f"[ingest] 步骤 3/6: 写入 pages.jsonl → {pages_out}")
    pages_out.parent.mkdir(parents=True, exist_ok=True)

    # full 版（含 blocks，供 section_tree 在内存中使用） —— 不持久化
    pages_full: List[dict] = []
    for p in result.pages:
        pages_full.append({
            "physical_page": p.physical_page,
            "printed_page": p.printed_page,
            "text": p.text,
            "toc_entries": p.toc_entries,
            "blocks": p.blocks,          # 含 PyMuPDF 图像字节，不可 JSON 序列化
        })

    # 落盘版去掉 blocks（compact + 避免序列化 bytes 报错）
    pages_compact = [
        {k: v for k, v in rec.items() if k != "blocks"}
        for rec in pages_full
    ]
    with pages_out.open("w", encoding="utf-8") as f:
        for rec in pages_compact:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"  -> 已写入 {len(pages_compact)} 行（blocks 已剥离）")

    print("[ingest] 步骤 4/6: pages.jsonl 契约校验")
    try:
        validate_pages_jsonl(pages_compact, label=str(pages_out))
    except ValueError as e:
        raise RuntimeError(str(e))
    print("  -> 校验通过 ✓")

    if skip_section_tree:
        print("[ingest] 步骤 5/6: [跳过 --skip-section-tree]")
        return pages_compact, []

    print("[ingest] 步骤 5/6: 双通道章节树构建")
    try:
        from data_pipeline.section_tree import (
            build_toc_tree,
            extract_text_titles,
            match_toc_with_text,
            finalize_page_ranges,
            attach_heading_offsets,
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
        # 标题页内偏移（页内切分依据；pages_full 文本此时已清洗）
        heading_miss = attach_heading_offsets(toc_tree, pages_full)

        sec_tree_path.parent.mkdir(parents=True, exist_ok=True)
        dump_section_tree(toc_tree, sec_tree_path)

        # 统计节点数
        def _count(nodes):
            c = 0
            for n in nodes:
                c += 1
                c += _count(n.children)
            return c
        total_nodes = _count(toc_tree)
        print(f"  -> 章节树写入 {sec_tree_path} ({total_nodes} 节点，"
              f"标题偏移未定位 {heading_miss})")
    except ImportError:
        raise RuntimeError("data_pipeline.section_tree 未就绪（A 交付物缺失）")
    except Exception as e:
        raise RuntimeError(f"章节树构建异常: {e}") from e

    tree_records: List[dict] = []
    with sec_tree_path.open(encoding="utf-8") as f:
        tree_records = [json.loads(line) for line in f if line.strip()]
    return pages_compact, tree_records


def _process_html_source(source, cfg) -> List[dict]:
    """HTML 来源经 A 的 html_loader 产出节点记录（接缝见模块 docstring）。"""
    try:
        from data_pipeline.html_loader import load_html_nodes
    except ImportError as e:
        raise RuntimeError(
            f"来源 {source.id!r}（type=html）需要成员 A 的 html_loader 交付物："
            "data_pipeline/html_loader.py 尚未就绪。期望接口 "
            "load_html_nodes(source_path, *, source_id, version, base_url, "
            "chunk_params) -> List[dict]（Chunk.to_dict 同款顶层结构，metadata 经 "
            "build_chunk_metadata 构建，source_type=html）。接到交付前请勿在配置 "
            "中注册 html 来源。"
        ) from e
    records = load_html_nodes(
        REPO_ROOT / source.path,
        source_id=source.id,
        version=source.version or "",
        base_url=source.url or "",
        chunk_params=dict(cfg.chunking.params),
    )
    if not records:
        raise RuntimeError(f"来源 {source.id!r}: html_loader 产出 0 个节点")
    return records


# ─── 核心编排 ────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="raw → cleaned → processed 编排（多来源注册式）",
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
    print(f"[ingest] 来源注册表: {', '.join(f'{s.id}({s.type})' for s in cfg.sources)}")

    # 分块器就绪检查（所有 PDF 来源共用同一 chunking 配置，工厂只建一次）
    method = cfg.chunking.method
    if method not in STRATEGY_MAP:
        print(f"[ingest] 错误: chunking.method={method} 无对应 chunker 实现"
              f"（当前支持: {', '.join(STRATEGY_MAP)}）", file=sys.stderr)
        return 1
    strategy = STRATEGY_MAP[method]
    strategy_file = REPO_ROOT / "data_pipeline" / "chunkers" / f"{strategy}.py"
    if not strategy_file.exists():
        print(f"[ingest] 错误: data_pipeline/chunkers/{strategy}.py 尚未交付"
              f"（chunking.method={method}）", file=sys.stderr)
        return 1
    try:
        from data_pipeline.chunkers.base import get_chunker
    except ImportError as e:
        print(f"[ingest] 错误: data_pipeline.chunkers 无法导入（{e}）。"
              f"检查 A 交付物是否已合并、tiktoken 是否已安装。",
              file=sys.stderr)
        return 1
    chunker = get_chunker(strategy, dict(cfg.chunking.params))

    registered = {s.id: s for s in cfg.sources}

    # ── 1~6. 逐来源处理 ──────────────────────────────────────────
    all_node_records: List[dict] = []
    all_chunks: List[Any] = []  # 质检消费 Chunk 对象；仅 PDF 来源产出
    for si, source in enumerate(cfg.sources, start=1):
        print(f"\n[ingest] ══ 来源 {si}/{len(cfg.sources)}: "
              f"{source.id}（type={source.type}）══")
        try:
            if source.type == "pdf":
                if not (REPO_ROOT / source.path).exists():
                    raise RuntimeError(f"PDF 不存在: {REPO_ROOT / source.path}")
                pages_out, sec_tree_path = _pdf_artifacts(source, cfg)
                pages_compact, tree_records = _process_pdf_source(
                    source, cfg, pages_out, sec_tree_path, args.skip_section_tree,
                )
                print("[ingest] 步骤 6/6: 分块构建")
                if not args.skip_section_tree and not sec_tree_path.exists():
                    raise RuntimeError(
                        f"章节树不存在: {sec_tree_path}"
                        "（分块依赖章节树，请去掉 --skip-section-tree 重跑）"
                    )
                chunks = chunker.chunk(pages_compact, tree_records)
                if not chunks:
                    raise RuntimeError(
                        f"分块器产出 0 个 chunk"
                        f"（输入 {len(pages_compact)} 页 / {len(tree_records)} 个树节点）"
                    )
                print(f"  -> {len(chunks)} 个 chunk（{source.id}）")
                all_chunks.extend(chunks)
                all_node_records.extend(c.to_dict() for c in chunks)
            elif source.type == "html":
                records = _process_html_source(source, cfg)
                print(f"  -> {len(records)} 个节点（html_loader 产出）")
                all_node_records.extend(records)
            else:  # pragma: no cover —— SourceCfg Literal 已挡，防御性兜底
                raise RuntimeError(f"未知来源类型: {source.type!r}")
        except RuntimeError as e:
            print(f"[ingest] 错误（来源 {source.id}）: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"[ingest] 未预期异常（来源 {source.id}）: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return 1

    if not all_node_records:
        print("[ingest] 错误: 所有来源合计产出 0 个节点", file=sys.stderr)
        return 1

    # ── 合并校验（先校验后落盘：坏合并不得覆盖既有好产物）──────────
    nodes_out = nodes_path(cfg)
    print(f"\n[ingest] 合并 Node 集: {len(all_node_records)} 条 → {nodes_out}")
    try:
        validate_nodes_jsonl(
            all_node_records, label=str(nodes_out), registered_sources=registered,
        )
    except ValueError as e:
        print(f"[ingest] {e}", file=sys.stderr)
        return 1
    print("  -> 契约校验通过 ✓（含来源注册一致性）")

    nodes_out.parent.mkdir(parents=True, exist_ok=True)
    with nodes_out.open("w", encoding="utf-8") as f:
        for rec in all_node_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    lens = [len(rec["text"]) for rec in all_node_records]
    print(f"  -> 长度: min={min(lens)}, max={max(lens)}, avg={sum(lens) // len(lens)}")

    # 质检（指南 §16 清单；配置 ingest.quality_check 开关）
    # 仅覆盖 Chunk 对象来源（PDF）；HTML 节点由 loader 自检 + 上方契约校验覆盖。
    if cfg.ingest.quality_check and all_chunks:
        try:
            from data_pipeline.quality_check import check_nodes
            check_nodes(all_chunks, verbose=True)
        except Exception as e:
            print(f"[ingest] 警告: 质检未能执行（不影响产物落盘）: {e}",
                  file=sys.stderr)
    elif cfg.ingest.quality_check:
        print("[ingest] 质检跳过：无 PDF Chunk 来源（HTML 节点由 loader 自检 + 契约校验覆盖）")

    # ── 完成 ──────────────────────────────────────────────────────
    print(f"\n[ingest] ✓ 完成。产物:")
    for source in cfg.sources:
        if source.type == "pdf":
            pages_out, sec_tree_path = _pdf_artifacts(source, cfg)
            print(f"   pages.jsonl   → {pages_out}")
            if sec_tree_path.exists():
                print(f"   section_tree  → {sec_tree_path}")
    print(f"   Node 集       → {nodes_out}")
    print(f"   配置          → {args.config}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    raise SystemExit(main())
