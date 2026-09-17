"""回答侧评测 runner（成员 C · 第四周，X2 交付）。

把「逐题生成答案 → 调用 judges」串起来，回答侧指标（faithfulness /
answer_relevance / correctness / citation_accuracy）由此进评测矩阵。

与 run_experiment 的分工：
  * run_experiment 负责检索（富引用含 text 保留给本模块）与报告落盘；
  * 本模块只做「生成 + 判分」，`evaluate_answers` 被 run_experiment 在
    response_metrics 非空时调用；也提供独立 CLI（不依赖 run_experiment）。

依赖注入：judge_fn / chat_stream 可注入，离线单测不联网、不依赖真实 LLM，
与 test_generation.py / test_judges.py 的模式一致。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generation.abstention import is_abstention  # noqa: E402
from generation.llm import LLMConfig  # noqa: E402

# judge_fn(metric, question, chunks, answer) -> JudgeResult
JudgeFn = Callable[[str, str, list[dict], str], Awaitable]
# chat_stream(messages) -> AsyncIterator[str]
ChatStream = Callable[[list[dict[str, str]]], Awaitable]


# ---------------------------------------------------------------- 判分派发


def _default_judge_fn(judge_cfg: LLMConfig) -> JudgeFn:
    """把模块 judges 包装成统一签名 (metric, question, chunks, answer)。"""
    from evaluation.judges import judge as J

    async def judge(metric: str, question: str, chunks: list[dict], answer: str):
        if metric == "answer_relevance":
            return await J.judge_answer_relevance(judge_cfg, question, answer)
        fn = {
            "faithfulness": J.judge_faithfulness,
            "correctness": J.judge_correctness,
            "citation_accuracy": J.judge_citation_accuracy,
        }[metric]
        return await fn(judge_cfg, question, chunks, answer)

    return judge


# ---------------------------------------------------------------- 生成


async def _generate(
    cfg, question: str, chunks: list[dict], chat_stream: ChatStream | None
) -> str:
    from generation.query_engine import AnswerStream, build_answer_stream

    if chat_stream is None:
        # 真实通路：从 .env 读 LLM 配置。脚本/CLI 直调（本模块与
        # abstention_eval 的入口）不经服务启动路径，没人把 .env 导出进
        # os.environ——不显式加载则 .env 填好也报"生成侧 LLM 未配置"
        # （同类缺陷第四次：2026-08-31 服务端、build_pipeline 分支、
        # run_experiment、两个 runner CLI；见 week4 review §3.13）。
        from server.core.settings import load_env_file

        load_env_file()
        stream = build_answer_stream(cfg)
    else:
        stream = AnswerStream(
            chat_stream,
            prompt_version=cfg.generation.prompt_version,
            source_priority=cfg.retrieval.source_priority,
        )
    parts: list[str] = []
    async for token in stream.stream(question, chunks):
        parts.append(token)
    return "".join(parts)


# ---------------------------------------------------------------- 逐题评测


async def evaluate_answers(
    cfg,
    questions: list[dict],
    retrievals: dict[str, list[dict]],
    *,
    judge_fn: JudgeFn | None = None,
    chat_stream: ChatStream | None = None,
) -> dict[str, dict]:
    """逐题生成 + 判分。

    retrievals: qid → 富引用列表（含 text，供生成与 faithfulness/citation 对照）。
    返回 {qid: {"answer", "abstained", "metrics": {metric: {score, raw_score,
    rationale, parse_ok}}}}。
    """
    metrics = cfg.evaluation.response_metrics
    judge = judge_fn or _default_judge_fn(
        LLMConfig.from_env(cfg.generation.llm_env_prefix)
    )
    out: dict[str, dict] = {}
    for q in questions:
        qid, question = q["id"], q["question"]
        chunks = retrievals.get(qid, [])
        answer = await _generate(cfg, question, chunks, chat_stream)
        entry: dict = {"answer": answer, "abstained": is_abstention(answer), "metrics": {}}
        for m in metrics:
            r = await judge(m, question, chunks, answer)
            entry["metrics"][m] = {
                "score": r.score,
                "raw_score": r.raw_score,
                "rationale": r.rationale,
                "parse_ok": r.parse_ok,
            }
        out[qid] = entry
    return out


# ---------------------------------------------------------------- 聚合


def aggregate(results: dict[str, dict], metrics: list[str]) -> dict:
    """按指标聚合：均值只统计 parse_ok=True 的判分，parse 失败单独计数（C2）。"""
    agg: dict = {}
    for m in metrics:
        entries = [e["metrics"][m] for e in results.values() if m in e.get("metrics", {})]
        ok = [e for e in entries if e.get("parse_ok")]
        agg[m] = {
            "mean": round(sum(e["score"] for e in ok) / len(ok), 4) if ok else None,
            "n": len(ok),
            "parse_failed": len(entries) - len(ok),
        }
    return agg


def abstention_count(results: dict[str, dict]) -> int:
    return sum(1 for e in results.values() if e.get("abstained"))


def build_response_section(results: dict[str, dict], metrics: list[str]) -> dict:
    """把逐题结果折叠成报告里的 response 段（不 bump 报告 schema，新增可选键）。"""
    per_question = [
        {
            "id": qid,
            "abstained": e.get("abstained", False),
            "answer": e.get("answer", ""),
            "metrics": e.get("metrics", {}),
        }
        for qid, e in results.items()
    ]
    return {
        "metrics": aggregate(results, metrics),
        "abstained": abstention_count(results),
        "total": len(results),
        "per_question": per_question,
    }


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="answer_eval", description=__doc__)
    parser.add_argument("--config", default="configs/experiments/struct_v1.yaml")
    parser.add_argument("--sample", type=int, default=None, help="只评前 N 题（冒烟用）")
    args = parser.parse_args(argv)

    import experiment_config as ec

    try:
        cfg = ec.load(args.config)
    except ec.ConfigError as e:
        print(f"[answer_eval] 配置无效：\n{e}", file=sys.stderr)
        return 1
    if not cfg.evaluation.response_metrics:
        print("[answer_eval] 该配置 response_metrics 为空，无回答侧指标可评", file=sys.stderr)
        return 1

    questions = _load_questions(REPO_ROOT / cfg.evaluation.dataset, args.sample)
    retriever = _build_retriever(cfg)
    retrievals = asyncio.run(_retrieve_all(retriever, questions, cfg.retrieval.top_k))

    results = asyncio.run(evaluate_answers(cfg, questions, retrievals))
    section = build_response_section(results, cfg.evaluation.response_metrics)

    print(f"[answer_eval] 实验={cfg.experiment.name} 问题={len(questions)} "
          f"拒答={section['abstained']}")
    for m, v in section["metrics"].items():
        mean = f"{v['mean']:.4f}" if v["mean"] is not None else "n/a"
        print(f"[answer_eval]   {m:<18} = {mean}  (n={v['n']}, parse_failed={v['parse_failed']})")

    out = ec.report_path(cfg).parent / f"{cfg.experiment.name}.answer_eval.json"
    out.write_text(json.dumps(section, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[answer_eval] 明细 → {out.relative_to(REPO_ROOT)}")
    return 0


def _load_questions(path: Path, sample: int | None) -> list[dict]:
    import run_experiment as rx

    return rx.load_questions(path, sample)


def _build_retriever(cfg):
    from retrieval.retriever import build_retriever

    return build_retriever(cfg)


async def _retrieve_all(retriever, questions: list[dict], top_k: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for q in questions:
        out[q["id"]] = await retriever.retrieve(q["question"], top_k)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
