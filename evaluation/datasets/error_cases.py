"""错误案例集加载与校验（成员 C · 第三周 §7：混版本 + 错来源）。

文件 evaluation/datasets/error_cases.jsonl，每行一个 JSON 对象：
{
  "id": "EC-MV-001",
  "category": "mixed_version" | "wrong_source",
  "question": "...",
  "chunks": [{"source_id","source_name","source_type","version","section","page_print","text"}],
  "gold_behavior": "conflict_disclosure" | "abstention" | "source_priority",
  "gold_note": "..."
}

用途：供 D 的 run_experiment / 可靠性评测消费（生成侧在冲突 / 错来源下的行为回归）。
本模块只负责加载与结构校验，不做判分。
"""

from __future__ import annotations

import json
from pathlib import Path

DATASET = Path(__file__).resolve().parent / "error_cases.jsonl"

CATEGORIES = {"mixed_version", "wrong_source"}
GOLD_BEHAVIORS = {"conflict_disclosure", "abstention", "source_priority"}
MIN_PER_CATEGORY = 10  # 指南 §7：混版本、错来源各 ≥10 例


def load(path: str | Path = DATASET) -> list[dict]:
    """逐行读取 JSONL；空行跳过，坏行报可读错误。"""
    cases: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} 第 {lineno} 行 JSON 解析失败: {e}") from e
    return cases


def validate(cases: list[dict]) -> list[str]:
    """结构校验，返回问题列表（空 = 通过）。"""
    problems: list[str] = []
    for c in cases:
        cid = c.get("id") or "<无 id>"
        if not str(cid).startswith("EC-"):
            problems.append(f"{cid}: id 应以 EC- 开头")
        if c.get("category") not in CATEGORIES:
            problems.append(f"{cid}: category 非法 {c.get('category')!r}，允许 {sorted(CATEGORIES)}")
        if not (c.get("question") or "").strip():
            problems.append(f"{cid}: question 缺失")
        chunks = c.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            problems.append(f"{cid}: chunks 必须为非空列表")
        else:
            for i, ch in enumerate(chunks, start=1):
                if not (ch.get("text") or "").strip():
                    problems.append(f"{cid}: chunks[{i}].text 缺失")
                if not ch.get("source_id"):
                    problems.append(f"{cid}: chunks[{i}].source_id 缺失")
        if c.get("gold_behavior") not in GOLD_BEHAVIORS:
            problems.append(f"{cid}: gold_behavior 非法 {c.get('gold_behavior')!r}")
        if not (c.get("gold_note") or "").strip():
            problems.append(f"{cid}: gold_note 缺失")

    for cat in CATEGORIES:
        n = sum(1 for c in cases if c.get("category") == cat)
        if n < MIN_PER_CATEGORY:
            problems.append(f"{cat} 仅 {n} 例，需 ≥{MIN_PER_CATEGORY}")
    return problems


def counts(cases: list[dict]) -> dict[str, int]:
    """按类别计数。"""
    return {cat: sum(1 for c in cases if c.get("category") == cat) for cat in sorted(CATEGORIES)}
