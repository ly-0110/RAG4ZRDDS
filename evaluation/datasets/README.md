# evaluation/datasets/ —— 评测数据集

## 文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `questions_multisource.jsonl` | **跨来源样例集（12 题）** | 基于用户手册 PDF 与 `zrdds_dev_guide` HTML 处理产物编写，覆盖 PDF+HTML 联合、HTML 示例核对和证据边界题 |
| `expected_sources_multisource.jsonl` | **跨来源样例集标注** | 与 `questions_multisource.jsonl` 配套；HTML 标注使用 `page_print: null`、真实 `section_keyword` 和 `source_url` |
| `smoke.json` | 第一周原始冒烟集（E 于 PR #13 重写，S001~S015 带自由文本页码） | 保留为来源依据，不直接参与评测（无任何脚本/配置引用）；页码主张同样未经核实 |
| `error_cases.jsonl` | **第三周夹具（成员 C，20 例，不计入验收项 5）** | 可靠性错误案例：混版本 + 错来源各 10 例，格式见下。**2026-09-07 会签决议**：经真值核对全部为手写虚构场景（引用第三周才接入的 `zrdds_dev_guide` 源、EC-MV-003 印刷页 300 超出手册最大 289、chunk 正文在真实产物中零命中、E1003 已证语料中不存在），按「宁缺毋滥」先例不计入验收项 5；其结构（question+chunks+gold_behavior）适合 HTML 接入后验证冲突披露，保留为多来源通路测试夹具 |
| `error_cases.py` | 加载/校验模块 | `load()` / `validate()` / `counts()`，供 run_experiment 或可靠性评测消费（**尚无管线消费，接线归属随 X2 议题定**） |
| `error_cases_real.jsonl` | **真实案例（D 补采，37 例，验收项 5 载体）** | 2026-09-07 由 `collect_real_error_cases.py` 从四份真实实验报告 + `audit-2026-08-30.md` 人工真值提取：`no_evidence_signal_missing` 20 例（审计判定「知识库无答案」的 5 题 × 4 配置，检索层仍自信返回证据）、`verified_wrong_top1` 8 例（top1 超出人工真值区间 ±1 页容差）、`cross_config_disagreement` 9 例（同题四配置 top1 页码不一致）。每条证据经机器校验：node_id 存在于对应产物、双页码差恒为 6 |
| `collect_real_error_cases.py` | 真实案例提取脚本 | 从 `evaluation/reports/*.json` 与审计真值生成 `error_cases_real.jsonl`；报告重跑（如索引重建后）需重新执行；`tests/unit/test_real_error_cases.py` 锁定真实性承诺 |
| `abstention.py` | 拒答专项加载/校验模块 | `load()` / `validate()` / `counts()` / `REQUIRED_COUNT=20`；`validate()` 校验 AB- 前缀、恰 20 题、category 合法、question/note 非空；被 `evaluation/runners/abstention_eval.py` 消费 |



```json
{"id": "Q001", "question": "...", "type": "debug", "version": "v2.3+", "difficulty": "medium"}
```

- `id` / `question` 为必填（`run_experiment` 校验）；`type` / `version` / `difficulty` 记录分类供分组分析。

## expected_sources.jsonl 字段（格式草案，口径待成员 C 定版）

```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [245, 249]}
```

- `source_id` / `page_print` / `section_keyword` 至少给出一个；非空条件需**同时满足**才算命中。
- `page_print`：印刷页（印刷页 = 物理页 − 6），对照 Node 产物的 `printed_page_start/end`。单页写整数，区间写 `[lo, hi]`（闭区间）。
- 检索结果侧用于匹配的字段是 chunk 的 `printed_page_start`（引用呈现页），宽区间标注可覆盖跨页块。

**占位版为何移除（2026-08-30 实证）**：抽查 `data/processed/struct_v1.jsonl` 发现 `smoke.json`
页码与真实分布严重不符——如"安装/环境变量"实际位于印刷页 168~171（第11章 软件安装指南），
冒烟集却标注"第 3-5 页"；按印刷页或物理页解释均无法自洽。用不可靠标注算指标会误导结论，
故宁缺毋滥：正式标注由成员 E 随问题集对 PDF 逐题核对后重写，成员 C 审核口径。

## error_cases.jsonl 字段（成员 C 第三周草案）

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


```json
{"id": "AB-001", "category": "fabricated_api", "question": "...", "note": "..."}
```

- `id`：`AB-<序号>`，唯一，AB-001…AB-020（恰 20 题）。
- `category`：`fabricated_api`（杜撰 API）| `fabricated_error_code`（杜撰错误码）| `fabricated_feature`（杜撰功能/实体）| `cross_version_claim`（跨版本断言）| `out_of_scope`（越界/非 ZRDDS 范畴）。
- `question` / `note`：题干与审计依据说明，均非空。
- 验收口径（`abstention_eval.py`）：逐题 retrieve → generate → `is_abstention()`（[generation/abstention.py](../../generation/abstention.py)），**20/20 拒答则退出码 0**，任一题虚构即非 0。
- `note` 字段只记录出题锚点，不参与判分——判分唯一依据是生成文本是否命中拒答标记，而非「题面预设答案」。

## 与配置的对应关系

`configs/experiments/*.yaml` 的 `evaluation` 区块：

- `expected_sources` → 本目录 `expected_sources.jsonl`
- `retrieval_metrics` → `hit_rate@K / mrr@K / precision@K / recall@K`
- `sample_size` → 冒烟抽样（`run_experiment --sample N` 可临时覆盖）
