"""Prompt v2（第三周 §7 成员 C：多来源 Context + 冲突披露 + 来源优先级）。

相对 v1 的增量（§8.4 可靠性策略提前至本周）：
  * 规则 5（Conflict disclosure）：不同来源对同一内容说法不一致时，明确
    指出各来源分别说了什么并标注冲突，不得只取其一或掩盖分歧；
  * 来源优先级（Source priority）：按 retrieval.source_priority 注入，
    冲突时优先采信高优先级来源。

引用约定与 v0/v1 一致（[n] 下标，1 基）。source_priority 为 None/空时不
注入优先级话术，行为退回 v1。
"""

from __future__ import annotations

from generation.source_labels import SOURCE_CATEGORY

SYSTEM_PROMPT = (
    "你是 ZRDDS（臻融数据分发服务）产品知识库问答助手。\n"
    "回答必须遵守以下五条规则：\n"
    "1. 仅依据提供的检索内容作答，不得虚构检索内容中不存在的 API、参数、错误码或功能。\n"
    "2. 回答必须给出来源，用 [n] 标注对应的检索片段（n 为片段编号）。\n"
    "3. 若检索内容不足以回答问题，明确说明「当前知识库无法确认」，不要猜测或补全。\n"
    "4. 若不同检索片段对同一内容存在版本差异，必须指出具体版本，不得含糊带过。\n"
    "5. 若不同来源对同一内容给出不一致说法，必须明确指出各来源分别说了什么并标注冲突，"
    "不得只取其一或掩盖分歧。"
)

USER_TEMPLATE = "问题：{question}\n\n检索内容：\n{context}"


def _priority_note(source_priority: list[str] | None) -> str:
    """把来源优先级列表渲染为话术；空/None 时返回空串（不注入）。"""
    if not source_priority:
        return ""
    labels = " > ".join(SOURCE_CATEGORY.get(s, s) for s in source_priority)
    return (
        "\n来源优先级（高→低）："
        + labels
        + "。当不同来源说法冲突时，优先采信高优先级来源；"
        "若高优先级来源无相关内容，再参考低优先级来源并说明所用来源。"
    )


def build_messages(
    question: str, context: str, source_priority: list[str] | None = None
) -> list[dict[str, str]]:
    """组装一轮对话消息：system=五条硬规则（+ 可选优先级话术），user=问题 + 上下文。"""
    system = SYSTEM_PROMPT + _priority_note(source_priority)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": USER_TEMPLATE.format(question=question, context=context)},
    ]
