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
        tree_map = {n["node_id"]: n for n in self._flatten_tree(section_tree)}

        all_chunks: List[Chunk] = []
        for node in self._flatten_tree(section_tree):
            if node["level"] != 3:
                continue
            chunks = self._process_section_node(node, page_texts, page_printed, tree_map)
            all_chunks.extend(chunks)

        # 最终校验
        for c in all_chunks:
            missing = validate_metadata(c.metadata)
            if missing:
                raise ValueError(f"Chunk {c.chunk_id} 缺失元数据: {missing}")
        return all_chunks

    # ========== 单个三级节处理 ==========
    def _process_section_node(self, node: dict, page_texts: dict,
                              page_printed: dict, tree_map: dict) -> List[Chunk]:
        raw_text = self._extract_text_by_pages(node, page_texts)
        if not raw_text.strip():
            return []

        segments = self._split_atomic(raw_text)
        chunks = self._assemble_chunks(segments, node, page_printed)

        total_len = sum(len(c.text) for c in chunks)
        if total_len > self.large_thresh:
            sub_chunks = self._split_by_subsections(node, page_texts, page_printed, tree_map)
            if sub_chunks:
                return sub_chunks
        return chunks

    # ========== 文本提取 ==========
    def _extract_text_by_pages(self, node: dict, page_texts: dict) -> str:
        start, end = node["physical_page_start"], node["physical_page_end"]
        parts = []
        for pg in range(start, end + 1):
            txt = page_texts.get(pg, "").strip()
            if txt:
                parts.append(txt)
        return "\n\n".join(parts)

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
                              page_printed: dict, tree_map: dict) -> List[Chunk]:
        sub_nodes = [n for n in tree_map.values()
                     if n["level"] in (4, 5) and self._is_descendant(n, node)]
        if not sub_nodes:
            return []

        sub_nodes.sort(key=lambda x: x["physical_page_start"])
        all_chunks = []
        for sub in sub_nodes:
            raw = self._extract_text_by_pages(sub, page_texts)
            if not raw.strip():
                continue
            if len(raw) > self.max_chars and sub["level"] == 4:
                deeper = self._split_by_subsections(sub, page_texts, page_printed, tree_map)
                if deeper:
                    all_chunks.extend(deeper)
                    continue
            segs = self._split_atomic(raw)
            chunks = self._assemble_chunks(segs, sub, page_printed)
            all_chunks.extend(chunks)
        return all_chunks

    def _is_descendant(self, child: dict, ancestor: dict) -> bool:
        # 必须严格是后代：排除自身（否则 level4 节点会把自己选为子节点 → 无限递归）
        if child is ancestor or child["node_id"] == ancestor["node_id"]:
            return False
        return (child["physical_page_start"] >= ancestor["physical_page_start"] and
                child["physical_page_end"]   <= ancestor["physical_page_end"] and
                child["section_path"].startswith(ancestor["section_path"]))

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