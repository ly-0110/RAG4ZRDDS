# 可靠性测试报告（成员 C · 第四周 · v1.0）

> 指南 §8 成员 C 三项交付的载体：① Abstention 行为定版（20 题专项）② 全量终跑评测（Retrieval + Response 全指标 + 人工抽检 30 题）③ 可靠性测试报告与错误案例集终版。
> 本报告只陈述**已实现**与**已实测**，未跑的部分如实标注「留命令」或「void/blocked」，不虚报数值。

---

## 1. 状态总览

| 评测面 | 状态 | 说明 |
|---|---|---|
| 检索侧指标（§9.1） | **void / blocked** | 被 E 的标注 P0/P1 门禁卡住（`week4-delivery-review.md` §3.4/§5）：六题题干有损转码（Q021/Q023/Q028/Q059/Q060/Q119）、114/120 区间标注待收窄。`final_v1.yaml` 的 `expected_sources: null`，检索侧只落检索结果、不产指标 |
| 回答侧指标（§9.2） | **已实现 · 全量留命令** | 四项指标（faithfulness / answer_relevance / correctness / citation_accuracy）的 runner + judges 已交付并离线单测通过；冒烟 `--sample N` 可跑，全量留命令 |
| 拒答专项（§8.4 Abstention） | **已实现 · 全量留命令** | 20 题「不存在信息」专项集 + 机器可读拒答判定 + 专项 runner 已交付；20/20 拒答则退出码 0 |
| 错误案例集终版 | **已交付** | `error_cases.jsonl`（20 夹具）+ `error_cases_real.jsonl`（70 真实）+ `abstention_questions.jsonl`（20 拒答）三集统一 |
| 人工抽检 30 题（§9.3） | **清单已生成** | `make manual-review` 确定性抽 30 题产六问检查清单，签署结果见 §6 |

---

## 2. 检索侧（§9.1）—— void / blocked，如实标注

检索正式指标依赖 `expected_sources` 标注集，而该标注集当前被 E 的 P0/P1 门禁冻结（依据 `docs/week4-delivery-review.md` §3.4、§5）：

| 阻塞 | 内容 | 影响 |
|---|---|---|
| **P0** | Q021/Q023/Q028/Q059/Q060/Q119 六题题干经有损转码，非 ASCII 字符全部变字面 `?` | 乱码题干污染检索与计分，不能跑正式指标 |
| **P1** | 114/120 题为区间标注、其中 69 题全书级区间 `[7,288/289]`，页码条件名存实亡 | hit/mrr 会虚高或失真 |

**处置**：`configs/experiments/final_v1.yaml` 将 `evaluation.expected_sources` 置 `null`、`retrieval_metrics` 保留 `[hit_rate@5, mrr@5]` 但不产出（run_experiment 在缺失标注集时只记录检索结果）。检索侧指标待 E 的 P0/P1 清零并回写 `expected_sources` 后，用同一条全量命令补齐，不改任何机制。

> 参考基线（非正式，仅作量级参考）：struct_bm25 在 PR#36 标注上实跑 `hit@5=0.3667 / mrr@5=0.2575`（`week4-delivery-review.md` §3.4）。

---

## 3. 回答侧（§9.2）—— 四项指标

指南 §9.2 建议五维（Correctness / Faithfulness / Answer Relevance / Context Relevance / Citation Accuracy）。本阶段按口径沿用现有 `RESPONSE_METRICS` 四项，**不含** Context Relevance（`experiment_config.py` 的 `RESPONSE_METRICS` 常量未改动）：

| 指标 | judge | 判据 | 空检索兜底 |
|---|---|---|---|
| `faithfulness` | `judge_faithfulness` | 答案陈述是否忠实于给定检索片段，无片外编造 | 无检索内容 → 判 0 分，不调 LLM |
| `answer_relevance` | `judge_answer_relevance` | 答案是否切题；**正确拒答应评 5 分**（C4） | — |
| `correctness` | `judge_correctness` | 答案与检索内容的事实一致性（无 gold answer，度量「证据一致的正确性」） | 无检索内容 → 判 0 分，不调 LLM |
| `citation_accuracy` | `judge_citation_accuracy` | `[n]` 标注是否真实指向对应片段、支撑被引事实 | 无检索内容 → 判 0 分，不调 LLM |

**落地文件**：
- 机器可读拒答单一事实源：[generation/abstention.py](../generation/abstention.py)（`ABSTENTION_MARKERS` + `is_abstention()`，C5）。
- runner：[evaluation/runners/answer_eval.py](../evaluation/runners/answer_eval.py)（X2）——逐题 retrieve → generate → 拒答判定 → 逐指标判分 → 聚合均值。
- judges：[evaluation/judges/judge.py](../evaluation/judges/judge.py)——C2（解析失败显式 `parse_ok=False`，不再静默记 0）、C3（判分固定 `temperature=0.0`）、C4（relevance 奖励正确拒答）+ 新增 `judge_correctness` / `judge_citation_accuracy`。

**指标量纲与聚合**：每项 judge 输出 `score ∈ [0,1]`（0~5 归一化）；均值只统计 `parse_ok=True` 的样本，`parse_failed` 单独计数（区分「判 0 分」与「解析失败」）。

