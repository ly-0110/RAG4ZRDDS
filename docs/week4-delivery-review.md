# 第四周交付记录（成员 D）

> **v0.7（2026-09-14）**：新增 **D 交付八：标注真值核对工具**（§4.8，`scripts/audit_annotations.py` + `make audit`）。判据**只来自 A 的产物与章节树、不调用检索器**，因此能抓出"标注=检索回显"这类自证循环；现库核对结果 verdict=blocked：120 题中 **48 题标注页答不对题**、**6 题题面实体全库零命中**（已逐一 grep 双产物核验为真阳性，且已导出为机器发现的真·拒答案例供 C 专项集）、13 题纯中文需人工、循环指纹 44/120=0.3667。它同时是 `--with-metrics` 的前置门禁——"宁缺毋滥"从约定变成可执行检查。全套单测 320 → **340**。
> **v0.6（2026-09-14）**：新增 **D 交付六：W1 过渡处置（方案 B，api.md v0.11）**（§4.6）与 **交付七：reranker 权重离线预取**（§4.7）。回查通道（`/sources/{rid}` 与 MCP `get_sources`）每条引用附带 `source_url`，**SSE wire 仍严格 7 字段**（实测确认）；真实产物装载 1606 条映射 / 1305 条带 URL。**冒烟脚本抓到一个真实缺陷**：MCP 成功路径第二次 `store.put` 覆盖了未富化记录——已修并调整比对口径。`BAAI/bge-reranker-v2-m3` 2.2GB 已缓存，B 落地即可离线加载。全套单测 314 → **320**。
> **v0.5（2026-09-14）**：新增 **D 交付五：Reranker 落地前的 D 侧配套**（§4.5）——引用制判定收敛为单一事实源 `experiment_config.uses_reference_index()`，`build_index` 跳过 / `--list` 父子标注 / `run_experiment` 子索引检查三处改判（避免 B 的 `hybrid_rerank` 复用子索引时被误建 25 分钟自有索引），schema 放宽 `hybrid_rerank.components` 为可选并新增拒绝 `vector/bm25` 误填。**回归矩阵已铺满 8 个实验**（§1.3）：首轮 3 pass/3 incomparable/2 no_baseline，提基准后第二轮 **8/8 pass**，零回归；全套 **314/314** 绿。未决新增第 6 项（reranker 权重离线预取，§7）。
> **v0.4（2026-09-14）**：新增 **D 交付四：Feedback 落库接缝**（§4）——`POST /feedback` + `{LOG_DIR}/feedback.jsonl` 四级日志 + api.md **v0.10**（D 侧提案待 E/C 会签；既有端点形状零变化，不阻塞前端）。单测 7 例、live 实测三条（含跨重启归因与"未知 rid 零落盘"）。演示题单第 5 题（RapidIO QoS）实测补录：top-1 = 10.21 RapidIOConfigQosPolicy 印刷 147/物理 153。**至此指南 §8 的 D 三项全部落地**（回归自动化 / 打包与 README / Demo 环境）。
> **v0.3（2026-09-14）**：新增 **D 交付三：打包与 README**（§3）——按用户决策走"make 链路真验证"。修掉 `make setup` 建 venv 而其余目标全用裸 `python` 的脱节（此前"三行命令可跑"名不副实），README 全文重写（含逐步骤耗时实测、live 后端三选、回归用法、已知限制如实登记），`.env.example` 补本地 Ollama 通路与 HF 离线提示；`make help` 中文在 GBK 控制台乱码已改 ASCII。**验证缺口如实标注**：`make setup` 的 venv 全新安装未在本机跑通（需重下 2GB+ 且改动在用环境）；Dockerfile/compose 未交付（本机无 docker）。
> **v0.2（2026-09-14）**：新增 **D 交付二：Demo 环境打通**（§2）——生成侧实际出词首次在本机 live 通路实测成功（第三周至今的缺口销项），四段演示场景（单来源定位/无证据拒答/跨来源联合/Hybrid 走服务通路）全部落真值与耗时，成文 `docs/demo-runbook.md` v0.1。**同时更正第三周我自己写错的验收口径**：`source_url` 从未进入 `SourceRef` wire 与 `api.md`，故"HTML 引用跳 URL"并未闭环（缺口 W1，§2.3）。
> **v0.1（2026-09-14）**：首版。周计划见项目记忆 `project-week4-plan.md`（指南 §8 D 三项 / §10 回归机制 / §19 Week 4 验收）。本版记录 **D 交付一：回归自动化落地**，以及分支状态、跨成员依赖与阻塞、待拍板决策点、Week 4 验收对照。
> 记录人：成员 D。验证口径沿用四步：基线核对 → pytest 全套 → 契约核对 → 真值/端到端实测。

---

## 1. D 交付一：回归自动化（指南 §8 D 任务 1 · §10 机制生效）

### 1.1 交付物

