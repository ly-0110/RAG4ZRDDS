# evaluation/datasets/ —— 评测数据集

## 文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `questions.jsonl` | **正式问题集（120 题）** | 单来源（用户手册 PDF）；字段见下 |
| `expected_sources.jsonl` | **正式问题集标注** | 与 `questions.jsonl` 配套的真值出处；有效性由 `make audit` 把关 |
| `questions_multisource.jsonl` | **跨来源样例集（12 题）** | 基于用户手册 PDF 与 `zrdds_dev_guide` HTML 处理产物编写，覆盖 PDF+HTML 联合、HTML 示例核对和证据边界题 |
| `expected_sources_multisource.jsonl` | **跨来源样例集标注** | 与 `questions_multisource.jsonl` 配套；HTML 标注使用 `page_print: null`、真实 `section_keyword` 和 `source_url` |
| `smoke.json` | 早期冒烟样例集（15 题） | 自由文本页码、未经核实，仅留作来源依据，不参与评测（无任何脚本/配置引用） |
| `error_cases.jsonl` | **冲突行为夹具（20 例）** | 混版本 + 错来源各 10 例，格式见下；用于多来源通路的冲突披露 / 拒答 / 优先级行为测试 |
| `error_cases.py` | 加载/校验模块 | `load()` / `validate()` / `counts()`，供可靠性评测消费 |
| `error_cases_real.jsonl` | **真实案例（70 例）** | 由 `collect_real_error_cases.py` 从真实实验报告 + 人工审计真值提取（20 无证据信号缺失 + 40 已验证脱靶 + 10 跨方案分歧）。每条证据经机器校验：`node_id` 存在于对应产物、双页码差恒为 6 |
| `collect_real_error_cases.py` | 真实案例提取脚本 | 从 `evaluation/reports/*.json` 与 `audit-2026-08-30.md` 人工真值生成 `error_cases_real.jsonl`；报告重跑（如索引重建后）需重新执行；`tests/unit/test_real_error_cases.py` 锁定真实性承诺 |
| `abstention_questions.jsonl` | **拒答专项（20 题）** | 字段 `{id, question, category, note}`，格式见下 |
| `abstention.py` | 拒答专项加载/校验模块 | `load()` / `validate()` / `counts()` / `REQUIRED_COUNT=20`；校验 AB- 前缀、恰 20 题、category 合法、question/note 非空 |
| `audit-2026-08-30.md` | 人工审计记录 | 对早期问题集的逐题真值核对结论，是错误案例采集与拒答题集的锚点来源 |

## questions.jsonl 字段

```json
{"id": "Q001", "question": "...", "type": "debug", "version": "v2.3+", "difficulty": "medium"}
```

- `id` / `question` 为必填（`run_experiment` 校验）；`type` / `version` / `difficulty` 记录分类供分组分析。

## expected_sources.jsonl 字段

```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [245, 249]}
```

- `source_id` / `page_print` / `section_keyword` 至少给出一个；非空条件需**同时满足**才算命中。
- `page_print`：印刷页（印刷页 = 物理页 − 6），对照 Node 产物的 `printed_page_start/end`。单页写整数，区间写 `[lo, hi]`（闭区间）。
- 检索结果侧用于匹配的字段是 chunk 的 `printed_page_start`（引用呈现页），宽区间标注可覆盖跨页块。
- **标注必须逐题对照产物/原文核实**：`make audit` 以 Node 产物与章节树为判据（不调检索器）反向检查标注，凡"标注 = 检索 top-1 回显"的循环论证、题面实体零命中、页码越界等都会被拦下；verdict 非 pass 时不开指标通道。

## error_cases.jsonl 字段

```json
{"id": "EC-MV-001", "category": "mixed_version", "question": "...",
 "chunks": [{"source_id": "user_manual", "source_name": "...", "source_type": "pdf",
             "version": "2.0", "section": "...", "page_print": 245, "text": "..."}],
 "gold_behavior": "conflict_disclosure", "gold_note": "..."}
```

- `id`：`EC-<类别>-<序号>`，唯一（`MV`=混版本、`WS`=错来源）。
- `category`：`mixed_version`（混版本/来源冲突）| `wrong_source`（错来源）。
- `chunks`：命中片段（含来源元数据与正文），供生成侧组装 context 后做行为回归。
- `gold_behavior`：理想行为——`conflict_disclosure`（披露冲突）| `abstention`（拒答不臆造）| `source_priority`（按优先级采信）。
- `gold_note`：人工核对说明。
- 硬性要求（`error_cases.py` 的 `validate()` 校验）：混版本、错来源各 ≥10 例。

## abstention_questions.jsonl 字段

```json
{"id": "AB-001", "category": "fabricated_api", "question": "...", "note": "..."}
```

- `id`：`AB-<序号>`，唯一，AB-001…AB-020（恰 20 题）。
- `category`：`fabricated_api`（杜撰 API）| `fabricated_error_code`（杜撰错误码）| `fabricated_feature`（杜撰功能/实体）| `cross_version_claim`（跨版本断言）| `out_of_scope`（越界/非 ZRDDS 范畴）。
- `question` / `note`：题干与出题锚点说明，均非空。
- 判定口径（`abstention_eval.py` + [generation/abstention.py](../../generation/abstention.py)）：逐题 retrieve → generate → 归类，合格 = 显式拒答 ∪ 事实性否定 + `[n]` 引用；**全部合格则退出码 0**，任一题虚构即非 0。
- `note` 字段只记录出题锚点，不参与判分——判分依据是生成文本本身，而非「题面预设答案」。

## 与配置的对应关系

`configs/experiments/*.yaml` 的 `evaluation` 区块：

- `dataset` → 本目录 `questions.jsonl`（多来源配置用 `questions_multisource.jsonl`）
- `expected_sources` → 本目录 `expected_sources.jsonl`（或 `expected_sources_multisource.jsonl`）
- `retrieval_metrics` → `hit_rate@K / mrr@K / precision@K / recall@K`
- `sample_size` → 冒烟抽样（`run_experiment --sample N` 可临时覆盖）
