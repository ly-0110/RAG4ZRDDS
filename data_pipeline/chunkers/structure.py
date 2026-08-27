# G:\DSH workspace\data_pipeline\chunkers\structure.py
"""
结构感知 Chunking（方案 A）：
- 三级节为知识单元
- 超大节沿四/五级子节下切
- 代码/表格/图片原子保护
- Metadata 统一由 metadata.py 构建
产出：data/processed/struct_v1.jsonl
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Tuple
from data_pipeline.chunkers.base import BaseChunker, Chunk
from data_pipeline.metadata import build_chunk_metadata, validate_metadata

# ---------- 正则：原子块保护 ----------
CODE_BLOCK_RE = re.compile(r'(```[\s\S]*?```)')
TABLE_RE      = re.compile(r'(\|.*?\|(?:\n\|.*?\|)+)')
IMG_RE        = re.compile(r'(\!\[.*?\]\(.*?\))')
ATOMIC_RE = re.compile(
    r'(```[\s\S]*?```|\|.*?\|(?:\n\|.*?\|)+|\!\[.*?\]\(.*?\))'
)


def _norm_text(s: str) -> str:
    """去空白归一化（用于标题对比）"""
    return re.sub(r'\s+', '', s)

class StructureChunker(BaseChunker):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.max_chars = config.get("max_chunk_chars", 2500)
        self.overlap   = config.get("overlap_chars", 200)
        self.large_thresh = config.get("large_section_thresh", self.max_chars)

    # ========== 主入口 ==========
    def chunk(self, pages: List[dict], section_tree: List[dict]) -> List[Chunk]:
        page_texts = {p["physical_page"]: p["text"] for p in pages}
        page_printed = {p["physical_page"]: p["printed_page"] for p in pages}
        flat_nodes = self._flatten_tree(section_tree)
        tree_map = {n["node_id"]: n for n in flat_nodes}

        # 文档序中每个节点的下一边界：第一个 level ≤ 自身的后继节点
        # （即其内容终点；D1/D2 修复——边界按页内标题偏移计）
        boundary_map: Dict[str, Any] = {}
        for i, n in enumerate(flat_nodes):
            boundary_map[n["node_id"]] = self._next_boundary(flat_nodes, i)

        all_chunks: List[Chunk] = []
        for node in flat_nodes:
            if node["level"] != 3:
                continue
            chunks = self._process_section_node(node, page_texts, page_printed,
                                                tree_map, boundary_map)
            all_chunks.extend(chunks)

        # 最终校验
        for c in all_chunks:
            missing = validate_metadata(c.metadata)
            if missing:
                raise ValueError(f"Chunk {c.chunk_id} 缺失元数据: {missing}")
        return all_chunks

    # ========== 单个三级节处理 ==========
    def _process_section_node(self, node: dict, page_texts: dict,
                              page_printed: dict, tree_map: dict,
                              boundary_map: dict) -> List[Chunk]:
        raw_text = self._extract_node_text(node, boundary_map.get(node["node_id"]),
                                           page_texts)
        if not raw_text.strip():
            return []

        segments = self._split_atomic(raw_text)
        chunks = self._assemble_chunks(segments, node, page_printed)

        total_len = sum(len(c.text) for c in chunks)
        if total_len > self.large_thresh:
            sub_chunks = self._split_by_subsections(node, page_texts, page_printed,
                                                     tree_map, boundary_map)
            if sub_chunks:
                return sub_chunks
        return chunks

    # ========== 文本提取（标题偏移感知） ==========
    @staticmethod
    def _node_start_pos(node: dict) -> Tuple[int, int]:
        """节点内容起点（物理页, 页内字符偏移）；未定位到标题时回退整页开头"""
        pg = node.get("heading_physical_page", -1)
        off = node.get("heading_char_offset", -1)
        if isinstance(pg, int) and pg >= 0 and isinstance(off, int) and off >= 0:
            return pg, off
        return node["physical_page_start"], 0

    @staticmethod
    def _next_boundary(flat_nodes: List[dict], idx: int):
        """文档序中第一个 level ≤ flat_nodes[idx] 的后继节点（内容终点边界）"""
        lvl = flat_nodes[idx]["level"]
        for j in range(idx + 1, len(flat_nodes)):
            if flat_nodes[j]["level"] <= lvl:
                return flat_nodes[j]
        return None

    @staticmethod
    def _heading_sort_key(node: dict) -> Tuple[int, int]:
        pg = node.get("heading_physical_page", -1)
        off = node.get("heading_char_offset", 0)
        if not isinstance(pg, int) or pg < 0:
            pg = node["physical_page_start"]
        if not isinstance(off, int) or off < 0:
            off = 0
        return (pg, off)

    def _extract_node_text(self, node: dict, boundary: Any, page_texts: dict) -> str:
        """按 [标题偏移, 下一边界标题偏移) 提取节点正文（跨页拼接）。
        边界缺省为节点末页文末；未定位标题的一端回退整页粒度。"""
        s_pg, s_off = self._node_start_pos(node)
        e_pg = node["physical_page_end"]
        e_off = len(page_texts.get(e_pg, ""))
        if boundary is not None:
            b_pg, b_off = self._node_start_pos(boundary)
            if (b_pg, b_off) < (e_pg, e_off):
                e_pg, e_off = b_pg, b_off
        if (e_pg, e_off) < (s_pg, s_off):
            e_pg, e_off = s_pg, s_off
        parts = []
        for pg in range(s_pg, e_pg + 1):
            txt = page_texts.get(pg, "")
            lo = s_off if pg == s_pg else 0
            hi = e_off if pg == e_pg else len(txt)
            lo, hi = min(lo, len(txt)), min(hi, len(txt))
            seg = txt[lo:hi].strip()
            if seg:
                parts.append(seg)
        return "\n\n".join(parts)

    # ========== 超长非原子段兜底切分（结构信号，不涉语义） ==========
    def _split_long_segment(self, seg: str) -> List[str]:
        pieces: List[str] = []
        start = 0
        while start < len(seg):
            end = min(start + self.max_chars, len(seg))
            if end < len(seg):
                boundary = -1
                for sep in ("\n\n", "\n", "。", "；", ".", ";"):
                    pos = seg.rfind(sep, start, end)
                    if pos > start + self.max_chars // 2:
                        boundary = pos + len(sep)
                        break
                if boundary == -1:
                    boundary = end
                end = boundary
            pieces.append(seg[start:end])
            start = end
        return [p for p in pieces if p.strip()]

    # ========== 原子块感知切分 ==========
    def _split_atomic(self, text: str) -> List[Tuple[str, bool]]:
        parts = []
        last = 0
        for m in ATOMIC_RE.finditer(text):
            if m.start() > last:
                parts.append((text[last:m.start()], False))
            parts.append((m.group(), True))
            last = m.end()
        if last < len(text):
            parts.append((text[last:], False))
        return parts

    # ========== 组装 Chunk（核心：生成 chunk_id 分片序号） ==========
    def _assemble_chunks(self, segments: List[Tuple[str, bool]], node: dict,
                         page_printed: dict) -> List[Chunk]:
        chunks = []
        buf = ""
        char_offset = 0
        chunk_seq = 0  # 分片序号

        # 超长非原子段先做结构兜底切分（段落/换行/句末），否则单段会整块超限
        expanded: List[Tuple[str, bool]] = []
        for seg, atomic in segments:
            if not atomic and len(seg) > self.max_chars:
                expanded.extend((p, False) for p in self._split_long_segment(seg))
            else:
                expanded.append((seg, atomic))
        segments = expanded

        # 预构建基础 metadata（不含 chunk_id）
        base_meta = build_chunk_metadata(
            source_file="ZRDDS用户手册.pdf",
            source_type="pdf",
            part=node.get("part", ""),
            chapter=node.get("chapter", ""),
            section_path=node["section_path"],
            section_level=node["level"],
            printed_page_start=node["printed_page_start"],
            printed_page_end=node["printed_page_end"],
            physical_page_start=node["physical_page_start"],
            physical_page_end=node["physical_page_end"],
            node_ids=[node["node_id"]],
            chunk_id="",  # 占位，下方逐个填入
            version="2.0",
            product="ZRDDS",
        )

        def flush():
            nonlocal buf, char_offset, chunk_seq, chunks
            if not buf.strip():
                return
            meta = base_meta.copy()
            meta["chunk_id"] = f"struct_v1_{node['node_id']}_{chunk_seq:05d}"
            chunks.append(Chunk(
                chunk_id=meta["chunk_id"],
                text=buf.strip(),
                metadata=meta,
                token_count=self._count_tokens(buf),
                char_start=char_offset - len(buf),
                char_end=char_offset,
            ))
            chunk_seq += 1
            buf = ""

        for seg, atomic in segments:
            if atomic:
                if buf:
                    flush()
                meta = base_meta.copy()
                meta["chunk_id"] = f"struct_v1_{node['node_id']}_{chunk_seq:05d}"
                chunks.append(Chunk(
                    chunk_id=meta["chunk_id"],
                    text=seg.strip(),
                    metadata=meta,
                    token_count=self._count_tokens(seg),
                    char_start=char_offset,
                    char_end=char_offset + len(seg),
                ))
                char_offset += len(seg)
                chunk_seq += 1
            else:
                if len(buf) + len(seg) > self.max_chars and buf:
                    flush()
                buf += seg
                char_offset += len(seg)

        if buf:
            flush()
        return chunks

    # ========== 超大节：沿四/五级子节下切 ==========
    def _split_by_subsections(self, node: dict, page_texts: dict,
                              page_printed: dict, tree_map: dict,
                              boundary_map: dict) -> List[Chunk]:
        sub_nodes = [n for n in tree_map.values()
                     if n["level"] in (4, 5) and self._is_descendant(n, node)]
        if not sub_nodes:
            return []

        # 只取直接子节点：候选中存在中间祖先层的后代交给递归处理，
        # 否则同一节点会被重复产出（chunk_id 冲突）
        def _has_intermediary(d: dict) -> bool:
            return any(o["node_id"] != d["node_id"] and self._is_descendant(d, o)
                       for o in sub_nodes)
        sub_nodes = [d for d in sub_nodes if not _has_intermediary(d)]

        sub_nodes.sort(key=self._heading_sort_key)
        all_chunks = []

        # 引导段：本节标题 → 第一个子节标题之间的正文（原先被丢弃）；
        # 仅含标题本身时不产出噪声块
        lead = self._extract_node_text(node, sub_nodes[0], page_texts)
        if lead.strip() and _norm_text(lead) != _norm_text(node["title"]):
            all_chunks.extend(
                self._assemble_chunks(self._split_atomic(lead), node, page_printed))

        for sub in sub_nodes:
            raw = self._extract_node_text(sub, boundary_map.get(sub["node_id"]),
                                          page_texts)
            if not raw.strip():
                continue
            if len(raw) > self.max_chars and sub["level"] == 4:
                deeper = self._split_by_subsections(sub, page_texts, page_printed,
                                                    tree_map, boundary_map)
                if deeper:
                    all_chunks.extend(deeper)
                    continue
            segs = self._split_atomic(raw)
            chunks = self._assemble_chunks(segs, sub, page_printed)
            all_chunks.extend(chunks)
        return all_chunks

    def _is_descendant(self, child: dict, ancestor: dict) -> bool:
        # D3 修复：section_path 已逐级嵌套，后代路径 = 祖先路径 + " / " + …
        return (child["physical_page_start"] >= ancestor["physical_page_start"] and
                child["physical_page_end"]   <= ancestor["physical_page_end"] and
                child["section_path"].startswith(ancestor["section_path"] + " / "))

    # ========== 工具 ==========
    def _flatten_tree(self, nodes: List[dict]) -> List[dict]:
        flat = []
        def dfs(ns):
            for n in ns:
                flat.append(n)
                dfs(n.get("children", []))
        dfs(nodes)
        return flat

# ========== CLI 单测 ==========
if __name__ == "__main__":
    import json, sys
    from pathlib import Path

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    pages_path = sys.argv[1] if len(sys.argv) > 1 else "data/cleaned/pages.jsonl"
    tree_path  = sys.argv[2] if len(sys.argv) > 2 else "data/processed/section_tree_v1.jsonl"
    out_path   = sys.argv[3] if len(sys.argv) > 3 else "data/processed/struct_v1.jsonl"

    with open(pages_path, encoding="utf-8") as f:
        pages = [json.loads(l) for l in f]
    with open(tree_path, encoding="utf-8") as f:
        tree = [json.loads(l) for l in f]

    chunker = StructureChunker({"max_chunk_chars": 2500, "overlap_chars": 200})
    chunks = chunker.chunk(pages, tree)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    print(f"[structure] 生成 {len(chunks)} 个 chunk -> {out_path}")
    lens = [len(c.text) for c in chunks]
    print(f"  长度分布: min={min(lens)}, max={max(lens)}, avg={sum(lens)//len(lens)}")