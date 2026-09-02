# evaluation/datasets/ —— 评测数据集

## 文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `questions.jsonl` | **冒烟集（15 题）** | 成员 E 第一周冒烟集，覆盖 API/配置/Error/Debug 等类型；正式 80~120 题问题集由 E 按指南 §6.1 类型配比编写并交 C 审核口径后**整体替换**本文件 |
| `expected_sources.jsonl` | **已创建（冒烟版）** | 期望来源标注，按 `smoke.json` 页码派生；正式评测需 E 对 PDF 逐题核对后重写，成员 C 审核口径 |
| `smoke.json` | 第一周原始冒烟集 | 成员 E 手写（自由文本 `expected_source`），保留为来源依据，不直接参与评测 |

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

## 与配置的对应关系

`configs/experiments/*.yaml` 的 `evaluation` 区块：

- `dataset` → 本目录 `questions.jsonl`
- `expected_sources` → 本目录 `expected_sources.jsonl`
- `retrieval_metrics` → `hit_rate@K / mrr@K / precision@K / recall@K`
- `sample_size` → 冒烟抽样（`run_experiment --sample N` 可临时覆盖）