| 文件 | 内容 |
|---|---|
| `scripts/run_regression.py`（新，~330 行） | 一键回归矩阵：实验发现 → 跑实验 → 与历史/基准报告比对 → 四态判定 + 退出码 |
| `scripts/run_experiment.py` | 报告 schema 升 **`rag4zrdds.report/v1.1`**：新增 `artifacts` 三份输入产物指纹；新增 `_artifact_fingerprints(cfg)` |
| `scripts/build_index.py` | 指纹算法抽出通用 `sha12_file(path)`，`_nodes_file_sha12` 委托之（**单一事实源**，R6 教训：算法副本必造成恒不匹配） |
| `Makefile` | 新增 `regression`（`REG_ARGS` 透传）与 **`test`**（此前 make 里根本没有单测入口） |
| `.gitignore` | 忽略回归的本机产物 `evaluation/reports/runs/`、`regression_2*.json`；`regression_latest.*` 与 `baseline/` 入库 |
| `tests/unit/test_run_regression.py`（新，36 例） | 闸门/明细/指标/变更映射/发现/紧凑锚点/main 失败聚合 |

### 1.2 机制设计要点

1. **可比性闸门（本次最关键的一条）**：报告此前只带 `config_hash8`。R1（PR#11）与 R4（PR#13）两次事故同根——**配置未变、磁盘产物被旧基线 PR 换掉**，只看 hash8 会让这类差异伪装成"可比"，从而把输入变更误记成性能回归（或反之掩盖真回归）。v1.1 报告额外记录 `nodes_file_sha12` / `questions_sha12` / `expected_sources_sha12`；比对前任一不符 → 判 `incomparable` 并列出原因，**不出 regression 结论**。旧版 v1 报告无 artifacts 同样判不可比（首次运行会看到，重跑即自愈）。
2. **双通道（宁缺毋滥不变量）**：
   - 明细通道（默认）：与标注无关，比 top-K 命中集合重合率、rank-1 一致率、空结果题数、耗时。重合率口径 = `|A∩B| / max(|A|,|B|)`（**不是 Jaccard**：top_k=5 换 1 条 Jaccard 只剩 0.667 会误报，重合系数为 0.8 恰好落在默认阈值上）。
   - 指标通道（`--with-metrics` 显式开）：真值标注定版后启用，指标下跌超 `--metric-tol`（默认 0.02）判 regression。默认关闭并在摘要标注"静默（标注未定版）"——现库 120 条标注仍是检索反推的循环版（week3 review §2.5），指标已算但不参与判定。
3. **变更 → 范围映射（§10 的 7 类变更）**：`--changed-only` 读 `git diff`（相对 `--base`，默认 `origin/develop` + 工作区）。`data_pipeline/`、`retrieval/`、`data/processed/`、`requirements.txt`、`scripts/`（D 的 ingest/build_index/配置校验/实验运行）任一改动 → **全量**；只改 `configs/experiments/X.yaml` → 只回归 X；只改生成侧 → 提示不纳入矩阵；判定器自身（`scripts/run_regression.py`）豁免，否则改进判定器会自触发全量。规则倾向偏全（漏跑比多跑危险）。
4. **历史不丢**：`run_experiment` 是覆盖式写报告，回归器在跑之前把旧报告归档到 `reports/runs/{name}__{生成时间}.json`；`--promote` 写 `reports/baseline/{name}.json` **紧凑锚点**（只留判定所需头部字段 + 每题 `node_id` 列表，340KB → 99KB，且锚点不带题干与标注原文）。
5. **退出码可挂 CI**：`regression`/`failed` → 1（总体 FAIL）；`incomparable`/`warn`/`missing`/`no_baseline` → 0（总体 REVIEW）；全清 → 0（PASS）。

### 1.3 实测证据（本机，2026-09-14）

- `python -m pytest tests/` → 本交付 **302/302 绿**（266 → +36）；随交付四/五追加至 **314/314**。
- **正向闭环**：`--only struct_bm25` 首轮 `incomparable`（历史报告为 v1 无指纹）→ 重跑 → `pass（vs 上次 pass / vs 基准 pass）`，结论 PASS、退出码 0。
- **真实实验复现性**：`--only struct_v1,struct_bm25` 连跑两轮，第二轮两实验均 `top-K 重合 1.0 / rank-1 一致 1.0 / hit_rate@5 delta +0.0000`，耗时 17.5s（真实 bge-m3 向量检索）与 0.6s（bm25）——同索引同产物的确定性复现得到实证。
- **负向验证（不破坏基线的前提下）**：把阈值抬到 `--min-overlap 1.0001` → 判 `regression`、总体 FAIL、**退出码 1**；`--with-metrics` 在零差值重跑下仍 `pass`（闸门不误伤）。
- **紧凑锚点**：`--promote` 后 `baseline/*.json` 由 340KB 级报告压到 46~108KB，比对照常成立（有单测锁定）。
- **全量矩阵已就位**：8 个实验首轮 = `3 pass / 3 incomparable / 2 no_baseline`（历史报告无 artifacts 指纹 + multisrc 两份首次进矩阵）；`--promote` 提基准后**第二轮 8/8 pass**（vs 上次与 vs 基准双通道），零回归零失败。矩阵里 `hybrid_v1` top-K 重合 **0.9883**（其余 1.0），与第三周记录的"RRF 并列边界非确定性"同源，落在阈值内不误报——属"被机制看见、但没被误报成回归"的正例。
- 落盘：`evaluation/reports/regression_latest.{json,md}`（矩阵摘要）+ `runs/` 归档（本机，已 gitignore）。
- **`--changed-only` 用真实历史三情形验证**（不是构造样本）：相对 `5d925c2`（本周 12 提交，改了 `scripts/`+`server/`+`configs/`）→ 正确推断**全量 8 实验**；相对 `c056f5d`（只改 docs 与删 `server/openai_compat/` 占位）→ 正确判**无需回归**；单改 `configs/experiments/struct_bm25.yaml` → 只选中该实验。

