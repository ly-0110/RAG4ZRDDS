# G:\DSH workspace\data_pipeline\section_tree.py
"""
双通道章节树构建：
- 通道 1：PDF 书签 (TOC) → 骨架树
- 通道 2：正文排版信号 (字号/加粗/编号正则) → 候选标题
- 交叉验证 → 统一章节树，含物理/印刷页码区间
产物：data/processed/section_tree_v1.jsonl
"""
from __future__ import annotations
import re, json, math
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# ========= 可调参数 =========
FONT_SIZE_TOL = 0.5       # 字号容差（pt）
SIM_THRESHOLD = 0.8       # 标题相似度阈值
PAGE_WINDOW = 1           # 交叉验证页码窗口 ±1
MIN_TITLE_LEN = 2         # 最短标题长度
# ============================

# 编号正则：PART / 章 / 三级节 / 四级节 / 五级节
RE_PART    = re.compile(r'^PART\s+\d+[\s\S]*$')
RE_CHAP    = re.compile(r'^第\s*\d+\s*章[\s\S]*$')
RE_SEC3    = re.compile(r'^\d+\.\d+(\.\d+)?\s')          # 1.1 / 1.1.1
RE_SEC4    = re.compile(r'^\d+\.\d+\.\d+\.\d+\s')       # 1.1.1.1
RE_SEC5    = re.compile(r'^\d+\.\d+\.\d+\.\d+\.\d+\s')  # 1.1.1.1.1

@dataclass
class TitleCandidate:
    physical_page: int
    level: int                # 1~5
    title: str
    font_size: float
    is_bold: bool
    bbox: Tuple[float,float,float,float]

@dataclass
class SectionNode:
    node_id: str
    level: int
    title: str
    part: str = ""
    chapter: str = ""
    section_path: str = ""
    physical_page_start: int = -1
    physical_page_end: int = -1
    printed_page_start: int = -1
    printed_page_end: int = -1
    toc_source: bool = False
    verified_by_text: bool = False
    children: List['SectionNode'] = None  # type: ignore

    def __post_init__(self):
        if self.children is None:
            self.children = []

# ---------- 工具函数 ----------
def _norm(s: str) -> str:
    return re.sub(r'\s+', '', s)

