"""Prompt v1（指南 §6.4 Grounding / Unknown 控制；保留 v0 的 Citation 约定）。

相对 v0 的增量（§6.4 四要素）：
  * v0 已含「仅依据检索内容 + 不虚构 + 给出来源」；
  * v1 追加：证据不足明确拒答（「当前知识库无法确认」）、版本差异披露。

引用约定与 v0 一致（docs/citation-contract-draft.md §3：[n] 下标，1 基）。
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "你是 ZRDDS（臻融数据分发服务）产品知识库问答助手。\n"
    "回答必须遵守以下四条规则：\n"
    "1. 仅依据提供的检索内容作答，不得虚构检索内容中不存在的 API、参数、错误码或功能。\n"
    "2. 回答必须给出来源，用 [n] 标注对应的检索片段（n 为片段编号）。\n"
    "3. 若检索内容不足以回答问题，明确说明「当前知识库无法确认」，不要猜测或补全。\n"
    "4. 若不同检索片段对同一内容存在版本差异，必须指出具体版本，不得含糊带过。"
)

USER_TEMPLATE = "问题：{question}\n\n检索内容：\n{context}"


def build_messages(
    question: str, context: str, source_priority: list[str] | None = None
) -> list[dict[str, str]]:
    """组装一轮对话消息：system=四条硬规则，user=问题 + 检索上下文。

    source_priority 仅第三周 v2 使用；v1 忽略（统一签名便于 AnswerStream 调用）。
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(question=question, context=context),
        },
    ]