### 1.4 边界与未覆盖

- 检索侧八个实验均已进矩阵并有基准；**回答侧仍空**——`response_metrics` 需 C 的 runner（§6），Week 4 验收项"有自动/半自动 Evaluation"目前只覆盖检索侧。

---

## 2. D 交付二：Demo 环境打通（指南 §8 D 任务 3 · 含第三周遗留销项）

### 2.1 生成侧实际出词首次实测（第三周至今的"未验证"缺口）

前置链路由 D 在本机启动并验证：Ollama `0.33.3`（11434，模型 `qwen3.5-9b` 8.8GB）→ `models/llm_gateway.py`（11500，转原生 `/api/chat` 强制 `think:false`）→ `.env` 的 `LLM_BASE_URL` 指向网关 → `make serve` live。

- 网关冷启动首次出词 **8.2s**（含 8.8GB 权重加载），输出干净无思考串。
- 应用侧 `/healthz` = `{"status":"ok","mode":"live"}`，检索器预热在绑端口前完成（live 启动预热决策继续生效）。
- **结论：SSE `sources → token×N → done` 全链路真实出词成立**，第三周记录里"生成侧实际出词未验证"一项现已实测通过。

### 2.2 四段演示场景实测（详见 `docs/demo-runbook.md` v0.1）

| 场景 | 配置 | 实测（rid） | 关键判据 |
|---|---|---|---|
| 单来源精确定位 | `struct_v1` | 9.0s / token×372（`33a22b78cb88`） | top-1 = 10.7 DurabilityQosPolicy，**印刷 127 / 物理 133**；答案不虚构"语言级枚举默认值" |
| 无证据拒答 | `struct_v1` | 7.6s / 6.7s | `E1003`（已证不存在）与"第 300 页"（手册最大印刷页 289）均明确"无法确认"，并逐条说明检到的片段是什么 |
| 跨来源联合 + 冲突披露 | `struct_multisrc_v1` | 29.0s / token×1280（`19ed56607bd4`） | 5 条引用两来源共存（HTML 函数页 ×4 + 手册 8.3.1 印刷 80）；答案主动区分 **C API vs C++ 风格接口** |
| Hybrid 走服务通路 | `struct_multisrc_hybrid` | 19.2s（`837a938406c8`） | 分数 **0.0276~0.0318**（RRF 量纲，满量程 2/61，与 api.md v0.9 一致，非 cosine 0.7x）；引用制复用两路子索引、零重建 |

可观测性同步实测：`/sources/<rid>` 返回 200（question + 798 字 answer + 5 引用，首条印刷页 127）；`logs/requests.jsonl` / `retrievals.jsonl` / `sources.jsonl` 三处均可按同一 rid 关联（`config_hash8=0a7830b7`、`index_dirname=struct_bge-m3_0a7830b7`、`mode=vector`、`latency_ms` 落盘）。

附带踩坑（已写进 runbook §5）：Git Bash 用 curl 发中文 body 会按 GBK 编码，网关 JSON 解码 500——**是客户端编码问题，不是服务缺陷**，演示与脚本一律用 UTF-8 客户端。

### 2.3 缺口 W1：`source_url` 从未进入 wire（含对第三周验收口径的更正）

实测链路：A 的 HTML 产物 `source_url` 1305/1305 非空 ✅ → 但 `retrieval.retriever.to_source_refs` 只投影 `SOURCE_REF_FIELDS` 七字段（`node_id/source_id/source_name/section/page_print/page_physical/score`），**`source_url` 被丢弃** → `docs/api.md` 全文 0 处定义 `source_url` → `web/` 前端 0 处引用。

后果：**HTML 引用只能显示文件名**（如 `group___c_publication.html`），用户点不回 Doxygen 原文页。

**更正**：`docs/week3-delivery-review.md` §3 我曾把"Citation 能区分来源"判为 ✅ 并写了"HTML 引用跳 URL"——那是**数据层（Node metadata）事实被当成了端到端能力**，四步审查里漏了"wire + 前端消费"这一环。本次实测予以更正。

