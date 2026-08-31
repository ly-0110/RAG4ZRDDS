"""Baseline Prompt v0（指南 §5 成员 C 第二条：只含两条硬规则）。

版本说明：
  * v0 只含两条硬规则，不做 Grounding/Abstention/版本冲突披露（第二周 §6.4 再扩）；
  * 引用约定与 docs/citation-contract-draft.md §3 对齐：答案内用 [n] 引用检索
    片段编号（1 基，对应 sources 数组下标），前端据此渲染可点击锚点。
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "你是 ZRDDS（臻融数据分发服务）产品知识库问答助手。\n"
    "回答必须遵守两条硬规则：\n"
    "1. 仅依据提供的检索内容作答，不得虚构检索内容中不存在的 API、参数、错误码或功能。\n"
    "2. 回答必须给出来源：用 [n] 标注对应的检索片段（n 为片段编号）。"
)

USER_TEMPLATE = "问题：{question}\n\n检索内容：\n{context}"


def build_messages(question: str, context: str) -> list[dict[str, str]]:
    """组装一轮对话消息：system=硬规则，user=问题 + 检索上下文。"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(question=question, context=context),
        },
    ]
