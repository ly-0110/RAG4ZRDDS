"""error_cases_real.jsonl 的真实性回归（D · 验收项 5 补采，2026-09-07 会签）。

锁定补采案例的「真实」承诺——区别于 PR#19 的手写夹具（error_cases.jsonl）：
  1. 案例数 ≥ 20（指南 §6.5 验收线）
  2. 每条证据的 node_id 必须存在于对应配置索引的真实产物（防手写虚构回流）
  3. 双页码差恒为 6（页码真值契约）
  4. 三类案例非空（no_evidence_signal_missing / verified_wrong_top1 / cross_config_disagreement）

数据由 evaluation/datasets/collect_real_error_cases.py 从四份真实报告 + 8-30 人工审计真值
生成；报告重跑（如索引重建后）需重新执行该脚本再跑本测试。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
DATASET = HERE / "evaluation" / "datasets" / "error_cases_real.jsonl"
COLLECTOR = HERE / "evaluation" / "datasets" / "collect_real_error_cases.py"

sys.path.insert(0, str(COLLECTOR.parent))

from collect_real_error_cases import REPORTS, _load_nodes_index  # noqa: E402

EXPECTED_CATEGORIES = {
    "no_evidence_signal_missing",
    "verified_wrong_top1",
    "cross_config_disagreement",
}


def _cases() -> list[dict]:
    if not DATASET.exists():
        raise AssertionError(
            f"{DATASET.name} 不存在——先运行 collect_real_error_cases.py 生成"
        )
    return [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_real_error_cases_meet_acceptance_threshold():
    cases = _cases()
    assert len(cases) >= 20  # 指南 §6.5：「20 个以上真实错误案例」


def test_real_error_case_categories_are_populated():
    cases = _cases()
    seen = {c["category"] for c in cases}
    assert EXPECTED_CATEGORIES <= seen


def test_every_evidence_node_exists_in_real_products():
    """核心承诺：证据不是手写的——node_id 必须能在对应产物里找到。"""
    cases = _cases()
    indexes = {name: _load_nodes_index(prod) for name, (_, prod) in REPORTS.items()}
    missing = [
        c["id"] for c in cases
        if c.get("mode") in indexes
        and c.get("top1")
        and c["top1"]["node_id"] not in indexes[c["mode"]]
    ]
    assert missing == []


def test_page_numbering_contract_holds_in_evidence():
    cases = _cases()
    bad = [
        c["id"] for c in cases
        if c.get("top1")
        and c["top1"]["page_physical"] - c["top1"]["page_print"] != 6
    ]
    assert bad == []


def test_case_ids_are_unique():
    cases = _cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