处置：属跨成员契约变更（B 的投影字段 + C 的 citation 组装 + E 的前端跳转 + D 的 api.md），2026-09-13 会签只决定过"暂不增补 `source_type`"，未覆盖 `source_url`。

**已按用户拍板执行方案 B（§4.6）**：D 单方在**回查通道**（`/sources/{rid}` 与 MCP `get_sources`）附带 `source_url`，api.md 升 **v0.11**；SSE wire 保持 7 字段不变（实测确认），因此不阻塞任何人、也不需要 B/C/E 先动代码。把 `source_url` 正式扩进 `SourceRef` 仍是待会签项（若 E 希望直接从 SSE 渲染链接，就得走方案 A）。

### 2.4 边界（本轮未覆盖）

- 场景 5（RapidIO QoS 精确 token 题）已实测补录：top-1 = 10.21 RapidIOConfigQosPolicy 印刷 147/物理 153，top-3 = 10.22 RapidIOControllerQosPolicy（148），top-4/5 = 21.2 RapidIO通信配置（256），与手册第 10 章 QoS 区间吻合。
- 演示服务当前跑在默认配置 `struct_v1`（`.env` 的 `RAG_EXPERIMENT_CONFIG`）；切多来源/hybrid 只需改该键重启，四场景实测值均已记录在 runbook。
- Ollama 与网关为本会话后台启动的长驻进程，重启机器后需按 runbook §2 重新拉起。

---

## 3. D 交付三：打包与 README（指南 §8 D 任务 2 · 按决策走 make 链路真验证）

### 3.1 修掉的真实缺陷

`make setup` 建 `.venv` 并往里装依赖，但**其余全部目标用裸 `python`/`uvicorn`** —— venv 纯属装饰，干净环境照 README 走会用错解释器（系统 python 里可能什么都没装），"三行命令内可跑"名不副实。修法：`VENV_DIR ?= .venv` + 平台判定（Windows `Scripts/python.exe` / POSIX `bin/python`）+ `PY := $(if $(wildcard ...),$(VENV_PY),python)`，所有目标统一走 `$(PY)`，`serve` 改 `$(PY) -m uvicorn`（裸 `uvicorn` 在 venv 外的 PATH 上未必存在）。

实测两个分支都成立：无 `.venv` 时 `make -n ingest` → `python scripts/ingest.py ...`；存在 venv 时（用临时目录桩验证）→ `<venv>/Scripts/python.exe scripts/ingest.py ...`。`VENV_DIR` 可覆盖，便于单测与 CI 注入。

另修一处自己刚引入的可用性问题：`make help` 打中文在 Windows GBK 控制台必乱码（实测输出 `褰撳墠瑙ｉ噴鍣?`），help 五行改纯 ASCII，详细说明放 README（UTF-8 文件查看无碍）。

### 3.2 README 与 .env.example

- **README 全文重写**（此前仍是第一周脚手架版：指向模板 `example_v1.yaml`、写着"第一周脚本落地后生效"、缺 `experiment/inspect/mcp/test/regression` 目标、还链向只存在于本机的 `AGENTS.md`——该文件不入 Git，对克隆者是死链，已删）。新结构：三行命令 + 逐步骤耗时实测表 + 两个网络坑（HF 离线开关、勿设 `HF_ENDPOINT`）+ live 后端三选（本地 Ollama / 云端兼容 API / 只检索不生成）+ make 目标表 + 配置驱动与 hash8/指纹/hybrid 引用制 + 回归与退出码 + `docs/` 全索引 + 目录 Owner 表 + **当前状态与已知限制**（reranker / 标注 void / W1 / 容器化 / semantic 超长块，逐条如实登记）。README 内 15 个链接存在性已程序化核对，0 缺失。
- **`.env.example` 补齐复现信息**：新增注释形式的本地 Ollama 通路（`LLM_BASE_URL=http://127.0.0.1:11500/v1` + 网关为何存在 + `LLM_API_KEY` 仍必填——已核 `generation/llm.py` 对 BASE_URL/API_KEY/MODEL 三者缺失即报错）与 Embedding 段的 HF 离线/直连提示。

### 3.3 本机实测清单

| 命令 | 结果 |
|---|---|
| `make -n ingest serve`（无 venv） | 回落系统 `python` / `python -m uvicorn` ✅ |
| `make -n ingest VENV_DIR=<临时 venv>` | 选中 `<venv>/Scripts/python.exe` ✅ |
| `make ingest` | 1.4s 完成，产物路径正常，内容语义未变 |
| `make test` | **302 passed** ✅ |
| `make inspect` | 质检全 0、结论"通过" ✅ |
| `RAG_MODE=mock make serve APP_PORT=8001` | `/healthz` = `mode:mock`（进程环境变量优先于 `.env` 的既定语义成立），`/query` = `sources → token×13 → done` ✅ |
| `make serve`（live，8000） | §2 已实测：预热后绑端口、四场景真实出词 ✅ |

