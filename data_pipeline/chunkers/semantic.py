# G:\DSH workspace\data_pipeline\chunkers\semantic.py
"""
语义分块 Chunking（方案 B · 成员 A 第二周交付）：
- 使用 LlamaIndex SemanticSplitterNodeParser：按嵌入相似度自动寻找语义断点
- 产出 Node 集落盘 data/processed/semantic_v1.jsonl（Metadata Schema 与 struct 一致）
- 嵌入模型双模式：
    embed_model: "mock"    → MockEmbedding（无 torch/模型依赖，冒烟/CI 用，无语义）
    embed_model: "bge-m3"  → HuggingFaceEmbedding(BAAI/bge-m3)（真实，需装依赖）
- 指南 §6.2：breakpoint_percentile_threshold=95、buffer_size=1 为建议起点

性能与碎块过滤修复（A 域遗留，docs/week2-delivery-review.md §2.1）：
- 全文档一次调用：原实现逐页构造 Document → splitter 内部为每页独立调一次
  get_text_embedding_batch（bge-m3 CPU 跑 ~300 页 ≈ 25 min）。现合并为单个
  Document，跨页用「页锚点」分隔（嵌入相似度天然容忍），splitter 一次 batch
  前向完成。
- 页码回填：语义切分只看句子相似度、不知道页边界。做法是先在句流里注入
  PAGE={phys} 锚点句（唯一控制字符，正文不可能出现），node 文本 = 句流里
  若干连续句子按 "" 拼接 —— 因此用同一 sentence_splitter 复算句流并对
  每句标注页号，再用「node 文本是句流连续子串」的性质（游标顺序匹配）定位
  每个 node 的起始句 → 起始句所在物理页即块起始页（与结构方案「块起始页
  单页口径」一致）。锚点只用于定位，绝不会进入 chunk 正文。
- 碎块过滤：min_chunk_chars（默认 20）过滤过短碎块（62 块 <10 字符的图号/
  节号碎片、166 块 <50 字符的边角料）；过滤数量计入日志，便于复测比较。
"""
from __future__ import annotations
import bisect
import re
from typing import List, Dict, Any, Tuple, Optional
from data_pipeline.chunkers.base import BaseChunker, Chunk
from data_pipeline.metadata import build_chunk_metadata, validate_metadata

# ---------- 原子块保护正则（与 structure.py 保持一致） ----------
ATOMIC_RE = re.compile(
    r'(```[\s\S]*?```|\|.*?\|(?:\n\|.*?\|)+|\!\[.*?\]\(.*?\))'
)

# ---------- 页锚点（跨页定位专用，见 class SemanticChunker） ----------
# 页锚点 = \x01PAGE=<物理页号>\x02：不可打印控制字符，手册正文/PDF 均不可能
# 出现，故可安全用作句流内唯一的「页边界」标记；只参与定位，剥离后才落正文。
_ANCHOR_RE = re.compile(r"\x01PAGE=(\d+)\x02")

# ---------- 句子切分器（替代 NLTK punkt，避免联网下载与沙箱限制） ----------
_SENTENCE_END_RE = re.compile(
    r'(?<=[。！？!?；;])\s*|(?<=[。！？!?；;]["\'”’）】])\s*|(?<=\n)\s*'
)


def _split_sentences(text: str) -> List[str]:
    """按中文/英文句末标点与换行切句；空段丢弃。"""
    parts = [p for p in _SENTENCE_END_RE.split(text) if p and p.strip()]
    return parts or ([text] if text.strip() else [])


