#!/usr/bin/env python3
"""
scripts/run_experiment.py — 统一评测脚本（D 维护，E 提供数据集）

职责（成员 D · 集成与实验平台）:
  * 读 yaml → 重建索引 → 跑评测集 → 落盘 reports/
  * E 提供 questions.jsonl / expected_sources.jsonl
  * C 定义判分口径

用法:
  python scripts/run_experiment.py --config configs/experiments/<实验>.yaml
  make experiment CFG=configs/experiments/<实验>.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec


def load_questions(dataset_path: Path) -> list[dict]:
    """加载问题集（E 维护）"""
    if not dataset_path.exists():
        raise FileNotFoundError(f"数据集不存在：{dataset_path}")
    questions = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def load_expected_sources(sources_path: Path) -> dict[str, list[dict]]:
    """加载期望来源标注（E 维护）"""
    # 按问题 ID 分组，方便判分
    sources_by_qid = {}
    if sources_path.exists():
        with open(sources_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    qid = rec["question_id"]
                    if qid not in sources_by_qid:
                        sources_by_qid[qid] = []
                    sources_by_qid[qid].append(rec)
    return sources_by_qid


def build_retriever(cfg):
    """构建检索器（B 实现）"""
    from retrieval.retriever import build_retriever
    return build_retriever(cfg)


def build_answer_stream(cfg):
    """构建生成器（C 实现）"""
    from generation.query_engine import build_answer_stream
    return build_answer_stream(cfg)


def evaluate_question(question: dict, retriever, answer_stream, expected_sources: list[dict]) -> dict:
    """评测单题：检索 + 生成 + 判分"""
    qid = question["id"]
    
    # 1. 检索
    start = time.perf_counter()
    chunks = retriever.retrieve(question["question"], cfg.retrieval.top_k)
    retrieval_time = time.perf_counter() - start
    
    # 2. 生成（如果启用）
    answer = ""
    if cfg.generation.enabled:
        stream = answer_stream.stream(question["question"], chunks)
        for token in stream:
            answer += token
    else:
        answer = "[生成实现尚未合入：等待成员 C 的 generation/ 包……]"
    
    # 3. 判分（C 实现）
    hit_count = 0
    if expected_sources and qid in expected_sources:
        for exp in expected_sources[qid]:
            # 简单判分：检查检索结果中是否有匹配的 source_id 和页码区间
            for chunk in chunks:
                if chunk.get("source_id") == exp.get("source_id"):
                    exp_page = exp.get("page_print")
                    chunk_page = chunk.get("page_print")
                    if exp_page is not None and chunk_page is not None:
                        if exp_page <= chunk_page <= exp_page + 5:  # 容差±5 页
                            hit_count += 1
                            break
    
    return {
        "qid": qid,
        "question": question["question"],
        "retrieved": chunks,
        "answer": answer,
        "retrieval_time_s": round(retrieval_time, 3),
        "hit_count": hit_count,
        "expected_hits": len(expected_sources) if expected_sources else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_experiment", description=__doc__)
    parser.add_argument("--config", "-c", default="configs/experiments/struct_v1.yaml")
    parser.add_argument("--sample", type=int, default=None, help="抽样评测（null=全集）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    args = parser.parse_args()

    # 加载配置
    cfg = ec.load(args.config)
    
    # 加载数据集（E 维护）
    dataset_path = REPO_ROOT / cfg.evaluation.dataset
    questions = load_questions(dataset_path)
    print(f"[experiment] 加载问题集：{len(questions)} 题")

    # 加载期望来源（E 维护）
    sources_path = REPO_ROOT / cfg.evaluation.expected_sources
    expected_sources_map = load_expected_sources(sources_path)
    print(f"[experiment] 期望来源标注：{sum(len(v) for v in expected_sources_map.values())} 条")

    # 构建检索器（B 实现）
    retriever = build_retriever(cfg)
    
    # 构建生成器（C 实现）
    answer_stream = build_answer_stream(cfg)

    # 抽样
    if args.sample is not None:
        import random
        rnd = random.Random(args.seed)
        questions = rnd.sample(questions, min(args.sample, len(questions)))
        print(f"[experiment] 抽样评测：{len(questions)} 题")

    # 评测
    results = []
    for q in questions:
        res = evaluate_question(q, retriever, answer_stream, expected_sources_map.get(q["id"], []))
        results.append(res)
    
    # 计算指标（C 定义口径）
    total = len(results)
    hits = sum(r["hit_count"] for r in results)
    hit_rate = hits / total if total > 0 else 0.0
    mrrs = []
    for r in results:
        retrieved = r["retrieved"]
        if not retrieved:
            continue
        best_rank = len(retrieved) + 1
        for i, chunk in enumerate(retrieved):
            if chunk.get("source_id") and any(
                e.get("source_id") == chunk.get("source_id") 
                for e in expected_sources_map.get(r["qid"], [])
            ):
                best_rank = i + 1
                break
        mrrs.append(1.0 / best_rank if best_rank <= len(retrieved) else 0.0)
    mrr = sum(mrrs) / len(mrrs) if mrrs else 0.0

    # 落盘报告（D 约定）
    report_path = REPO_ROOT / cfg.report.dir / f"{cfg.experiment.name}.json"
    report = {
        "schema": "rag4zrdds.report/v1",
        "experiment": cfg.experiment.name,
        "stage": cfg.experiment.stage,
        "config_hash8": ec.index_dirname(cfg),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+0800"),
        "duration_seconds": sum(r["retrieval_time_s"] for r in results),
        "index": {
            "dirname": ec.index_dirname(cfg),
            "backend": cfg.index.backend,
            "metric": cfg.index.metric,
        },
        "retrieval": {
            "mode": cfg.retrieval.mode,
            "top_k": cfg.retrieval.top_k,
        },
        "dataset": {
            "questions": str(dataset_path),
            "expected_sources": str(sources_path),
            "total": total,
            "evaluated": len(results),
        },
        "metrics": {
            "hit_rate@5": round(hit_rate, 4),
            "mrr@5": round(mrr, 4),
        },
        "per_question": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n[experiment] 报告已落盘：{report_path}")
    print(f"[experiment] Hit Rate@5 = {hit_rate:.4f}, MRR@5 = {mrr:.4f}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