**执行**：
```bash
make answer-eval SAMPLE=5      # 冒烟：前 5 题，验证报告含 response 段 + 四指标
make experiment CFG=configs/experiments/final_v1.yaml   # 全量终跑（120 题）
```

---

## 4. 拒答专项（§8.4 Abstention）—— 20 题定版

「不存在信息」专项题集 [evaluation/datasets/abstention_questions.jsonl](../evaluation/datasets/abstention_questions.jsonl)，AB-001…AB-020，字段 `{id, question, category, note}`：

| category | 数量 | 含义 |
|---|---|---|
| `fabricated_api` | 4 | 杜撰不存在的 API（如 `connect()`） |
| `fabricated_error_code` | 3 | 杜撰不存在的错误码（如 E1003） |
| `fabricated_feature` | 7 | 杜撰不存在的功能/实体 |
| `cross_version_claim` | 3 | 跨版本断言（知识库无版本对比依据） |
| `out_of_scope` | 3 | 越界/非 ZRDDS 范畴 |

锚点全部来自审计已确立的「语料中不存在」事实（`connect()`、E1003、版本对比、第 300 页越界等，见 `evaluation/datasets/README.md` 与 demo-runbook 实测）。

**机器可读拒答判定**（`is_abstention()`）：命中 `无法确认` / `无法给出有依据` / `没有检索到` / `知识库中没有` / `未找到相关` 等标记串即判拒答；「不支持 X」这类**检索到的真值否定**不算拒答（避免把正确回答误判成臆造）。

**执行**（20/20 拒答则退出码 0，任一题虚构即非 0）：
```bash
make abstention
```

---

## 5. 错误案例集终版

三集统一，计数口径见 [evaluation/datasets/README.md](../evaluation/datasets/README.md)：

| 集 | 数量 | 性质 | 用途 |
|---|---|---|---|
| `error_cases.jsonl` | 20 | 手写夹具（混版本 10 + 错来源 10） | 多来源通路测试（冲突披露 / 拒答 / 优先级） |
| `error_cases_real.jsonl` | 70 | 真实案例（D 从四份实验报告 + 审计真值提取） | 验收项 5 载体；`test_real_error_cases.py` 锁定真实性 |
| `abstention_questions.jsonl` | 20 | 拒答专项 | 第四周 Abstention 定版验收 |

---

## 6. 人工抽检 30 题（§9.3）

指南 §9.3 要求每周随机抽 20~30 题人工检查。实现为 [scripts/sample_manual_review.py](../scripts/sample_manual_review.py)：`random.Random(0)` 确定性抽 30 题，产 §9.3 六问检查清单（是否回答 / 技术事实正确 / 文档依据 / Citation 准确 / 虚构 API / 混用版本）到 `evaluation/reports/manual_review.md`，供 C 逐题签署。

```bash
make manual-review
```

> 抽检结果以 `evaluation/reports/manual_review.md` 签署态为准；全量终跑后回填本表。

---

## 7. 全量终跑命令（留命令，待 E 标注清零后触发）

```bash
# 一键：检索侧（标注就绪后）+ 回答侧四指标 + 拒答判定，报告含 response 段
make experiment CFG=configs/experiments/final_v1.yaml

# 逐项冒烟
make answer-eval SAMPLE=30      # 回答侧前 30 题
make abstention                 # 20 题拒答专项
make manual-review              # 人工抽检 30 题清单
```

配置 [configs/experiments/final_v1.yaml](../configs/experiments/final_v1.yaml)（stage=product）与 `struct_multisrc_v1` 同 hash8（`d57f695e`），**与多来源配置共用同一索引目录** `indexes/struct_bge-m3_d57f695e`（1606 nodes），不会为 final_v1 另建一套索引；该索引当前**未构建**，首次全量运行会自动构建（`run_experiment` 缺索引即自动构建，等价 `make index CFG=configs/experiments/struct_multisrc_v1.yaml`，bge-m3 CPU 约 25 分钟）。`source_priority: [zrdds_dev_guide, user_manual]`（开发者指南 > 用户手册）。

---

## 8. 验证方式与当前结果

| # | 验证 | 结果 |
|---|---|---|
| 1 | `python -m pytest tests/ -q`（含新增 `test_abstention` / `test_answer_eval` + 扩展 `test_judges`） | C 域测试全绿；15 例失败为既有环境问题（跨盘符 tmp 路径、未建子索引、缺 `mcp` 包），与本域改动无关 |
| 2 | `python scripts/experiment_config.py configs/experiments/final_v1.yaml` | `[配置有效]`，hash8=`d57f695e`，复用多来源索引 |
| 3 | 拒答专项 `make abstention` | 留命令（需 LLM env + OpenRouter；20/20 拒答则退出码 0） |
| 4 | 回答评测 `make answer-eval SAMPLE=5` | 留命令（报告应含 `response` 段 + 四指标均值） |
| 5 | 回归 `make regression --only struct_v1` | 留命令（确认回答侧接入不改变检索可比字段） |
