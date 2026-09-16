"""evaluation/runners/answer_eval.py 的单元测试（注入 fake chat_stream / judge，不联网）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from evaluation.judges.judge import JudgeResult
from evaluation.runners import answer_eval as ae


def _cfg(response_metrics):
    return SimpleNamespace(
        generation=SimpleNamespace(prompt_version="v2", llm_env_prefix="LLM_"),
        retrieval=SimpleNamespace(source_priority=[]),
        evaluation=SimpleNamespace(response_metrics=response_metrics),
    )


async def _fake_chat(messages):
    yield "当前知识库无法确认该功能是否存在。"


async def _fake_judge(metric, question, chunks, answer):
    return JudgeResult(metric=metric, score=1.0, raw_score=5, rationale="ok")


def _run(metrics, questions, retrievals, judge=_fake_judge, chat=_fake_chat):
    return asyncio.run(ae.evaluate_answers(
        _cfg(metrics), questions, retrievals, judge_fn=judge, chat_stream=chat))


def test_evaluate_detects_abstention_and_collects_metrics():
    res = _run(
        ["faithfulness", "answer_relevance"],
        [{"id": "Q1", "question": "q"}],
        {"Q1": [{"text": "正文", "source_id": "user_manual"}]},
    )
    assert res["Q1"]["abstained"] is True
    assert res["Q1"]["answer"] == "当前知识库无法确认该功能是否存在。"
    assert res["Q1"]["metrics"]["faithfulness"]["score"] == 1.0
    assert res["Q1"]["metrics"]["answer_relevance"]["score"] == 1.0


def test_evaluate_judge_receives_question_and_chunks():
    seen = {}

    async def judge(metric, question, chunks, answer):
        seen["question"] = question
        seen["chunks"] = chunks
        return JudgeResult(metric=metric, score=0.6, raw_score=3, rationale="x")

    chunks = [{"text": "正文", "source_id": "user_manual"}]
    _run(["faithfulness"], [{"id": "Q1", "question": "如何创建？"}], {"Q1": chunks}, judge=judge)
    assert seen["question"] == "如何创建？"
    assert seen["chunks"] == chunks


def test_aggregate_means_only_parse_ok():
    results = {
        "Q1": {"abstained": False, "metrics": {
            "faithfulness": {"score": 0.8, "raw_score": 4, "rationale": "", "parse_ok": True},
            "answer_relevance": {"score": 0.0, "raw_score": 0, "rationale": "", "parse_ok": False},
        }},
        "Q2": {"abstained": True, "metrics": {
            "faithfulness": {"score": 1.0, "raw_score": 5, "rationale": "", "parse_ok": True},
            "answer_relevance": {"score": 1.0, "raw_score": 5, "rationale": "", "parse_ok": True},
        }},
    }
    agg = ae.aggregate(results, ["faithfulness", "answer_relevance"])
    assert agg["faithfulness"]["mean"] == 0.9
    assert agg["faithfulness"]["n"] == 2
    assert agg["faithfulness"]["parse_failed"] == 0
    assert agg["answer_relevance"]["mean"] == 1.0
    assert agg["answer_relevance"]["parse_failed"] == 1


def test_build_response_section_shape():
    results = {"Q1": {"abstained": True, "answer": "无法确认", "metrics": {}}}
    section = ae.build_response_section(results, [])
    assert section["total"] == 1
    assert section["abstained"] == 1
    assert section["per_question"][0]["id"] == "Q1"