### 3.4 验证缺口与未交付项（如实说明）

- **`make setup` 的 venv 全新安装未在本机跑通**：会重新下载 torch / sentence-transformers 等 2GB+，且改变本机在用环境，代价与风险大于收益。README 的 setup 行因此只标"视网络"。**这是本交付唯一的验证缺口——汇报时不得声称"干净环境已实测"。**
- **Dockerfile / docker-compose 未交付**：本机 `docker` 命令不存在（实测 `command not found`）。三选一路线中按用户决策选了"只做 make 链路"。若评审要求容器形态，需先装 Docker Desktop（WSL2）再补，估 0.5~1 天独立工作量。

---

## 4. D 交付四 ~ 八：Feedback 落库 / Reranker 配套 / W1 过渡处置 / 权重预取 / 标注真值核对

E 的第四周任务是"反馈按钮与数据落库"，但**落库属 D 的日志设施**——按既定分工，D 先把服务端与契约做出来，E 只需在答案卡片加两个按钮发一次 POST。

### 4.1 实现

- `server/api/feedback.py`：`POST /feedback` → 201 `{status, feedback_id, request_id, rating}`；记录追加 `{LOG_DIR}/feedback.jsonl`，与 requests/retrievals/sources 构成**四级日志**，全部可按 `request_id` 关联。
- `server/core/schema.py::FeedbackRequest`：`rating` 限定 `up|down`（细化原因走 `comment`，不扩枚举）；`node_ids` 可选 ≤20。
- `docs/api.md` 升 **v0.10**（新增端点小节 + 变更记录；顺带把头部"模式现状"更新到 2026-09-14 实况：本地 Ollama 通路已实测、`LLM_BASE_URL/API_KEY/MODEL` 缺一即启动报错）。

### 4.2 三个刻意的设计取舍

1. **未知 `request_id` → 404 拒绝，不照单收下**：脱离具体回答的"整体满意度"无法归因，收下只会生产孤儿数据（与"宁缺毋滥"同源）。
2. **`node_ids` 做归属校验**：不属于该次引用的节点直接 400 并列出越界项——前端把 rid 与 node 配错对是最可能的实现错误，服务端挡住比事后清洗便宜。
3. **不落答案正文**：答案已在 `sources.jsonl`，反馈记录只存 `question` 摘要 + `answer_present` + `cited_nodes`，避免长答案被逐条复制而膨胀。

### 4.3 验证

- 单测 **7 例**（`tests/unit/server/test_feedback.py`）：成功落盘字段齐、comment/node_ids 落盘、`/feedback` 自身进请求级日志、未知 rid 404 且**不留记录**、`node_ids` 越界 400 且不留记录、`rating` 非枚举 422、缺 `request_id` 422。全套 **309/309** 绿。
- live 实测三条：对**上一轮服务会话遗留的 rid** `837a938406c8` 打 up → 201（跨重启仍可归因，靠 `sources.jsonl` 水合）；伪造 rid `ffffffffffff` → 404 可读且零落盘；新生成 rid 带 `node_ids` 打 down → 201。见 `logs/feedback.jsonl`。

### 4.4 状态

契约标注为 **D 侧提案、待 E/C 会签**（两档 rating 是否够 E 的 UI 用、是否需 `answer_version` 之类归因字段由 E 定）。既有 `/query`、`/sources`、`/healthz` 形状零变化，**前端不改也能继续跑**，因此本项不阻塞任何人。

### 4.5 D 交付五：Reranker 落地前的 D 侧配套（`717286e`）

B 本周要交 `hybrid_rerank`。D 侧此前把"无自有索引（引用制）"按 `mode == "hybrid"` 字面写在三处（`build_index.cmd_build` 跳过、`--list` 父子标注、`run_experiment._ensure_index` 子索引检查）。**若 B 的精排同样复用子索引，这三处会各自漂移**，最坏情况是 `run_experiment` 为一个引用制精排实验白建 25 分钟没人用的索引并污染 `indexes/`。

- 新增单一事实源 `experiment_config.uses_reference_index(cfg)`：`mode ∈ {hybrid, hybrid_rerank}` 且给了 `components` 即引用制；三处调用点全部改判。
- schema 放宽但更严：`hybrid_rerank` 的 `components` **可选**（形态由 B 定——"引用制+精排"或"自有索引+精排"都走得通），给了就校验引用 yaml 存在；**新增拒绝** `vector`/`bm25` 误填 `components`（这类配置错误过去会静默生效）。
- `configs/experiments/README.md` 的 `components` 行同步该语义，并注明判定唯一处。
- 测试 **+5 例**（真值表 / 两类校验 / 门面跳过并断言"不应产生自有索引目录" / `run_experiment` 子索引复用路径）。
- **端到端证据**：重构后 `make regression REG_ARGS=--only struct_hybrid` 正常复用两路子索引（`0a7830b7` + `677d777f`）并出报告；随后全量矩阵 8/8 pass（§1.3）。

