"""拒答（Abstention）机器可读判定（成员 C · 第四周，回应 C5 反馈）。

把「是否拒答」从人读文案提升为可机读断言：judges 的 relevance 判分（C4）与
回答侧 runner（`evaluation/runners/answer_eval.py`）、20 题拒答专项
（`evaluation/runners/abstention_eval.py`）共用同一判定源，避免各处各自正则
漂移。

判定口径：回答命中任一「显式不确定/证据不足」标志即视为拒答。刻意**不收**
「不支持 X / 不存在 X」这类事实性否定——那可能是检索到的真值（正确回答），
而非"无法确认"。拒答在 prompt 里约定的话术是「当前知识库无法确认」（v1/v2），
空检索兜底串见 generation/query_engine._NO_EVIDENCE。
"""

from __future__ import annotations

# 显式"不确定/证据不足"标志（按出现即拒答）。顺序无关，命中任一即 True。
ABSTENTION_MARKERS: tuple[str, ...] = (
    "无法确认",
    "无法给出",
    "无法可靠判断",
    "没有检索到",
    "检索不到",
    "未检索到",
    "知识库中没有",
    "知识库没有",
    "知识库中暂无",
    "没有找到足够资料",
    "没有足够资料",
    "未找到相关",
    "无相关内容",
)


def is_abstention(answer: str) -> bool:
    """判断一段回答是否为「拒答」（显式表示知识库无法确认/证据不足）。

    仅做子串命中；大小写无关（兼容英文变体）。空串视为非拒答（调用方自行处置）。
    """
    text = (answer or "").strip().lower()
    if not text:
        return False
    return any(m.lower() in text for m in ABSTENTION_MARKERS)