def _sim(a: str, b: str) -> float:
    """简单 Jaccard 相似度（字符级）"""
    sa, sb = set(_norm(a)), set(_norm(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def _level_from_text(title: str) -> Optional[int]:
    """仅按编号正则判定层级"""
    if RE_PART.match(title):  return 1
    if RE_CHAP.match(title):  return 2
    if RE_SEC5.match(title):  return 5
    if RE_SEC4.match(title):  return 4
    if RE_SEC3.match(title):  return 3
    return None

def _gen_id(path_parts: List[str]) -> str:
    return "s_" + "_".join(re.sub(r'[^\w\u4e00-\u9fff]+', '_', p).strip('_') for p in path_parts)

# ---------- 通道 1：TOC ----------
def build_toc_tree(pages: List[dict]) -> List[SectionNode]:
    """把每页的 toc_entries 还原成树（只保留起始页）"""
    nodes_by_page: Dict[int, List[dict]] = defaultdict(list)
    for p in pages:
        for e in p.get("toc_entries", []):
            nodes_by_page[e["physical_page"]].append(e)

    # 书签是扁平列表，按 level 还原父子关系
    root = SectionNode(node_id="root", level=0, title="ROOT")
    stack: List[Tuple[int, SectionNode]] = [(0, root)]  # (level, node)

    for phys_page in sorted(nodes_by_page.keys()):
        printed = pages[phys_page]["printed_page"]
        for e in sorted(nodes_by_page[phys_page], key=lambda x: x["level"]):
            lvl, title = e["level"], e["title"].strip()
            if lvl < 1 or lvl > 5:
                continue
            # 找父节点
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            parent = stack[-1][1]
            node = SectionNode(
                node_id=_gen_id([parent.node_id, title]) if parent.node_id != "root" else _gen_id([title]),
                level=lvl,
                title=title,
                physical_page_start=phys_page,
                physical_page_end=phys_page,   # 先占位，后面补全
                printed_page_start=printed,
                printed_page_end=printed,
                toc_source=True,
            )
            # 继承 part/chapter
            if lvl == 1:
                node.part = title
            elif lvl == 2:
                node.part = parent.part
                node.chapter = title
            else:
                node.part = parent.part
                node.chapter = parent.chapter
            node.section_path = " / ".join([node.part, node.chapter, node.title]) if node.chapter else (node.part + " / " + node.title)
            parent.children.append(node)
            stack.append((lvl, node))
    return root.children

# ---------- 通道 2：正文标题 ----------
def extract_text_titles(pages: List[dict]) -> List[TitleCandidate]:
    """遍历 blocks/spans，按字号+加粗+编号提取候选标题"""
    candidates = []
    # 先统计全文字号分布，取前 3 大作为标题候选阈值
    all_sizes = []
    for p in pages:
        for blk in p.get("blocks", []):
            if blk["type"] != 0: continue
            for line in blk.get("lines", []):
                for sp in line.get("spans", []):
                    all_sizes.append(sp["size"])
    if not all_sizes:
        return candidates
    top_sizes = sorted(set(round(s,1) for s in all_sizes), reverse=True)[:3]
    size_thresh = min(top_sizes) if top_sizes else 12

    for p in pages:
        phys = p["physical_page"]
        for blk in p.get("blocks", []):
            if blk["type"] != 0: continue
            for line in blk.get("lines", []):
                line_text = "".join(sp["text"] for sp in line.get("spans", [])).strip()
                if len(line_text) < MIN_TITLE_LEN: continue
                # 取该行最大字号、是否加粗
                max_sz = max((sp["size"] for sp in line["spans"]), default=0)
                is_bold = any("bold" in sp.get("font","").lower() for sp in line["spans"])
                lvl = _level_from_text(line_text)
                if lvl is None:
                    # 无编号：仅靠字号/加粗判断
                    if max_sz + FONT_SIZE_TOL >= size_thresh and is_bold:
                        lvl = 4  # 视为四级节候选
                    else:
                        continue
                candidates.append(TitleCandidate(
                    physical_page=phys,
                    level=lvl,
                    title=line_text,
                    font_size=max_sz,
                    is_bold=is_bold,
                    bbox=blk["bbox"]
                ))
    return candidates

# ---------- 交叉验证 & 合并 ----------
def match_toc_with_text(toc_nodes: List[SectionNode],
                        text_cands: List[TitleCandidate]) -> List[SectionNode]:
    """把正文候选挂到 TOC 树上，补全结束页、修正层级"""
    # 建立 TOC 扁平列表
    flat: List[SectionNode] = []
    def _flatten(ns):
        for n in ns:
            flat.append(n)
            _flatten(n.children)
    _flatten(toc_nodes)

    # 页码索引
    by_page: Dict[int, List[SectionNode]] = defaultdict(list)
    for n in flat:
        by_page[n.physical_page_start].append(n)

    for cand in text_cands:
        page = cand.physical_page
        # 在 [page-1, page, page+1] 找最佳匹配
        best, best_sim = None, 0
        for p in range(page - PAGE_WINDOW, page + PAGE_WINDOW + 1):
            for n in by_page.get(p, []):
                if n.level != cand.level: continue
                s = _sim(n.title, cand.title)
                if s > best_sim:
                    best, best_sim = n, s
        if best and best_sim >= SIM_THRESHOLD:
            best.verified_by_text = True
            # 结束页暂时不改，后面统一补全
    return toc_nodes

def finalize_page_ranges(nodes: List[SectionNode], total_pages: int):
    """深度优先：子节点的 end = 下一个同级/侄子的 start-1，叶子延伸到父 end"""
    flat = []
    def _dfs(ns):
        for i, n in enumerate(ns):
            n._idx = i
            flat.append(n)
            _dfs(n.children)
    _dfs(nodes)

    # 先按物理页排序
    flat.sort(key=lambda x: x.physical_page_start)

    for i, n in enumerate(flat):
        if n.physical_page_end == n.physical_page_start:  # 仍是占位
            # 找下一个同级或更高级的节点
            nxt = None
            for j in range(i+1, len(flat)):
                if flat[j].level <= n.level:
                    nxt = flat[j]
                    break
            if nxt:
                n.physical_page_end = nxt.physical_page_start - 1
            else:
                n.physical_page_end = total_pages - 1
            n.printed_page_end = n.physical_page_end + 7  # PAGE_OFFSET=7

# ---------- 落盘 ----------
def dump_section_tree(nodes: List[SectionNode], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        def _walk(ns):
            for n in ns:
                rec = {
                    "node_id": n.node_id,
                    "level": n.level,
                    "title": n.title,
                    "part": n.part,
                    "chapter": n.chapter,
                    "section_path": n.section_path,
                    "physical_page_start": n.physical_page_start,
                    "physical_page_end": n.physical_page_end,
                    "printed_page_start": n.printed_page_start,
                    "printed_page_end": n.printed_page_end,
                    "toc_source": n.toc_source,
                    "verified_by_text": n.verified_by_text,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                _walk(n.children)
        _walk(nodes)

# ---------- CLI ----------
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/cleaned/pages.jsonl")
    parser.add_argument("--output", default="data/processed/section_tree_v1.jsonl")
    args = parser.parse_args()

    print(f"[section_tree] 读取 {args.input}")
    pages = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            pages.append(json.loads(line))

    print("[1/4] 构建 TOC 骨架...")
    toc_tree = build_toc_tree(pages)
    print(f"      TOC 节点数: {sum(1 for _ in iter_all(toc_tree))}")

    print("[2/4] 提取正文标题候选...")
    text_cands = extract_text_titles(pages)
    print(f"      候选数: {len(text_cands)}")

    print("[3/4] 交叉验证 & 合并...")
    match_toc_with_text(toc_tree, text_cands)

    print("[4/4] 补全页码区间 & 落盘...")
    finalize_page_ranges(toc_tree, len(pages))
    dump_section_tree(toc_tree, Path(args.output))
    print(f"[section_tree] 完成 → {args.output}")

def iter_all(nodes):
    for n in nodes:
        yield n
        yield from iter_all(n.children)

if __name__ == "__main__":
    main()