**权重离线预取**：已按用户拍板预取完成（§4.7）。

### 4.6 D 交付六：缺口 W1 的过渡处置（方案 B，api.md **v0.11**）

用户拍板"只改 `/sources` 回查接口（D 单方可做）"。实现：

- `server/core/pipeline.py`：`Pipeline` 新增 `source_urls`（node_id → 原文 URL），live 分支启动时从本实验的 Node 产物建表（`node_id ← chunk_id` 映射已锁定）并打印装载规模；产物缺失 → 空表，不报错。
- `server/core/schema.py::with_source_urls`：契约层唯一投影函数，HTTP 与 MCP 两条回查通路共用；**构造副本**，绝不原地改 `wire_sources`（否则 URL 会顺着同一对象漏进 SSE 帧）。
- `server/api/query.py` / `server/mcp_server.py`：只有 `store.put` 的记录带该字段；SSE 事件与 MCP 工具返回值仍是 7 字段。
- 实测：多来源题 5 条引用 **4 条 HTML 带真实 URL**（`https://docs.zrtechnology.com/cdoc/html/group___c_publication.html`）、PDF 为 `null`；**SSE 响应体经程序化检查不含 `source_url`**；真实产物装载规模 1606 条映射 / 1305 条带 URL（与 A 的契约一致），单来源 PDF = 0 条。
- 测试 **+6 例**（`tests/unit/server/test_source_url_backfill.py`：映射读取含坏行/回退/缺文件、回查带键、SSE 不带键、JSONL 落盘、未知节点为 null）。

**冒烟脚本抓到一个真实缺陷**：`make smoke-mcp` 首次失败，根因是 MCP 成功路径的**第二次 `store.put` 仍在写未富化的 `wire`**，把先前带 URL 的记录覆盖掉（回读取最后一条）。只跑单测漏不掉它——`test_mcp_server` 的成功路径断言恰好也抓到了。已修，并把冒烟脚本的回查一致性检查改为按 v0.11 语义比对（剥掉 `source_url` 后必须逐字段相等，且只允许多这一个键）。

**仍未闭合**：`source_url` 正式进 `SourceRef` wire（方案 A）需 B 改投影 + C 改 citation 组装 + E 改渲染，等会签；URL 的 base_url 仍是文档站占位值，待例会确认正式域名。

### 4.7 D 交付七：reranker 权重离线预取

`BAAI/bge-reranker-v2-m3` 已缓存到本机 HF hub（**2.2GB**，`model.safetensors` + tokenizer 全套，直连下载成功）。B 落地 `hybrid_rerank` 时可直接离线加载（配 `HF_HUB_OFFLINE=1`），不必在演示当天赌网络。

### 4.8 D 交付八：标注真值核对工具（`scripts/audit_annotations.py` + `make audit`）

第三周我给的"E 整改路径"只有一句"逐题对 PDF 核对"，缺可执行的验收手段——**没有工具，整改就无法被验证，只能靠口头承诺**。本次把它做成一条命令，也是指标闸门的前置门禁。

**为什么判据不能来自检索**：第二、三周两次事故的共性就是"标注 = 检索 top-1 回显"，用检索结果给检索打分。本工具的判定只读 **A 的产物与章节树**（`printed_page_start/end`、块正文、块标题），**不调用任何检索器**；报告 top-1 只用来算"反推指纹"比例，绝不当真值。

**判据（阻断项）**：`PAGE_OUT_OF_RANGE`（页码越出该来源真实页区间，如手册印刷页最大 289）· `PAGE_NO_CHUNK`（标注页无任何块承载）· `TERM_NOT_FOUND`（关键词在章节树/块标题/正文三处皆零命中）· `SECTION_PAGE_MISMATCH` / `TERM_PAGE_MISMATCH`（关键词所属章节或出现页与标注页矛盾）· **`QUESTION_TOKEN_OFF_PAGE`**（题干技术 token 不在标注页 ±2 页内 → 这页回答不了这题）· **`QUESTION_TOKEN_ABSENT`**（题面实体全库零命中）· HTML 来源标了印刷页 · 缺标注/多余题号。非阻断：`NO_TOKEN_PROBE`（纯中文题干，无 token 可机检，交人工）、`CIRCULAR_TOP1`（聚合比例超阈值才判 `suspect_circular`）。

**现库实测（verdict=blocked，退出码 1）**：120 题中 **48 题 `QUESTION_TOKEN_OFF_PAGE`**（标注页答不对题）、**6 题 `QUESTION_TOKEN_ABSENT`**、13 题无 token 可检、循环指纹 44/120=0.3667（未达 0.9 阈值，说明"错位"比"整批反推"更普遍）。