class SemanticChunker(BaseChunker):
    # 跨页锚点：作为 Document 内独立「句子」注入句流，供 splitter 当普通句
    # 参与断点判定；切分后按句流定位回填 physical/printed 页号，并从 chunk
    # 正文剥离（锚点绝不进入索引/检索/引用）。
    # 字符选取：不可打印 + 不可能被任何手册正文匹配（gbk/pdf 都不会出现 NUL/U+0001）。
    _PAGE_ANCHOR_FMT = "\x01PAGE={phys}\x02"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.max_chars = config.get("max_chunk_chars", 2500)
        self.overlap = config.get("overlap_chars", 200)
        # 碎块过滤：默认 ≥20 字符（week2-delivery-review.md §2.1 建议起点）；
        # 0 关闭过滤以保持向后兼容（如对比实验需要原始分布）。
        self.min_chunk_chars = config.get("min_chunk_chars", 20)
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
        1. 全文档拼接为单个 Document（性能：一次 embedding batch 前向；
           原逐页方案 ≈300 次独立调用 → 25 min → 现 ~单次调用）。
        2. 拼接时在页边界注入 PAGE={phys} 锚点；切分后按句流定位回填
           physical/printed 页号（块起始页单页口径，见 _build_stream_index）。
        3. 只处理命中章节树的页：封面/目录等无归属页不参与（与 struct 覆盖
           一致，保证三方案公平对比；否则语义方案会多出"未命中章节"块）。
        4. 碎块过滤：丢弃剥离锚点后 len(text) < min_chunk_chars 的 node
           （默认 20 字符），过滤数量计入 stderr 日志，便于复测比对。
        """
        tree_map = {n["node_id"]: n for n in self._flatten_tree(section_tree)}

        # 命中章节的页才参与分块（按 physical_page 升序）
        included_pages: List[Tuple[int, int, str]] = []
        skipped_pages = 0
        for p in sorted(pages, key=lambda x: x.get("physical_page", 0)):
            phys = p.get("physical_page")
            printed = p.get("printed_page", phys)
            text = (p.get("text") or "").strip()
            if phys is None or not text:
                continue
            if not self._infer_section_from_page(phys, tree_map)["node_ids"]:
                skipped_pages += 1
                continue
            included_pages.append((phys, printed, text))
        if skipped_pages:
            print(f"[semantic] 跳过无章节归属页 {skipped_pages} 页（封面/目录等）",
                  file=__import__("sys").stderr)

        if not included_pages:
            return []

        # 全文档一次拼接 + 页锚点；锚点会被 _split_sentences 切为独立「句子」
        parts: List[str] = []
        for phys, _printed, text in included_pages:
            parts.append(self._PAGE_ANCHOR_FMT.format(phys=phys))
            parts.append(text)
        full_text = "\n\n".join(parts)

        from llama_index.core.schema import Document
        doc = Document(
            text=full_text,
            metadata={
                "source_file": "ZRDDS用户手册.pdf",
                "source_type": "pdf",
            },
        )
        nodes = self.splitter.get_nodes_from_documents([doc])

        # Node → Chunk 映射 + 碎块过滤。
        # 页码回填（锚点剥离 + 起始句定位，详见 _build_stream_index）：
        # 语义切分只按嵌入相似度断句、不知道页边界；页锚点只是句流里的定位句。
        # node 文本 = 句流中若干连续句子按 "" 拼接（llama_index 实现），因此
        # 可复算句流、逐句标注所在页，再用「node 文本是句流连续子串」的性质
        # （游标顺序匹配）定位每个 node 的起始句 → 起始句所在物理页即块起始页
        # （与 struct 方案「块起始页单页口径」一致）。锚点只用于定位，剥离后
        # 绝不进入 chunk 正文/索引。
        pages_of, offsets, concat = self._build_stream_index(full_text)
        all_chunks: List[Chunk] = []
        dropped_short = 0
        dropped_unmapped = 0
        printed_for_chunk: Dict[int, int] = {
            phys: printed for phys, printed, _ in included_pages
        }
        cursor = 0  # 已消费的句流偏移（llama node 依序划分整个句流，无重叠/空洞）
        for i, node in enumerate(nodes):
            raw = node.get_content() or ""
            start_off = self._locate_node_in_stream(raw, cursor, concat)
            if start_off is not None:
                cursor = start_off + len(raw)
            phys = self._resolve_phys_for_node(
                raw, start_off, pages_of, offsets, printed_for_chunk)
            if phys is None:
                dropped_unmapped += 1
                continue
            chunk = self._node_to_chunk(node, raw, phys, i, tree_map,
                                        printed_for_chunk)
            if chunk is None:
                dropped_short += 1
                continue
            all_chunks.append(chunk)

        if dropped_short:
            print(
                f"[semantic] 过滤 <{self.min_chunk_chars} 字符碎块 {dropped_short} 块"
                f"（min_chunk_chars={self.min_chunk_chars}）",
                file=__import__("sys").stderr,
            )
        if dropped_unmapped:
            print(
                f"[semantic] 无法定位物理页丢弃 {dropped_unmapped} 块"
                f"（理论不可达；若复现请检查 llama_index 版本行为）",
                file=__import__("sys").stderr,
            )

        # 最终校验（冻结 Metadata Schema）
        for c in all_chunks:
            missing = validate_metadata(c.metadata)
            if missing:
                raise ValueError(f"Chunk {c.chunk_id} 缺失元数据: {missing}")
        return all_chunks

    # ========== 句流索引与页码回填 ==========
    def _build_stream_index(self, full_text: str):
        """复算 splitter 的句流并逐句标注物理页（splitter 无状态、确定性）。

        SemanticSplitterNodeParser 在内部对 full_text 调用本模块 _split_sentences
        （与这里同一函数、同一输入 → 同一句流），随后 node 文本 = 句流中若干
        连续句子按 "" 拼接。页锚点是句流中形如 \\x01PAGE=N\\x02 的定位句：
        逐句扫描时遇到锚点即切换「当前页」标签。

        返回 (pages_of, offsets, concat)：
          pages_of[i]  → 第 i 句所在物理页（None 表示首锚点之前，实际不存在）
          offsets[i]   → 第 i 句在 concat 中的起始偏移
          concat       → "".join(句流)（node 文本的父串）
        """
        stream = _split_sentences(full_text)
        pages_of: List[Optional[int]] = []
        cur_page: Optional[int] = None
        for piece in stream:
            m = _ANCHOR_RE.search(piece)
            if m:
                cur_page = int(m.group(1))
            pages_of.append(cur_page)
        offsets: List[int] = []
        acc = 0
        for piece in stream:
            offsets.append(acc)
            acc += len(piece)
        return pages_of, offsets, "".join(stream)

    def _locate_node_in_stream(
        self, raw: str, cursor: int, concat: str,
    ) -> Optional[int]:
        """定位 node 文本在句流 concat 中的起始偏移（找不到返回 None）。

        node 依序划分整个句流，正常情况 concat[cursor:] 恰好以 raw 开头
        （O(1) 前缀校验）；校验失败（理论上不发生）退化为 find(raw, cursor)。
        """
        if not raw:
            return None
        if 0 <= cursor <= len(concat) - len(raw) and concat.startswith(raw, cursor):
            return cursor
        hit = concat.find(raw, cursor if 0 <= cursor <= len(concat) else 0)
        return hit if hit >= 0 else None

    def _resolve_phys_for_node(
        self, raw: str, start_off: Optional[int],
        pages_of: List[Optional[int]], offsets: List[int],
        printed_for_chunk: Dict[int, int],
    ) -> Optional[int]:
        """node 起始句所在物理页 = 块起始页；定位失败则扫 raw 内锚点兜底。"""
        if start_off is not None:
            idx = bisect.bisect_right(offsets, start_off) - 1
            if 0 <= idx < len(pages_of):
                phys = pages_of[idx]
                if phys is not None and phys in printed_for_chunk:
                    return phys
        # 兜底：文本内直接找锚点（正常不可达，防 llama_index 版本行为变化）
        for m in reversed(_ANCHOR_RE.findall(raw or "")):
            phys = int(m)
            if phys in printed_for_chunk:
                return phys
        if printed_for_chunk:
            return next(iter(sorted(printed_for_chunk)))
        return None

    # ========== Node → Chunk ==========
    def _node_to_chunk(
        self, node, raw: str, phys: Optional[int], idx: int,
        tree_map: Dict[str, dict], printed_for_chunk: Dict[int, int],
    ) -> Optional[Chunk]:
        text = self._clean_node_text(raw)
        if not text:
            return None

        # 碎块过滤：A 域遗留（docs/week2-delivery-review.md §2.1）：
        # 实测 166/1059 块 <50 字符，62 块 <10 字符（多见图号/节号碎片），
        # 索引后形成噪声证据。建议 ≥20 字符；对剥离锚点后的正文判长。
        if len(text) < self.min_chunk_chars:
            return None

        printed = printed_for_chunk.get(phys, phys)

        # 按物理页回填章节路径（最细粒度节点）
        sec = self._infer_section_from_page(phys, tree_map) if phys is not None \
            else self._empty_section(phys, printed)

        # 块级页码：与结构方案一致取块起始页单页口径——Citation 精度优于整节区间近似
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

    @staticmethod
    def _clean_node_text(raw: str) -> str:
        """剥离页锚点控制字节——锚点只用于内部定位，绝不进入 chunk 正文/索引。"""
        return _ANCHOR_RE.sub("", raw or "").strip()

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
