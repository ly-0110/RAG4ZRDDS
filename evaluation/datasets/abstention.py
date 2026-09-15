"""20 题「不存在信息」拒答专项数据集加载与校验（成员 C · 第四周 §8）。

文件 evaluation/datasets/abstention_questions.jsonl，每行一个 JSON 对象：
{
  "id": "AB-001",
  "category": "fabricated_api" | "fabricated_error_code" | "fabricated_feature"
             | "cross_version_claim" | "out_of_scope",
  "question": "...",
  "note": "为何判定知识库不存在该信息"
}

用途：`evaluation/runners/abstention_eval.py` 逐题检索→生成→断言拒答，
验证「20 个不存在信息专项题全部不虚构」（指南 §8 成员 C 第一条）。
本模块只负责加载与结构校验，不做判分。
"""

from __future__ import annotations

import json
from pathlib import Path

DATASET = Path(__file__).resolve().parent / "abstention_questions.jsonl"

CATEGORIES = {
    "fabricated_api",
    "fabricated_error_code",
    "fabricated_feature",
    "cross_version_claim",
    "out_of_scope",
}
REQUIRED_COUNT = 20  # 指南 §8 成员 C：20 个「不存在信息」专项题


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
        if not str(cid).startswith("AB-"):
            problems.append(f"{cid}: id 应以 AB- 开头")
        if c.get("category") not in CATEGORIES:
            problems.append(f"{cid}: category 非法 {c.get('category')!r}，允许 {sorted(CATEGORIES)}")
        if not (c.get("question") or "").strip():
            problems.append(f"{cid}: question 缺失")
        if not (c.get("note") or "").strip():
            problems.append(f"{cid}: note 缺失（需说明为何判定不存在）")
    if len(cases) != REQUIRED_COUNT:
        problems.append(f"题数 {len(cases)} != {REQUIRED_COUNT}（指南 §8 要求 20 题）")
    ids = [c.get("id") for c in cases]
    if len(ids) != len(set(ids)):
        problems.append("id 重复")
    return problems


def counts(cases: list[dict]) -> dict[str, int]:
    """按类别计数。"""
    return {cat: sum(1 for c in cases if c.get("category") == cat) for cat in sorted(CATEGORIES)}
