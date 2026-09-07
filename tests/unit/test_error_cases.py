"""错误案例集加载与校验的单元测试（不联网，只校验数据形状与数量）。"""
from __future__ import annotations

from evaluation.datasets.error_cases import (
    CATEGORIES,
    MIN_PER_CATEGORY,
    counts,
    load,
    validate,
)


def test_load_returns_all_cases():
    cases = load()
    assert len(cases) >= 20
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id 必须唯一"


def test_validate_passes_on_ship_data():
    assert validate(load()) == []


def test_each_category_meets_minimum():
    c = counts(load())
    for cat in CATEGORIES:
        assert c[cat] >= MIN_PER_CATEGORY, f"{cat} 数量不足 {MIN_PER_CATEGORY}"