零命中六题已逐一核验（防误判）：`matched_count`(Q021/Q028) · `status_kind`(Q023) · `keyindex`(Q059) · `encoding_vendor_id`(Q060) · `readerthreadconfigqospolicy`(Q119) 在 PDF 产物与 1606 条合并产物中 **grep 均为 0 次**，且其标注指向无关章节（Q119 问线程配置却标到"24.2 Licence授权方式"第 276 页）→ **题面实体不存在，属真阳性**。

**双重产出**：`evaluation/reports/annotation_audit.{json,md}`（E 的逐题回炉清单，含"token 实际出现在哪几页"）；`--emit-abstention` 导出的 6 题是**机器发现的真·无证据题**（`evaluation/reports/abstention_candidates.jsonl`），可直接补强 C 的 Abstention 专项集——第三周 C 那 20 例因手写虚构被判不计入验收，这批的来源是产物反证。

**闸门关系**：`make audit` 退出码非 0 → 不得开 `make regression REG_ARGS=--with-metrics`，六份 void 报告也不得刷成"指标"。这一条把"宁缺毋滥"从口头约定变成可执行检查。

---

## 5. 分支与开工前置状态

- 分支起点 `feature/server-platform` = `5d925c2`（与 origin 同步）；**PR#31 由用户提交，仍待 squash 合入 develop**（远端 develop 落后本地多个提交）。
- 用户决策（2026-09-14）：**先把本周内容做完，再发新的 PR**；因此本地在 `5d925c2` 之上继续累积提交，暂不合入、暂不改远端。
- 本周本地提交：`2ecd6c4` 交付一 回归自动化 → `ff929bf` 本记录 v0.1 → `f05114f` 交付二 Demo 环境 + v0.2 → `dfff5da` 交付三 打包与 README + v0.3 → `b60f78f` 交付四 Feedback 落库 + api.md v0.10 + v0.4 → `717286e` 交付五 reranker 配套 → `69cd312` 回归矩阵基线（8 实验）→ `6c8f0a7` 本记录 v0.5 → 本次提交 交付六/七（W1 回查附带 source_url + api.md v0.11 + reranker 权重预取）+ 本记录 v0.6。
- **指南 §8 D 三项全部落地**：①回归自动化 ✅ 实测（§1）②打包 = README/make 链路 ✅ 实测，容器形态按决策未做（§3.4）③最终 Demo 环境 ✅ 四场景实测（§2）。**额外交付**：E 任务 1 落库侧（§4.1~4.4）、B reranker 配套与权重预取（§4.5/§4.7）、W1 过渡处置（§4.6）。全套单测 266 → **320**。
- 索引状态：六套全部可用且指纹匹配，本轮回归与全部 Demo **未触发任何重建**（复用链路正常；hybrid 走引用制）。

## 6. 跨成员依赖与阻塞（截至本版实测）

| 事项 | 归属 | 实测现状 | 对 D/Week4 的影响 |
|---|---|---|---|
| 真值标注（逐题对 PDF 核对） | E | 循环 + 非规范模型副本产物未修；**本次机器核对（`make audit`，判据只来自产物）**：120 题中 **48 题标注页答不对题**、**6 题题面实体全库零命中**、13 题纯中文需人工，与规范报告 top-1 仅 44/120 吻合 | 指标闸门只能默认关闭；六份 void 报告无法刷新；Week4 验收项 1/2/3 继续阻塞。**整改清单已可生成**：`evaluation/reports/annotation_audit.md` 逐题列出"token 实际出现在哪几页" |
| Reranker（§8.2） | B | `retrieval/retriever.py:154` 仍 `NotImplementedError("hybrid_rerank 待第四周实现")` | "Reranker 有实验数据"验收项拿不到；**D 侧已全部备好**（`uses_reference_index` 收敛 + 三处改判 + 5 测试 §4.5；bge-reranker-v2-m3 权重 2.2GB 已离线缓存 §4.7），只等 B 的实现 |
| `answer_eval.py` runner（X2） | C | `evaluation/runners/` 仍只有 `.gitkeep` | 回答侧指标无法进矩阵；D 的 `run_experiment` 保持 `response_metrics` 非空即拒绝的现有语义 |
| semantic 超长块 | A | `data_pipeline/chunkers/semantic.py:63` 的 `self.max_chars` 仍无消费点 | `semantic_v1` 已进矩阵（用旧代码产物的既有索引，pass）；A 一旦替换产物 → 指纹翻转 → 需重建索引（约 529s）+ `--promote` 重提基准 |
| Prompt 版本一致性（议题 8） | C/D | `struct_bm25.yaml` 仍 `prompt_version: v0` | 配置在 D 域，改前需与 C 对齐 |
| **W1 `source_url` 进 wire** | B/C/E | `SOURCE_REF_FIELDS` 七字段不含 `source_url`；`api.md` 从未定义；`web/` 0 引用（§2.3 实测） | **已按方案 B 落地回查通道**（§4.6：`/sources` 与 MCP `get_sources` 带 URL，SSE 仍 7 字段）；正式进 wire 仍需 B/C/E 会签 |
| **新发现 F1：filters 在身份段 vs 查询期过滤** | B（+D） | `index_identity_json` 含 `retrieval.filters`（R5 决策的产物），而 B 自 PR#30 起把 filters **下推到查询期**执行——`verify_filters.py` 刻意在检索器层换装以"不触发索引身份漂移"。**实测**：`struct_v1` 基线 hash8 `0a7830b7`；仅加 `filters:{version:"2.4"}` → `8961118d`；换 `2.0` → `d37176c1`；再加 `source_id` → `26bceadb`（对照：只改 `generation.prompt_version` → hash8 不变，R5 修复仍成立） | 后果＝§8.3"按版本过滤"若落成独立实验配置，会为**内容完全相同**的 Node 集再嵌一遍（单来源约 8min、多来源约 25min）并多占一份索引目录。D **未**擅自把 filters 移出身份段（会改掉既有六套索引的派生名 = R5 类孤儿化事故）。例会与 B 二选一：①filters 出身份段（需配套回切演练与迁移说明）②约定版本过滤只在运行时换装、不建独立实验配置 |

