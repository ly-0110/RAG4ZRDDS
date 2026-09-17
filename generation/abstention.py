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

import re

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


# ---------------------------------------------------------------- 合判口径（2026-09-17）
# 20 题拒答专项的验收条款是「全部不虚构」。实测（本机 2026-09-17，见
# docs/week4-delivery-review.md §3.13⑤）发现：模型对"ZRDDS 有 connect() 吗"这类
# 问题会**直接否定并给出语料出处**（"没有提供 connect() 方法" + 表 6-2 的可用函数），
# 这是更优的作答而非拒答措辞——只认拒答标志的口径会把它记成"未拒答"，闸门恒红。
# 故增补第二类合格作答：
#   合格 = 显式拒答 ∪ 事实性否定（且带 [n] 引用可核对）
# 「带引用」是硬条件：没有出处的否定仍是无依据断言，照旧计入虚构风险。
# 本口径是**机器初筛**，最终以人工抽检（`make manual-review` 六问清单）为准。
FACTUAL_DENIAL_MARKERS: tuple[str, ...] = (
    "不提供", "未提供", "没有提供", "不直接支持", "不支持", "不存在", "没有名为",
    "不属于", "并非", "并没有", "不包含", "未包含", "而非", "没有该",
)
_CITATION_RE = re.compile(r"\[\d+\]")


def is_factual_denial(answer: str) -> bool:
    """事实性否定 + 至少一处 `[n]` 引用 → 视为「有依据的否定」（合格作答）。"""
    text = (answer or "").strip()
    if not text or not _CITATION_RE.search(text):
        return False
    return any(m in text for m in FACTUAL_DENIAL_MARKERS)


def classify_answer(answer: str) -> str:
    """回答归类：`abstained`（显式拒答）/ `factual_denial`（有依据的否定）/
    `confident`（既未拒答也未否定 → 虚构风险，拒答专项闸门的唯一失败态）。"""
    if is_abstention(answer):
        return "abstained"
    if is_factual_denial(answer):
        return "factual_denial"
    return "confident"
