# 可靠性测试报告

> 本报告汇总**检索、回答、拒答、错误案例**四个评测面的实测结果，每项数字都能在
> `evaluation/reports/<实验名>.json` 中按题复核；完整实验对比见 `docs/experiment-results.md`。
> 检索指标的前置闸门为 `make audit`（标注有效性，判据只来自 Node 产物与章节树，不调检索器）。

---

## 1. 总览

| 评测面 | 结果 | 报告落点 |
|---|---|---|
| 检索指标（单来源 120 题） | `struct_v1` hit@5 **0.7833** / mrr@5 **0.6050**；三模式、三分块方案对比见结果分析 §3 | `evaluation/reports/struct_v1.json` 等 |
| 检索指标（跨来源 12 题） | `struct_multisrc_hybrid_rerank` mrr@5 **0.4792** 为最高；`_v1` hit@5 0.5833 | `evaluation/reports/struct_multisrc_*.json` |
| 回答侧（120 题） | faithfulness **0.8950** / answer_relevance **0.9883** / correctness **0.9633** / citation_accuracy **0.9583**（n=120、判分失败 0） | `evaluation/reports/final_v1.json` |
| 拒答专项（20 题） | **20/20 不虚构**（16 题显式拒答 + 4 题"事实性否定 + `[n]` 引用"），虚构风险 0 | `evaluation/reports/abstention_eval.json` |
| 错误案例集 | 20 手写夹具 + 70 真实案例 + 20 拒答题，共三集 | `evaluation/datasets/` |
| 人工抽检 30 题 | `make manual-review` 确定性抽取，产六问检查清单待逐题签署 | `evaluation/reports/manual_review.md` |

---

## 2. 检索侧

检索指标的分母是 `evaluation/datasets/expected_sources.jsonl`（120 题真值标注）。标注有效性
由 `make audit` 把关，当前 verdict 为 **pass**（循环论证指纹 0/120、题面乱码 0、阻断项 0）。

单来源 120 题、同一份 struct 分块下三种检索模式的实测（完整表见 `docs/experiment-results.md` §3）：

| 实验 | 模式 | hit@5 | mrr@5 |
|---|---|---|---|
| `struct_v1` | vector（bge-m3 + chroma，cosine） | **0.7833** | 0.6050 |
| `struct_hybrid` | hybrid（vector + BM25，RRF k=60） | 0.7500 | **0.6254** |
| `struct_bm25` | bm25（字符 bigram + ASCII 词整体） | 0.6833 | 0.5393 |

跨来源问题集（12 题 / 25 条期望来源）上，交叉编码器精排是唯一明确改善排序的手段
（mrr@5 0.4792，比 hybrid 高 0.046、比 vector 高 0.10），代价是单题从 ~0.8s 涨到 ~17s。

---

## 3. 回答侧（四项指标）

五维评测中的 Context Relevance 不在本阶段口径内，`RESPONSE_METRICS` 采用以下四项：

| 指标 | 判据 | 空检索兜底 |
|---|---|---|
| `faithfulness` | 答案陈述是否忠实于给定检索片段，无片外编造 | 无检索内容 → 判 0 分，不调 LLM |
| `answer_relevance` | 答案是否切题；**正确拒答应评 5 分** | — |
| `correctness` | 答案与检索内容的事实一致性（无 gold answer，度量「证据一致的正确性」） | 无检索内容 → 判 0 分，不调 LLM |
| `citation_accuracy` | `[n]` 标注是否真实指向对应片段、支撑被引事实 | 无检索内容 → 判 0 分，不调 LLM |

**落地文件**：

- 机器可读拒答单一事实源：[generation/abstention.py](../generation/abstention.py)
  （`ABSTENTION_MARKERS` + `is_abstention()` + `classify_answer()`）。
- runner：[evaluation/runners/answer_eval.py](../evaluation/runners/answer_eval.py)——
  逐题 retrieve → generate → 拒答判定 → 逐指标判分 → 聚合均值。
- judges：[evaluation/judges/judge.py](../evaluation/judges/judge.py)——判分固定 `temperature=0.0`；
  解析失败显式记 `parse_ok=False`，不静默记 0；relevance 体系奖励正确拒答。

**指标量纲与聚合**：每项 judge 输出 `score ∈ [0,1]`（0~5 归一化）；均值只统计 `parse_ok=True`
的样本，`parse_failed` 单独计数（区分「判 0 分」与「解析失败」）。

