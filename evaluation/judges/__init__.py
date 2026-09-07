"""LLM-as-judge 判分（成员 C · 第二周）。

导出 Faithfulness / Answer Relevance 两个 judge 与 JudgeResult 结果类型。
判分需经 OpenAI 兼容 LLM（配置来自 .env 的 LLM_*，复用 generation.llm）。
"""
from evaluation.judges.judge import JudgeResult, judge_answer_relevance, judge_faithfulness

__all__ = ["JudgeResult", "judge_faithfulness", "judge_answer_relevance"]
