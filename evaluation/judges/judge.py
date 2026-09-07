"""LLM-as-judge 判分（成员 C · 第二周）：Faithfulness / Answer Relevance。

设计（指南 §6 成员 C 第一条）：
  * 复用 generation/llm.py 的 LLMConfig + complete_chat（非流式）——judge 需要
    一次性拿到完整回答再解析，流式增量不适合；
  * 让模型输出 JSON {"score": 0~5 整数, "rationale": "..."}，本模块负责稳健
    解析（JSON 失败退化为正则提取）并把 score 归一化到 [0,1]；
  * JudgeResult 独立于传输层，供 D 的 run_experiment 聚合、也供本地冒烟直接调用。

评分量纲：统一 0~5 整数（LLM 判分更稳），对外归一化 score∈[0,1]，raw_score 保留
原始 0~5 便于回溯。判分是 LLM 生成，天然有随机性；正式口径用固定低温度与同
judge 模型，回归对比才有意义（见 evaluation/reports 的 compare_baseline）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from generation.context_builder import build_context
from generation.llm import LLMConfig, complete_chat

_SCORE_RE = re.compile(r'"score"\s*:\s*(\d+)')


@dataclass(frozen=True)
class JudgeResult:
    """一次判分的结构化结果。score 已归一化到 [0,1]，raw_score 为原始 0~5。"""

    metric: str  # "faithfulness" | "answer_relevance"
    score: float  # 归一化 [0,1]
    raw_score: int  # 原始 0~5
    rationale: str

    @classmethod
    def from_model_output(cls, metric: str, text: str) -> "JudgeResult":
        raw, rationale = _parse(text)
        return cls(metric=metric, score=raw / 5.0, raw_score=raw, rationale=rationale)


def _parse(text: str) -> tuple[int, str]:
    """从模型输出稳健提取 (score, rationale)：先 JSON，失败退化为正则/原文。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
        score = int(data.get("score"))
        return _clamp(score), str(data.get("rationale", "")).strip()
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    m = _SCORE_RE.search(text)
    if m:
        return _clamp(int(m.group(1))), text
    return 0, text


def _clamp(score: int) -> int:
    return max(0, min(5, score))


# ---------------------------------------------------------------- 判分 prompt


FAITHFULNESS_SYSTEM = (
    "你是 RAG 系统的忠实度（Faithfulness）评测员。判断「回答」是否严格依据"
    "「检索内容」，有没有虚构检索内容中不存在的 API、参数、错误码或功能。\n"
    "评分（0~5 整数）：\n"
    "  5 = 完全忠实于检索内容，无虚构、无过度引申；\n"
    "  3 = 大体忠实，但有少量未标注的推断或过度引申；\n"
    "  0 = 大部分虚构，或与检索内容无关。\n"
    '只输出一行 JSON：{"score": <0~5 整数>, "rationale": "<一句话理由>"}'
)

FAITHFULNESS_USER = (
    "问题：{question}\n\n检索内容：\n{context}\n\n回答：{answer}"
)

RELEVANCE_SYSTEM = (
    "你是 RAG 系统的答案相关性（Answer Relevance）评测员。判断「回答」是否"
    "直接、完整地回应了「问题」，有没有答非所问或遗漏关键点。\n"
    "评分（0~5 整数）：\n"
    "  5 = 完整、直接回应问题；\n"
    "  3 = 部分回应，遗漏关键点或含无关内容；\n"
    "  0 = 答非所问，或基本未回应问题。\n"
    '只输出一行 JSON：{"score": <0~5 整数>, "rationale": "<一句话理由>"}'
)

RELEVANCE_USER = "问题：{question}\n\n回答：{answer}"


# ---------------------------------------------------------------- judge 入口


async def _judge(
    config: LLMConfig, metric: str, system_prompt: str, user_prompt: str
) -> JudgeResult:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    text = await complete_chat(config, messages)
    return JudgeResult.from_model_output(metric, text)


async def judge_faithfulness(
    config: LLMConfig,
    question: str,
    chunks: list[dict] | str,
    answer: str,
) -> JudgeResult:
    """判「回答」对「检索内容」的忠实度；chunks 为富引用（含 text）或已拼好的 context。"""
    context = build_context(chunks) if isinstance(chunks, list) else chunks
    if not context.strip():
        return JudgeResult(
            metric="faithfulness", score=0.0, raw_score=0, rationale="无检索内容可供对照"
        )
    user = FAITHFULNESS_USER.format(question=question, context=context, answer=answer)
    return await _judge(config, "faithfulness", FAITHFULNESS_SYSTEM, user)


async def judge_answer_relevance(
    config: LLMConfig, question: str, answer: str
) -> JudgeResult:
    """判「回答」对「问题」的相关性。"""
    user = RELEVANCE_USER.format(question=question, answer=answer)
    return await _judge(config, "answer_relevance", RELEVANCE_SYSTEM, user)