## 7. 决策点与拍板结果

**已决（2026-09-14 用户拍板）**

1. **容器化路线** = 先做 make 链路真验证。本机 `docker` 命令不存在（实测），README/Makefile 的三行命令必须实跑通过；Dockerfile 若交付须显式标注"未在本机验证"。
2. **PR 节奏** = 本周内容做完后再发新 PR。PR#31 由用户提交、暂不动；D 在本地分支继续累积提交。
3. **本地 LLM 实跑** = D 直接启动并验证 → **已完成**（§2.1/§2.2，四场景实测通过）。

**已决（第二轮，2026-09-14）**

4. **OpenAI 兼容门面** = **已决：不做，且空目录已删**（`server/openai_compat/.gitkeep` 于 2026-09-14 移除；`docs/api.md` 的"已知边界"同步改写——MCP 已交付、门面经决策不做）。
5. **缺口 W1 处置** = **已决：方案 B**（D 单方在回查通道附带 `source_url`，落地见 §4.6；SSE wire 扩字段仍待 B/C/E 会签）。原三选一记录如下：
   - 方案 A（推荐，契约正确解）：会签新增可选第 8 字段 `source_url`（HTML 非空 / PDF 为 null）——D 起草提案 + 改 `api.md`，B 改 `SOURCE_REF_FIELDS` 投影、C 改 citation 组装、E 加前端跳转。四人均需动手，周五前完成取决于 B/C/E。
   - 方案 B（D 单方可做，权宜）：SSE 契约不动，仅在 `GET /sources/{rid}` 持久化记录里附带 `source_url`，E 从回查接口取 URL 渲染链接。代价 = 同一引用两处字段不一致。
   - 方案 C：本周记为已知缺口，Demo 只展示 HTML 引用显示文件名。
6. **reranker 权重离线预取** = **已决并执行**：`BAAI/bge-reranker-v2-m3` 已缓存本机（2.2GB，§4.7）。
7. **本会话后台服务** = 已按选择全部收摊并核验：网关（11500）与 live 服务（8000）已停、`netstat` 确认端口释放；`ollama stop qwen3.5-9b` 卸载 10GB 占用。**未终止 11434 上的 Ollama 服务进程**（PID 42688）——它是你本机自启的、并非本会话启动，需停请你自己来。

## 8. Week 4 验收对照（指南 §19）· 本版现状

| 通过标准 | 现状 | 依据 |
|---|---|---|
| Hybrid Retrieval 可运行 | ✅ | PR#30 实验通路 + **本版新增 live 服务通路实测**（RRF 分数 0.0276~0.0318、引用制零重建，§2.2） |
| Reranker 有实验数据 | ❌ 未开始 | B 域 `hybrid_rerank` 仍抛 NotImplementedError（§6） |
| Unknown/Abstention 可工作 | ✅ **本版补实测** | 两条"确证无证据"题（E1003 不存在 / 第 300 页越界）live 通路均明确拒答且不虚构（§2.2）；20 题专项口径仍待 C 定版 |
| 有 Citation | ◕ 达标（含过渡处置） | 双页码/来源分型/`/sources` 回查达标；W1 已按方案 B 让**回查通道带 `source_url`**（§4.6，实测 4/5 HTML 引用可跳原文），SSE wire 扩第 8 字段仍待 B/C/E 会签 |
| 有自动/半自动 Evaluation | ◌ 本版推进 | 检索侧自动化闭环：8 实验全量矩阵 + 基准锚点（§1.3）、可比性闸门与退出码可挂 CI；回答侧待 C 的 runner |
| 有最终 Demo | ◕ 本版落地 | `docs/demo-runbook.md` v0.1 + 四场景本机实测通过；剩余缺口是 reranker 与 W1（§7 决策 5） |
