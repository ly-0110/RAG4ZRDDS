# G:\DSH workspace\data_pipeline\chunkers\hybrid.py
"""
混合分块 Chunking（方案 C · 成员 A 第二周交付）：
- 主体沿用结构感知策略（三级节为知识单元，同 structure.py）
- 差异化：超大节（超阈值）沿四/五级子节下切后，若仍超出单块上限，
  用语义分块（SemanticSplitterNodeParser）对子节内容做语义二次切分
- 产出 Node 集落盘 data/processed/hybrid_v1.jsonl
- 嵌入模型双模式：embed_model: "mock"（冒烟）| "bge-m3"（真实）
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Tuple
from data_pipeline.chunkers.base import BaseChunker, Chunk
from data_pipeline.metadata import build_chunk_metadata, validate_metadata

# 原子块保护正则（与 structure.py 一致）
ATOMIC_RE = re.compile(
    r'(```[\s\S]*?```|\|.*?\|(?:\n\|.*?\|)+|\!\[.*?\]\(.*?\))'
)

# ---------- 句子切分器（替代 NLTK punkt，避免联网下载与沙箱限制） ----------
_SENTENCE_END_RE = re.compile(
    r'(?<=[。！？!?；;])\s*|(?<=[。！？!?；;]["\'”’）】])\s*|(?<=\n)\s*'
)


def _split_sentences(text: str) -> List[str]:
    """按中文/英文句末标点与换行切句；空段丢弃。"""
    parts = [p for p in _SENTENCE_END_RE.split(text) if p and p.strip()]
    return parts or ([text] if text.strip() else [])


class HybridChunker(BaseChunker):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.max_chars = config.get("max_chunk_chars", 2500)
        self.overlap = config.get("overlap_chars", 200)
        self.large_thresh = config.get("large_section_thresh", self.max_chars)
        # 语义二次切分参数
        self.breakpoint_percentile_threshold = config.get(
            "breakpoint_percentile_threshold", 95)
        self.buffer_size = config.get("buffer_size", 1)
        self.embed_model_name = config.get("embed_model", "bge-m3")

        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.core.embeddings.mock_embed_model import MockEmbedding

        if self.embed_model_name.lower() in ("mock", "fake", "none"):
            self.embed_model = MockEmbedding(embed_dim=64)
        else:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            hf_model = "BAAI/bge-m3" if self.embed_model_name == "bge-m3" \
                else self.embed_model_name
            self.embed_model = HuggingFaceEmbedding(
                model_name=hf_model, device="cpu")

        self.semantic_splitter = SemanticSplitterNodeParser(
            buffer_size=self.buffer_size,
            breakpoint_percentile_threshold=self.breakpoint_percentile_threshold,
            embed_model=self.embed_model,
            sentence_splitter=_split_sentences,
        )

    # ========== 主入口 ==========
    def chunk(self, pages: List[dict], section_tree: List[dict]) -> List[Chunk]:
        page_texts = {p["physical_page"]: p["text"] for p in pages}
        page_printed = {p["physical_page"]: p["printed_page"] for p in pages}
        tree_map = {n["node_id"]: n for n in self._flatten_tree(section_tree)}

        all_chunks: List[Chunk] = []
        for node in self._flatten_tree(section_tree):
            if node["level"] != 3:
                continue
            chunks = self._process_section_node(
                node, page_texts, page_printed, tree_map)
            all_chunks.extend(chunks)

        # 最终校验（冻结 Metadata Schema）
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

        # 先结构切分（与 struct 方案一致）
        segments = self._split_atomic(raw_text)
        chunks = self._assemble_chunks(segments, node, page_printed)

        total_len = sum(len(c.text) for c in chunks)

        # 超大节：沿四/五级子节下切
        if total_len > self.large_thresh:
            sub_chunks = self._split_by_subsections(
                node, page_texts, page_printed, tree_map)
            if sub_chunks:
                # 子节切分后仍超单块上限的 → 语义二次切分
                final: List[Chunk] = []
                for c in sub_chunks:
                    if len(c.text) > self.max_chars:
                        final.extend(self._semantic_resplit(c))
                    else:
                        final.append(c)
                return final
            # 无子节可用：整节语义切分兜底
            return self._semantic_split_raw(raw_text, node, page_printed)
        return chunks

    # ========== 语义二次切分 ==========
    def _semantic_resplit(self, chunk: Chunk) -> List[Chunk]:
        """对单个超限 chunk 做语义切分，chunk_id 保留父前缀+序号"""
        from llama_index.core.schema import Document
        doc = Document(
            text=chunk.text,
            metadata={
                "physical_page": chunk.metadata.get("physical_page_start"),
                "printed_page": chunk.metadata.get("printed_page_start"),
                "source_file": chunk.metadata.get("source_file", "ZRDDS用户手册.pdf"),
                "source_type": chunk.metadata.get("source_type", "pdf"),
            },
        )
        nodes = self.semantic_splitter.get_nodes_from_documents([doc])
        out: List[Chunk] = []
        for i, node in enumerate(nodes):
            text = (node.get_content() or "").strip()
            if not text:
                continue
            meta = dict(chunk.metadata)
            base_id = f"{chunk.chunk_id}_sem{i:03d}"
            # 语义切分后仍超上限 → 字符兜底切分（mock 嵌入可能合并不切）
            if len(text) > self.max_chars:
                meta["chunk_prefix"] = base_id
                for j, sub in enumerate(self._split_long_text(text, meta)):
                    sub.metadata = dict(meta)
                    sub.metadata["chunk_id"] = f"{base_id}_p{j:03d}"
                    sub.metadata.pop("chunk_prefix", None)  # 非Schema字段，防泄漏落盘
                    out.append(sub)
            else:
                meta["chunk_id"] = base_id
                out.append(Chunk(
                    chunk_id=meta["chunk_id"],
                    text=text,
                    metadata=meta,
                    token_count=self._count_tokens(text),
                    char_start=0,
                    char_end=len(text),
                ))
        return out

    def _semantic_split_raw(self, raw_text: str, node: dict,
                            page_printed: dict) -> List[Chunk]:
        """整节语义切分兜底（无子节可下切时）"""
        from llama_index.core.schema import Document
        doc = Document(
            text=raw_text,
            metadata={
                "physical_page": node["physical_page_start"],
                "printed_page": node["printed_page_start"],
                "source_file": "ZRDDS用户手册.pdf",
                "source_type": "pdf",
            },
        )
        nodes = self.semantic_splitter.get_nodes_from_documents([doc])
        out: List[Chunk] = []
        for i, node_ in enumerate(nodes):
            text = (node_.get_content() or "").strip()
            if not text:
                continue
            meta = build_chunk_metadata(
                source_id="user_manual",
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
                chunk_id="",
                version="2.0",
                product="ZRDDS",
            )
            base_id = f"hybrid_v1_{node['node_id']}_sem{i:03d}"
            # 语义切分后仍超上限 → 字符兜底切分（mock 嵌入可能合并不切）
            if len(text) > self.max_chars:
                meta["chunk_prefix"] = base_id
                for j, sub in enumerate(self._split_long_text(text, meta)):
                    sub.metadata = dict(meta)
                    sub.metadata["chunk_id"] = f"{base_id}_p{j:03d}"
                    sub.metadata.pop("chunk_prefix", None)  # 非Schema字段，防泄漏落盘
                    out.append(sub)
            else:
                meta["chunk_id"] = base_id
                out.append(Chunk(
                    chunk_id=meta["chunk_id"],
                    text=text,
                    metadata=meta,
                    token_count=self._count_tokens(text),
                    char_start=0,
                    char_end=len(text),
                ))
        return out

    # ========== 文本提取 / 原子保护 ==========
    def _extract_text_by_pages(self, node: dict, page_texts: dict) -> str:
        start, end = node["physical_page_start"], node["physical_page_end"]
        parts = []
        for pg in range(start, end + 1):
            txt = page_texts.get(pg, "").strip()
            if txt:
                parts.append(txt)
        return "\n\n".join(parts)

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

    # ========== Chunk 组装（chunk_id 前缀 hybrid_v1） ==========
    def _assemble_chunks(self, segments: List[Tuple[str, bool]], node: dict,
                         page_printed: dict) -> List[Chunk]:
        chunks = []
        buf = ""
        char_offset = 0
        chunk_seq = 0

        base_meta = build_chunk_metadata(
            source_id="user_manual",
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
            chunk_id="",
            version="2.0",
            product="ZRDDS",
        )

        def flush():
            nonlocal buf, char_offset, chunk_seq, chunks
            if not buf.strip():
                return
            meta = base_meta.copy()
            meta["chunk_id"] = f"hybrid_v1_{node['node_id']}_{chunk_seq:05d}"
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
                meta["chunk_id"] = f"hybrid_v1_{node['node_id']}_{chunk_seq:05d}"
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

    # ========== 子节下切（与 struct 一致） ==========
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
                deeper = self._split_by_subsections(
                    sub, page_texts, page_printed, tree_map)
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
                child["physical_page_end"] <= ancestor["physical_page_end"] and
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
    import json
    import sys
    from pathlib import Path

    pages_path = sys.argv[1] if len(sys.argv) > 1 else "data/cleaned/pages.jsonl"
    tree_path = sys.argv[2] if len(sys.argv) > 2 else "data/processed/section_tree_v1.jsonl"
    out_path = sys.argv[3] if len(sys.argv) > 3 else "data/processed/hybrid_v1.jsonl"

    with open(pages_path, encoding="utf-8") as f:
        pages = [json.loads(l) for l in f if l.strip()]
    with open(tree_path, encoding="utf-8") as f:
        tree = [json.loads(l) for l in f if l.strip()]

    embed = sys.argv[4] if len(sys.argv) > 4 else "mock"
    chunker = HybridChunker({
        "max_chunk_chars": 2500,
        "overlap_chars": 200,
        "large_section_thresh": 2500,
        "breakpoint_percentile_threshold": 95,
        "buffer_size": 1,
        "embed_model": embed,
    })
    chunks = chunker.chunk(pages, tree)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    print(f"[hybrid] 生成 {len(chunks)} 个 chunk -> {out_path}")
    lens = [len(c.text) for c in chunks]
    print(f"  长度分布: min={min(lens)}, max={max(lens)}, "
          f"avg={sum(lens) // len(lens) if lens else 0}")
