# 回答级日志字段定义（v1.0 · 已落地）

> 版本 **v1.0（2026-09-17 定版）**　状态：**已会签（用户代行；C 事后追认）并已落地**——
> 实现见 `server/core/request_log.py::LoggedAnswerStream`（pipeline 层接线，
> HTTP 与 MCP 两条入口同覆盖；mock 不落盘），回归 `tests/unit/server/test_answer_log.py`（5 例）。
> 拟稿：成员 D（日志设施的 Owner）。字段定义按指南 §3.1 属成员 C，本稿只是把
> 「D 侧已有记录形状 + 生成侧可观测事实」摊开，供 C 增删改，避免继续空等。
> 落点：`{LOG_DIR}/answers.jsonl`（与 `requests.jsonl` / `retrievals.jsonl` 同级）。

## 1. 为什么单独要一级

三级日志现状：**请求级**（`requests.jsonl`，rid/method/path/status/耗时）与**检索级**
（`retrievals.jsonl`，`docs/retrieval-log-schema.md` v0.2 已会签）都已落地；**回答级**
自第二周挂在 `server/core/request_log.py:9`（"字段待成员 C 定"）至今——C 的生成侧
（Prompt v2 / judges / `answer_eval`）已于 PR#42 全部合入，字段定义仍缺位。

已有的落盘点覆盖了什么、缺什么：

| 落点 | 已有 | 回答级日志要补的增量 |
|---|---|---|
| `requests.jsonl` | 请求方法/路径/状态/耗时 | 生成**行为**（模型、Prompt 版本、拒答判定、终止原因） |
| `sources.jsonl` | 引用明细 + `question` + `answer` | 生成**参数与计时**（首 token 延迟、总时长、token 数）；且该文件的 `answer` 在失败/中止路径上可能是 `null` 或半截 |
| `retrievals.jsonl` | 检索侧全过程 | 检索结果**如何被用掉**（引用条数、是否拒答、是否放弃生成） |

## 2. 存储格式

| 项 | 约定（拟） |
|---|---|
| 文件 | `{LOG_DIR}/answers.jsonl`（`LOG_DIR` 默认为 `logs/`） |
| 格式 | 追加式 JSONL，一次 `/query`（或 MCP `query_knowledge_base`）请求**一条**；`ts` 由 `JsonlLog` 框架自动前置 |
| 生命周期 | 追加不截断；损坏行容忍（与既有三级日志同原则：日志绝不阻断服务） |
| 入库 | 不入 Git（`logs/` 已在 .gitignore）；正文只落本地 |
| 写盘时机 | SSE `done` 或 `error` 事件发出后写一条（含中止路径），保证"一问一条" |

## 3. 字段定义（拟，字段名待 C 定）

除注明外均必填。

| 字段 | 类型 | 说明 |
|---|---|---|
| `request_id` | str \| null | 关联 `requests.jsonl` / `retrievals.jsonl`；MCP 侧为 `mcp-` 前缀 rid；脚本直调为 `null` |
| `experiment` | str | 实验名（如 `final_v1`），与检索日志同源 |
| `config_hash8` | str | 配置身份 hash（仅索引身份段派生，R5 语义） |
| `prompt_version` | str | 实际使用的 Prompt 版本（`v0` / `v1` / `v2`），取自 `cfg.generation.prompt_version` |
| `model` | str | 生成模型名（`LLM_MODEL`） |
| `question` | str | 查询原文（不截断） |
| `answer` | str | 答案正文（不截断）。**与检索日志的 `text` 同立场：只落本地，不进报告、不进 wire** |
| `abstained` | bool | 是否判为拒答（`generation.abstention.is_abstention`，单一事实源） |
| `abstention_reason` | str \| null | 拒答成因：`no_retrieval`（检索空/无证据） \| `llm_abstain`（模型依证据拒答） \| null |
| `citation_count` | int | 随本次回答下发的引用条数（= `sources` 事件长度） |
| `source_ids` | array[str] | 引用来源 id 去重列表（如 `["user_manual","zrdds_dev_guide"]`），用于"答案是否真的用了某个来源"的离线分析 |
| `first_token_ms` | float \| null | 首个 token 延迟（流式）；非流式/未出词为 null |
| `duration_ms` | float | 从进入生成到流结束的墙钟耗时 |
| `token_chunks` | int | 下发 token 事件条数（**不是** tokenizer 计数，仅作粗粒度体量指标） |
| `finish_reason` | str | `stop` \| `length` \| `cancelled`（前端"停止生成"）\| `error` |
| `error` | str \| null | 错误摘要（与 SSE `error` 事件同文本），成功为 null |

## 4. 三条需要 D 表态的取舍（拟，供 C 否决）

1. **不再重复落引用明细**：`citation_count` / `source_ids` 只是索引；完整引用仍在
   `sources.jsonl`（`/sources/{rid}` 回查的唯一事实源），避免两处正文/字段漂移。
2. **中止语义与 `sources.jsonl` 对齐**：前端中止时服务端已把部分答案以"…（已终止）"
   留档（2026-09-17 实现），回答日志记 `finish_reason=cancelled` + 半截 `answer`，
   与 `sources.jsonl` 中同一 rid 的记录一致。
3. **判分结果不入此日志**：judges / `answer_eval` 是**离线评测**（`run_experiment`），
   结果落在 `evaluation/reports/*.json`，在线日志只记生成侧行为，避免把评测口径
   烘进运行日志。

## 5. 待 C 会签的问题

1. 字段取舍与命名是否照上表？尤其：`token_chunks` 是否建议换成真实 tokenizer 计数
   （需要引入 tokenizer 依赖，D 倾向不做）。
2. `answer` 是否确需落盘——`sources.jsonl` 已存同一份；若认为冗余，回答日志可去掉
   该字段，仅记体量与 `finish_reason`（D 不反对）。
3. `abstention_reason` 的两分类是否够用？是否需要区分"检索给了证据但模型仍拒答"
   与"证据不足且模型拒答"。
4. 是否需要记录 `top_k` / `filters`（检索侧已在 `retrievals.jsonl`，这里是否重复）。
5. 是否需要把 RAG 的 `source_priority` 生效情况（实际命中来源与优先级的差异）记一条。

## 6. 落地记录（2026-09-17 执行完毕，原计划留档）

1. ~~新增 `LoggedAnswerStream`~~ ✅ 已落地：包装 `pipeline.answer_stream`，`stop`/`error`/
   `cancelled` 三条出口各写一条（取消走 `GeneratorExit`，部分答案仍留档），沿用
   `JsonlLog`/`current_request_id`；写盘失败不阻断回答。
2. `server/api/query.py` 与 `server/mcp_server.py` 无需改协议（rid 已在 scope 内）。
3. 单测：成功路径、拒答路径、前端中止路径、上游报错路径各一例 + "日志写盘失败不阻断回答"。
4. `docs/api.md` 补一段"日志落点"说明（**字段无增删，端点契约不变**）。

---

> 本稿只定义字段与落点，不改任何现有行为；C 回签或改单后 D 再接线。
