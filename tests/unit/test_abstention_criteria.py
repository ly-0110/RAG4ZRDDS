"""拒答专项合判口径（2026-09-17 会签）回归测试。

验收条款是"20 题**全部不虚构**"，故合格态有两类：显式拒答，或有引用背书的事实性
否定；`confident`（既未拒答也未否定）才是唯一的失败态。这里锁的就是这条边界，
尤其是"没有引用的否定不算合格"。口径由来见 docs/week4-delivery-review.md §3.13⑤。
"""

from __future__ import annotations

from generation.abstention import classify_answer, is_factual_denial


class TestFactualDenial:
    def test_denial_with_citation_is_accepted(self):
        assert is_factual_denial(
            "ZRDDS 的 DomainParticipant 没有提供 connect() 方法 [2]。"
        )

    def test_denial_without_citation_is_not_accepted(self):
        """无出处的否定仍是无依据断言 → 不得算合格。"""
        assert not is_factual_denial("ZRDDS 不支持 RESTful API。")

    def test_positive_answer_with_citation_is_not_a_denial(self):
        assert not is_factual_denial(
            "调用 create_participant() 时需要传入 domainId 参数 [1]。"
        )

    def test_empty_answer(self):
        assert not is_factual_denial("")


class TestClassifyAnswer:
    def test_abstention_marker_wins(self):
        assert classify_answer("当前知识库无法确认该功能是否存在。") == "abstained"

    def test_denial_with_citation(self):
        assert classify_answer("该接口不属于 Topic，而是 DataReader 的方法 [5]。") == "factual_denial"

    def test_confident_answer_is_the_only_failure(self):
        assert classify_answer("ZRDDS 通过 XxxManager 提供该能力，参数为 A/B。") == "confident"

    def test_real_ab_001_shape_from_measured_run(self):
        """本机实测 AB-001 的真实形态（回答侧事实性否定 + 表引用）。"""
        answer = ("根据提供的检索内容，**ZRDDS 的 DomainParticipant 没有提供 `connect()` "
                  "方法用于主动建立网络连接**。根据 [2]（用户手册·第 48 页）中表 6-2"
                  "《DomainParticipant 的函数》列出的功能，不存在名为 `connect()` 的方法。")
        assert classify_answer(answer) == "factual_denial"
