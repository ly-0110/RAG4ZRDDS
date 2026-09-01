# G:\DSH workspace\data_pipeline\chunkers\semantic.py
"""
语义分块 Chunking（方案 B · 成员 A 第二周交付）：
- 使用 LlamaIndex SemanticSplitterNodeParser：按嵌入相似度自动寻找语义断点
- 产出 Node 集落盘 data/processed/semantic_v1.jsonl（Metadata Schema 与 struct 一致）
- 嵌入模型双模式：
    embed_model: "mock"    → MockEmbedding（无 torch/模型依赖，冒烟/CI 用，无语义）
    embed_model: "bge-m3"  → HuggingFaceEmbedding(BAAI/bge-m3)（真实，需装依赖）
- 指南 §6.2：breakpoint_percentile_threshold=95、buffer_size=1 为建议起点
"""
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from data_pipeline.chunkers.base import BaseChunker, Chunk
from data_pipeline.metadata import build_chunk_metadata, validate_metadata

# ---------- 原子块保护正则（与 structure.py 保持一致） ----------
import re
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


class SemanticChunker(BaseChunker):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.max_chars = config.get("max_chunk_chars", 2500)
        self.overlap = config.get("overlap_chars", 200)
        # 语义分块参数（指南 §6.2）
        self.breakpoint_percentile_threshold = config.get(
            "breakpoint_percentile_threshold", 95)
        self.buffer_size = config.get("buffer_size", 1)
        self.embed_model_name = config.get("embed_model", "bge-m3")

        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.core.embeddings.mock_embed_model import MockEmbedding

        if self.embed_model_name.lower() in ("mock", "fake", "none"):
            # 冒烟模式：无真实语义，仅验证管道与 Schema
            self.embed_model = MockEmbedding(embed_dim=64)
        else:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            hf_model = "BAAI/bge-m3" if self.embed_model_name == "bge-m3" \
                else self.embed_model_name
            self.embed_model = HuggingFaceEmbedding(
                model_name=hf_model, device="cpu")

        self.splitter = SemanticSplitterNodeParser(
            buffer_size=self.buffer_size,
            breakpoint_percentile_threshold=self.breakpoint_percentile_threshold,
            embed_model=self.embed_model,
            sentence_splitter=_split_sentences,
        )

    # ========== 主入口 ==========
    def chunk(self, pages: List[dict], section_tree: List[dict]) -> List[Chunk]:
        """
        语义分块主入口：
        1. 全文档拼接为带页边界的文本（保留 physical/printed 页码）
        2. SemanticSplitter 按语义相似度切分
        3. 每个语义 Node 按所在物理页回填三级节路径（page → 最细节点）
        4. 构建标准 Chunk + 冻结 Metadata Schema
        """
        tree_map = {n["node_id"]: n for n in self._flatten_tree(section_tree)}

        # 构建 (physical_page, printed_page, text) 有序列表
        page_items = sorted(
            ((p["physical_page"], p["printed_page"], p["text"]) for p in pages),
            key=lambda x: x[0],
        )

        # 组装 LlamaIndex Document：文本段落间注入页标记，便于回映射
        segments: List[Tuple[int, int, str]] = []  # (physical_page, printed_page, text)
        for phys, printed, text in page_items:
            text = (text or "").strip()
            if not text:
                continue
            segments.append((phys, printed, text))

        # 语义切分需要连续文本；跨页拼接时用 \n\n 分隔并在 Node 元数据带页号
        # 只处理命中章节树的页：封面/目录等无归属页不参与（与 struct 覆盖一致，
        # 保证三方案公平对比；否则语义方案会多出"未命中章节"块）
        from llama_index.core.schema import Document
        docs = []
        skipped_pages = 0
        for phys, printed, text in segments:
            if not self._infer_section_from_page(phys, tree_map)["node_ids"]:
                skipped_pages += 1
                continue
            docs.append(Document(
                text=text,
                metadata={
                    "physical_page": phys,
                    "printed_page": printed,
                    "source_file": "ZRDDS用户手册.pdf",
                    "source_type": "pdf",
                },
            ))
        if skipped_pages:
            print(f"[semantic] 跳过无章节归属页 {skipped_pages} 页（封面/目录等）",
                  file=__import__("sys").stderr)

        nodes = self.splitter.get_nodes_from_documents(docs)

        # Node → Chunk 映射
        all_chunks: List[Chunk] = []
        for i, node in enumerate(nodes):
            chunk = self._node_to_chunk(node, i, tree_map)
            if chunk:
                all_chunks.append(chunk)

        # 最终校验（冻结 Metadata Schema）
        for c in all_chunks:
            missing = validate_metadata(c.metadata)
            if missing:
                raise ValueError(f"Chunk {c.chunk_id} 缺失元数据: {missing}")
        return all_chunks

    # ========== Node → Chunk ==========
    def _node_to_chunk(
        self, node, idx: int, tree_map: Dict[str, dict]
    ) -> Optional[Chunk]:
        text = (node.get_content() or "").strip()
        if not text:
            return None

        phys = node.metadata.get("physical_page")
        printed = node.metadata.get("printed_page", phys)

        # 按物理页回填章节路径（最细粒度节点）
        sec = self._infer_section_from_page(phys, tree_map) if phys is not None \
            else self._empty_section(phys, printed)

        # 块级页码：LlamaIndex node 元数据只含（起始）页，跨页块的止页未知，
        # 故双页码取块起始页单页口径——Citation 精度优于整节区间近似
        meta = build_chunk_metadata(
            source_id="user_manual",
            source_file=node.metadata.get("source_file", "ZRDDS用户手册.pdf"),
            source_type=node.metadata.get("source_type", "pdf"),
            part=sec["part"],
            chapter=sec["chapter"],
            section_path=sec["section_path"],
            section_level=sec["section_level"],
            printed_page_start=printed,
            printed_page_end=printed,
            physical_page_start=phys,
            physical_page_end=phys,
            node_ids=sec["node_ids"],
            chunk_id=f"semantic_v1_{idx:05d}",
            version="2.0",
            product="ZRDDS",
        )
        return Chunk(
            chunk_id=meta["chunk_id"],
            text=text,
            metadata=meta,
            token_count=self._count_tokens(text),
            char_start=0,          # 语义分块不保留原始字符偏移
            char_end=len(text),
        )

    # ========== 页码 → 章节推断 ==========
    def _infer_section_from_page(
        self, physical_page: Optional[int], tree_map: Dict[str, dict]
    ) -> Dict[str, Any]:
        if physical_page is None:
            return self._empty_section(None, None)
        # 选择覆盖该页且层级最深（最细）的节点
        best = None
        for n in tree_map.values():
            if n["physical_page_start"] <= physical_page <= n["physical_page_end"]:
                if best is None or n["level"] > best["level"]:
                    best = n
        if best is None:
            return self._empty_section(physical_page, None)
        return {
            "part": best.get("part", ""),
            "chapter": best.get("chapter", ""),
            "section_path": best["section_path"],
            "section_level": best["level"],
            "printed_page_start": best["printed_page_start"],
            "printed_page_end": best["printed_page_end"],
            "physical_page_start": best["physical_page_start"],
            "physical_page_end": best["physical_page_end"],
            "node_ids": [best["node_id"]],
        }

    @staticmethod
    def _empty_section(phys: Optional[int], printed: Optional[int]) -> Dict[str, Any]:
        p = phys if phys is not None else 0
        pr = printed if printed is not None else p
        return {
            "part": "",
            "chapter": "",
            "section_path": "未命中章节",
            "section_level": 3,
            "printed_page_start": pr,
            "printed_page_end": pr,
            "physical_page_start": p,
            "physical_page_end": p,
            "node_ids": [],
        }

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
    out_path = sys.argv[3] if len(sys.argv) > 3 else "data/processed/semantic_v1.jsonl"

    with open(pages_path, encoding="utf-8") as f:
        pages = [json.loads(l) for l in f if l.strip()]
    with open(tree_path, encoding="utf-8") as f:
        tree = [json.loads(l) for l in f if l.strip()]

    embed = sys.argv[4] if len(sys.argv) > 4 else "mock"
    chunker = SemanticChunker({
        "max_chunk_chars": 2500,
        "overlap_chars": 200,
        "breakpoint_percentile_threshold": 95,
        "buffer_size": 1,
        "embed_model": embed,
    })
    chunks = chunker.chunk(pages, tree)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    print(f"[semantic] 生成 {len(chunks)} 个 chunk -> {out_path}")
    lens = [len(c.text) for c in chunks]
    print(f"  长度分布: min={min(lens)}, max={max(lens)}, "
          f"avg={sum(lens) // len(lens) if lens else 0}")
