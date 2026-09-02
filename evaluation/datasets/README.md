# evaluation/datasets/ —— 评测数据集

## 文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `questions.jsonl` | **占位集（15 题）** | 由成员 E 第一周冒烟集 `smoke.json` 转写；正式 80~120 题问题集由 E 按指南 §6.1 类型配比编写并交 C 审核口径后**整体替换**本文件 |
| `expected_sources.jsonl` | **尚无（占位版已于 2026-08-30 移除）** | 期望来源标注。占位版按 `smoke.json` 页码派生，经 Node 产物实证不可用（见下）；缺失时 `run_experiment.py` 只记录检索结果、不计算指标 |
| `expected_sources.draft.jsonl` | **草稿（E 初版重标，数据未核实，勿接入）** | 格式符合本 README 草案、`run_experiment.py` 可直接消费，保留作格式样例；但页码经 Node 产物抽查不合格——S001 称 9.7.1 在印刷 68（实为 7.3 SQL 过滤）、S003~S006 区间与第 11 章标注自相矛盾，仅 S002 与审计真值一致（2026-09-02，详见 AGENTS 当日记录）；且 id 为 S001~S015，与 `questions.jsonl` 的 Q001~Q015 不对应。**接入条件**：E 逐题对 PDF 核对（页码地面真值=页眉印刷数字）、id 与问题集对齐、C 定口径后，方可改名 `expected_sources.jsonl` 接入 |
| `smoke.json` | 第一周原始冒烟集（E 于 PR #13 重写，S001~S015 带自由文本页码） | 保留为来源依据，不直接参与评测（无任何脚本/配置引用）；页码主张同样未经核实 |

## questions.jsonl 字段（指南 §6.1）

```json
{"id": "Q001", "question": "...", "type": "debug", "version": "v2.3+", "difficulty": "medium"}
```

- `id` / `question` 为必填（`run_experiment` 校验）；`type` / `version` / `difficulty` 记录分类供分组分析。

## expected_sources.jsonl 字段（格式草案，口径待成员 C 定版）

```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [245, 249]}
```

- `question_id`：必填，对应 `questions.jsonl` 的 `id`；同一题允许多行（多个可接受来源）。
- `source_id` / `page_print` / `section_keyword` 至少给出一个；非空条件需**同时满足**才算命中。
- `page_print`：印刷页（印刷页 = 物理页 − 6），对照 Node 产物的 `printed_page_start/end`。单页写整数，区间写 `[lo, hi]`（闭区间）。
- 检索结果侧用于匹配的字段是 chunk 的 `printed_page_start`（引用呈现页），宽区间标注可覆盖跨页块。

**占位版为何移除（2026-08-30 实证）**：抽查 `data/processed/struct_v1.jsonl` 发现 `smoke.json`
页码与真实分布严重不符——如"安装/环境变量"实际位于印刷页 168~171（第11章 软件安装指南），
冒烟集却标注"第 3-5 页"；按印刷页或物理页解释均无法自洽。用不可靠标注算指标会误导结论，
故宁缺毋滥：正式标注由成员 E 随问题集对 PDF 逐题核对后重写，成员 C 审核口径。

## 与配置的对应关系

`configs/experiments/*.yaml` 的 `evaluation` 区块：

- `dataset` → 本目录 `questions.jsonl`
- `expected_sources` → 本目录 `expected_sources.jsonl`
- `retrieval_metrics` → `hit_rate@K / mrr@K / precision@K / recall@K`
- `sample_size` → 冒烟抽样（`run_experiment --sample N` 可临时覆盖）
