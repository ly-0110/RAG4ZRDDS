"""Context 组装：检索片段 → 注入 Prompt 的上下文文本（指南 §5 成员 C：定义 context 格式）。

格式约定（与 docs/citation-contract-draft.md §3 对齐）：
  * 每个片段编号 [n]（1 基，对应 sources 数组下标），LLM 据此输出 [n] 引用标记；
  * 每段首行给出来源（文件名 · 印刷页码 · 章节），正文紧跟其后；
  * 片段按检索器返回顺序传入（已按 score 降序），本模块不排序。

示例：
  [1] 来源：ZRDDS用户手册.pdf · 第 42 页 · 3.4 节
  <正文…>

  [2] 来源：ZRDDS用户手册.pdf · 第 47 页 · 3.5 节
  <正文…>
"""

from __future__ import annotations

_SEPARATOR = "\n\n"


def _format_source(chunk: dict) -> str:
    """把一条富引用格式化为可读来源行；缺页/缺节时优雅降级。"""
    parts = [chunk.get("source_name") or "未知来源"]
    page = chunk.get("page_print")
    if page is not None:
        parts.append(f"第 {page} 页")
    section = (chunk.get("section") or "").strip()
    if section:
        parts.append(section)
    return " · ".join(parts)


def build_context(chunks: list[dict]) -> str:
    """把检索片段拼成编号上下文；无片段/片段全为空正文时返回空串（由调用方走拒答）。"""
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        text = (chunk.get("text") or "").strip()
        header = f"[{i}] 来源：{_format_source(chunk)}"
        blocks.append(header if not text else f"{header}\n{text}")
    return _SEPARATOR.join(blocks)