**实测（`final_v1`，120 题）**：

| 指标 | 均值 | n | 判分失败 |
|---|---|---|---|
| faithfulness | **0.8950** | 120 | 0 |
| answer_relevance | **0.9883** | 120 | 0 |
| correctness | **0.9633** | 120 | 0 |
| citation_accuracy | **0.9583** | 120 | 0 |

faithfulness 是四项里最低的：约一成答案被判"有超出检索依据的表述"，是最值得继续压的指标
（Prompt 迭代 / 更强 judge 模型 / 上下文裁剪）。

---

## 4. 拒答专项（20 题「不存在信息」）

题集 [evaluation/datasets/abstention_questions.jsonl](../evaluation/datasets/abstention_questions.jsonl)，
AB-001…AB-020，字段 `{id, question, category, note}`：

| category | 数量 | 含义 |
|---|---|---|
| `fabricated_api` | 4 | 杜撰不存在的 API（如 `connect()`） |
| `fabricated_error_code` | 3 | 杜撰不存在的错误码（如 E1003） |
| `fabricated_feature` | 7 | 杜撰不存在的功能/实体 |
| `cross_version_claim` | 3 | 跨版本断言（知识库无版本对比依据） |
| `out_of_scope` | 3 | 越界/非 ZRDDS 范畴 |

**判定口径**：合格 = 显式拒答 ∪ **事实性否定 + `[n]` 引用**（无出处的否定不算合格）。
命中 `无法确认` / `无法给出有依据` / `没有检索到` / `知识库中没有` / `未找到相关` 等标记串判为显式拒答；
而「不支持 X」这类**检索到的真值否定**是比拒答更好的作答，单列 `factual_denial` 计数。

**实测结果**：16 题显式拒答 + 4 题事实性否定（例：AB-001 答"DomainParticipant **没有提供**
`connect()` 方法"并列出表 6-2 可用函数；AB-004 指出恢复暂停分发的实际函数是
`DDS_Publisher_resume_publications` 而非 `resume()`），**虚构风险（confident）0 题**。
原始 20 条答案在 `evaluation/reports/abstention_eval.json` 逐题可查。

```bash
make abstention        # 合格 20/20 则退出码 0，任一题虚构即非 0
```

---

## 5. 错误案例集

三集统一，字段与计数口径见 [evaluation/datasets/README.md](../evaluation/datasets/README.md)：

| 集 | 数量 | 性质 | 用途 |
|---|---|---|---|
| `error_cases.jsonl` | 20 | 手写夹具（混版本 10 + 错来源 10） | 多来源通路测试（冲突披露 / 拒答 / 优先级） |
| `error_cases_real.jsonl` | 70 | 真实案例（20 无证据信号缺失 + 40 已验证脱靶 + 10 跨方案分歧） | 分块与检索改进的回归靶子；`test_real_error_cases.py` 锁定真实性 |
| `abstention_questions.jsonl` | 20 | 拒答专项 | 拒答行为验收 |

真实案例全部源自实际实验报告与人工审计真值，机器校验 `node_id` 在对应产物中存在、双页码差恒为 6。

---

## 6. 人工抽检 30 题

实现为 [scripts/sample_manual_review.py](../scripts/sample_manual_review.py)：`random.Random(0)`
确定性抽 30 题，生成六问检查清单（是否回答 / 技术事实正确 / 文档依据 / Citation 准确 /
虚构 API / 混用版本）到 `evaluation/reports/manual_review.md`，由评审人逐题签署。

```bash
make manual-review
```

---

## 7. 复现命令

```bash
make index                                          # 按实验配置建索引（缺则自动建，存在则复用）
make experiment CFG=configs/experiments/final_v1.yaml   # 检索 + 回答侧四指标 + 拒答判定
make answer-eval SAMPLE=30                          # 回答侧前 30 题（冒烟）
make abstention                                     # 20 题拒答专项
make manual-review                                  # 人工抽检 30 题清单
```

[configs/experiments/final_v1.yaml](../configs/experiments/final_v1.yaml) 与 `struct_multisrc_v1`
同索引身份（`d57f695e`），**共用同一索引目录** `indexes/struct_bge-m3_d57f695e`（1638 节点），
不会另建一套索引；`source_priority: [zrdds_dev_guide, user_manual]`（开发文档 > 用户手册）。
