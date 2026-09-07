"""evaluation/judges 判分模块的单元测试（不联网，只测解析与 prompt 构造）。"""
from __future__ import annotations

import asyncio

import pytest

from evaluation.judges.judge import (
    FAITHFULNESS_SYSTEM,
    RELEVANCE_SYSTEM,
    JudgeResult,
    _parse,
    judge_faithfulness,
)
from generation.llm import LLMConfig


def _cfg() -> LLMConfig:
    return LLMConfig(provider="openai", base_url="http://x/v1", api_key="sk-test", model="m")


def test_parse_clean_json():
    raw, rationale = _parse('{"score": 4, "rationale": "基本忠实"}')
    assert raw == 4
    assert rationale == "基本忠实"


def test_parse_fenced_json():
    raw, _ = _parse('```json\n{"score": 3, "rationale": "x"}\n```')
    assert raw == 3


def test_parse_regex_fallback():
    raw, _ = _parse('评分："score": 5，很忠实')
    assert raw == 5


def test_parse_clamps_out_of_range():
    assert _parse('{"score": 99}')[0] == 5
    assert _parse('{"score": -3}')[0] == 0


def test_judge_result_normalizes_to_unit():
    r = JudgeResult.from_model_output("faithfulness", '{"score": 5, "rationale": "ok"}')
    assert r.metric == "faithfulness"
    assert r.raw_score == 5
    assert r.score == 1.0


def test_judge_prompts_request_score():
    assert "score" in FAITHFULNESS_SYSTEM
    assert "忠实度" in FAITHFULNESS_SYSTEM
    assert "相关性" in RELEVANCE_SYSTEM


def test_judge_faithfulness_empty_chunks_skips_llm():
    r = asyncio.run(judge_faithfulness(_cfg(), "问题", [], "回答"))
    assert r.score == 0.0
    assert r.rationale == "无检索内容可供对照"


# ------------------------------------------------- 回归：非对象 JSON 不得抛异常
# 2026-09-07 D 代修 C1：data.get 在非 dict 上抛 AttributeError，而 except 只接了
# JSONDecodeError/TypeError/ValueError → 一条畸形 judge 响应中断整批评测。


@pytest.mark.parametrize("raw", ['[1,2,3]', '"just a string"', "null", "true", "123"])
def test_parse_non_object_json_does_not_raise(raw):
    score, rationale = _parse(raw)
    assert score == 0
    assert rationale == raw


def test_parse_array_with_embedded_score_recovers_via_regex():
    # 顶层是数组但内部含 score：正则兜底应捞回分数，而非直接判 0
    score, _ = _parse('[{"score": 4, "rationale": "基本忠实"}]')
    assert score == 4
