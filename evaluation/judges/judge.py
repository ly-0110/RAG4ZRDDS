"""LLM-as-judge 判分（成员 C · 第二周起）：Faithfulness / Answer Relevance /
Correctness / Citation Accuracy。

设计（指南 §6 / §9.2）：
  * 复用 generation/llm.py 的 LLMConfig + complete_chat（非流式）——judge 需要
    一次性拿到完整回答再解析，流式增量不适合；
  * 让模型输出 JSON {"score": 0~5 整数, "rationale": "..."}，本模块负责稳健
    解析（JSON 失败退化为正则提取）并把 score 归一化到 [0,1]；
  * JudgeResult 独立于传输层，供 D 的 run_experiment 聚合、也供本地冒烟直接调用。

评分量纲：统一 0~5 整数（LLM 判分更稳），对外归一化 score∈[0,1]，raw_score 保留
原始 0~5 便于回溯。判分是 LLM 生成，天然有随机性；正式口径用固定低温度（C3）与
同 judge 模型，回归对比才有意义。

C2 反馈：解析失败不再静默记 0——JudgeResult.parse_ok=False 标记「未能从模型输出
解析出分数」，聚合层据此与「真判 0 分」区分（宁可在报告里显式标失败）。
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
    """一次判分的结构化结果。score 已归一化到 [0,1]，raw_score 为原始 0~5。

    parse_ok=False 表示未能从模型输出解析出 score（此时 raw_score/score 按 0 记，
    但应被聚合层识别为「判分失败」而非「真 0 分」）。
    """

    metric: str  # "faithfulness" | "answer_relevance" | "correctness" | "citation_accuracy"
    score: float  # 归一化 [0,1]
    raw_score: int  # 原始 0~5
    rationale: str
    parse_ok: bool = True

    @classmethod
    def from_model_output(cls, metric: str, text: str) -> "JudgeResult":
        raw, rationale, ok = _parse(text)
        return cls(metric=metric, score=raw / 5.0, raw_score=raw,
                   rationale=rationale, parse_ok=ok)


def _parse(text: str) -> tuple[int, str, bool]:
    """从模型输出稳健提取 (score, rationale, ok)。

    ok=False 表示模型输出里没有任何可解析的 score（按 0 记，调用方可区分）。
    LLM 输出是不可信的边界数据：顶层可能是数组/字符串/null 而非对象，一律走
    正则兜底，不允许异常穿透中断整批评测。
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        try:
            return _clamp(int(data.get("score"))), str(data.get("rationale", "")).strip(), True
        except (TypeError, ValueError):
            pass
    m = _SCORE_RE.search(text)
    if m:
        return _clamp(int(m.group(1))), text, True
    return 0, text, False


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
    "特别说明（正确拒答不算跑题）：若「回答」明确表示「当前知识库无法确认」"
    "或同类拒答（在知识库确无此信息时），这本身就是对问题最诚实的回应，"
    "应评 5 分，不得因未给出正面答案而扣分。\n"
    "评分（0~5 整数）：\n"
    "  5 = 完整、直接回应问题（含正确拒答）；\n"
    "  3 = 部分回应，遗漏关键点或含无关内容；\n"
    "  0 = 答非所问，或基本未回应问题。\n"
    '只输出一行 JSON：{"score": <0~5 整数>, "rationale": "<一句话理由>"}'
)

RELEVANCE_USER = "问题：{question}\n\n回答：{answer}"

CORRECTNESS_SYSTEM = (
    "你是 RAG 系统的正确性（Correctness）评测员。判断「回答」的事实是否站得住："
    "与「检索内容」是否一致、有没有事实错误、是否真的回答了「问题」。\n"
    "注意：本题没有标准答案可对照，评的是「依据给定检索内容得出的回答是否"
    "自洽且无事实硬伤」；检索内容本身错误不应归咎于回答。\n"
    "评分（0~5 整数）：\n"
    "  5 = 事实正确、与检索内容一致、回答了问题；\n"
    "  3 = 大体正确，但有少量事实含糊或遗漏；\n"
    "  0 = 存在事实错误，或与检索内容明显矛盾。\n"
    '只输出一行 JSON：{"score": <0~5 整数>, "rationale": "<一句话理由>"}'
)

CORRECTNESS_USER = "问题：{question}\n\n检索内容：\n{context}\n\n回答：{answer}"

CITATION_SYSTEM = (
    "你是 RAG 系统的引用准确度（Citation Accuracy）评测员。判断「回答」中的"
    "[n] 引用标注是否真实指向对应编号的检索片段，并支撑被引事实。\n"
    "扣分情形：编号越界（引用不存在的片段）、被引事实在对应片段里找不到、"
    "张冠李戴（事实其实来自别的片段）、该标注却不标（给出技术事实但无 [n]）。\n"
    "评分（0~5 整数）：\n"
    "  5 = 引用编号全部有效且准确支撑被引事实；\n"
    "  3 = 引用大体准确，但有个别越界/张冠李戴或漏标；\n"
    "  0 = 引用大面积无效、虚构编号，或给出事实却完全无引用。\n"
    '只输出一行 JSON：{"score": <0~5 整数>, "rationale": "<一句话理由>"}'
)

CITATION_USER = "问题：{question}\n\n检索内容：\n{context}\n\n回答：{answer}"


# ---------------------------------------------------------------- judge 入口


async def _judge(
    config: LLMConfig, metric: str, system_prompt: str, user_prompt: str,
    *, temperature: float = 0.0,
) -> JudgeResult:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    text = await complete_chat(config, messages, temperature=temperature)
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
            metric="faithfulness", score=0.0, raw_score=0,
            rationale="无检索内容可供对照", parse_ok=True,
        )
    user = FAITHFULNESS_USER.format(question=question, context=context, answer=answer)
    return await _judge(config, "faithfulness", FAITHFULNESS_SYSTEM, user)


async def judge_answer_relevance(
    config: LLMConfig, question: str, answer: str
) -> JudgeResult:
    """判「回答」对「问题」的相关性（正确拒答视为满分，C4）。"""
    user = RELEVANCE_USER.format(question=question, answer=answer)
    return await _judge(config, "answer_relevance", RELEVANCE_SYSTEM, user)


async def judge_correctness(
    config: LLMConfig,
    question: str,
    chunks: list[dict] | str,
    answer: str,
) -> JudgeResult:
    """判「回答」的事实正确性（无标准答案，评「证据一致的正确性」，§9.2）。"""
    context = build_context(chunks) if isinstance(chunks, list) else chunks
    if not context.strip():
        return JudgeResult(
            metric="correctness", score=0.0, raw_score=0,
            rationale="无检索内容可供对照", parse_ok=True,
        )
    user = CORRECTNESS_USER.format(question=question, context=context, answer=answer)
    return await _judge(config, "correctness", CORRECTNESS_SYSTEM, user)


async def judge_citation_accuracy(
    config: LLMConfig,
    question: str,
    chunks: list[dict] | str,
    answer: str,
) -> JudgeResult:
    """判「回答」的 [n] 引用是否准确（编号有效 + 被引事实落在对应片段，§9.2）。"""
    context = build_context(chunks) if isinstance(chunks, list) else chunks
    if not context.strip():
        return JudgeResult(
            metric="citation_accuracy", score=0.0, raw_score=0,
            rationale="无检索内容可供对照", parse_ok=True,
        )
    user = CITATION_USER.format(question=question, context=context, answer=answer)
    return await _judge(config, "citation_accuracy", CITATION_SYSTEM, user)
