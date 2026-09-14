# 第四周交付记录（成员 D）

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

- `python -m pytest tests/` → **302/302 绿**（266 → +36）。
- **正向闭环**：`--only struct_bm25` 首轮 `incomparable`（历史报告为 v1 无指纹）→ 重跑 → `pass（vs 上次 pass / vs 基准 pass）`，结论 PASS、退出码 0。
- **真实实验复现性**：`--only struct_v1,struct_bm25` 连跑两轮，第二轮两实验均 `top-K 重合 1.0 / rank-1 一致 1.0 / hit_rate@5 delta +0.0000`，耗时 17.5s（真实 bge-m3 向量检索）与 0.6s（bm25）——同索引同产物的确定性复现得到实证。
- **负向验证（不破坏基线的前提下）**：把阈值抬到 `--min-overlap 1.0001` → 判 `regression`、总体 FAIL、**退出码 1**；`--with-metrics` 在零差值重跑下仍 `pass`（闸门不误伤）。
- **紧凑锚点**：`--promote` 后 `baseline/struct_v1.json` 100KB / `struct_bm25.json` 99KB，比对照常成立（有单测锁定）。
- 落盘：`evaluation/reports/regression_latest.{json,md}`（矩阵摘要）+ `runs/` 归档（本机）。

### 1.4 边界与未覆盖

- `--changed-only` 的路径映射由单测覆盖，**未在真实多人 PR 流上跑过**；下周若有 B 的 reranker PR 合入即为首个实战样本。
- 回归矩阵本轮实跑 `struct_v1` + `struct_bm25` 两个实验；hybrid / 多来源四配置**未进矩阵**（其 live 检索通路已在 §2.2 单独实测，但 `run_experiment` 报告与明细回归尚未跑）；semantic 待 A 处置超长块（§5）。
- 指标闸门默认关闭，Week 4 验收项"有自动/半自动 Evaluation"目前只覆盖检索侧，回答侧阻塞在 C（§5）。

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

处置：属跨成员契约变更（B 的投影字段 + C 的 citation 组装 + E 的前端跳转 + D 的 api.md），2026-09-13 会签只决定过"暂不增补 `source_type`"，未覆盖 `source_url`。方案已提交用户拍板（见决策节），未定前 D 不擅自改他人域。

### 2.4 边界（本轮未覆盖）

- 场景 5（RapidIO QoS 精确 token 题）已列入 runbook 题单，**实测值待补录**。
- 演示环境目前仍绑定在 `struct_multisrc_hybrid` 配置上；切回单来源基线只需改 `RAG_EXPERIMENT_CONFIG` 并重启。
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

## 4. 分支与开工前置状态

- 分支起点 `feature/server-platform` = `5d925c2`（与 origin 同步）；**PR#31 由用户提交，仍待 squash 合入 develop**（远端 develop 落后本地多个提交）。
- 用户决策（2026-09-14）：**先把本周内容做完，再发新的 PR**；因此本地在 `5d925c2` 之上继续累积提交，暂不合入、暂不改远端。
- 本周已入库（本地提交）：`2ecd6c4` 回归自动化（`.gitignore` / `Makefile` / `scripts/{build_index,run_experiment,run_regression}.py` / `tests/unit/test_run_regression.py` / 两份 v1.1 报告 + 基准锚点 + 回归矩阵）、`ff929bf` 本记录 v0.1、`f05114f` Demo 交付（`docs/demo-runbook.md` + 本记录 v0.2）、以及交付三（`Makefile` 解释器选择 + `README.md` 重写 + `.env.example` 补注 + 本记录 v0.3）。
- **指南 §8 D 三项完成度**：①回归自动化 ✅ 已交付并实测；②打包 = README/make 链路 ✅ 交付（容器形态按决策未做，§3.4）；③最终 Demo 环境 ✅ 四场景实测通过（reranker 一档缺 B 实现，W1 缺契约）。
- 索引状态：六套全部可用且指纹匹配，本轮回归与全部 Demo **未触发任何重建**（复用链路正常；hybrid 走引用制）。

## 5. 跨成员依赖与阻塞（截至本版实测）

| 事项 | 归属 | 实测现状 | 对 D/Week4 的影响 |
|---|---|---|---|
| 真值标注（逐题对 PDF 核对） | E | `expected_sources.jsonl` 120 条仍在，但与规范索引报告 top-1 仅 **44/120** 吻合（本次实测），仍是循环 + 非规范模型副本产物 | 指标闸门只能默认关闭；6 份 void 报告无法刷新；Week4 验收项 1/2/3 继续阻塞 |
| Reranker（§8.2） | B | `retrieval/retriever.py:154` 仍 `NotImplementedError("hybrid_rerank 待第四周实现")` | "Reranker 有实验数据"验收项拿不到；D 侧配套（build_index 跳过 / 子索引检查 / 权重离线缓存）待其落地 |
| `answer_eval.py` runner（X2） | C | `evaluation/runners/` 仍只有 `.gitkeep` | 回答侧指标无法进矩阵；D 的 `run_experiment` 保持 `response_metrics` 非空即拒绝的现有语义 |
| semantic 超长块 | A | `data_pipeline/chunkers/semantic.py:63` 的 `self.max_chars` 仍无消费点 | semantic 索引/报告/错误案例三者仍挂起，矩阵里该实验暂不实跑 |
| Prompt 版本一致性（议题 8） | C/D | `struct_bm25.yaml` 仍 `prompt_version: v0` | 配置在 D 域，改前需与 C 对齐 |
| **W1 `source_url` 进 wire** | B/C/E | `SOURCE_REF_FIELDS` 七字段不含 `source_url`；`api.md` 0 处定义；`web/` 0 处引用（§2.3 实测） | 指南 §7 E 任务"HTML 引用跳 URL"无法达成；Week 4 "有 Citation" 降档；处置方案待拍板（§6 决策 5） |

## 6. 决策点与拍板结果

**已决（2026-09-14 用户拍板）**

1. **容器化路线** = 先做 make 链路真验证。本机 `docker` 命令不存在（实测），README/Makefile 的三行命令必须实跑通过；Dockerfile 若交付须显式标注"未在本机验证"。
2. **PR 节奏** = 本周内容做完后再发新 PR。PR#31 由用户提交、暂不动；D 在本地分支继续累积提交。
3. **本地 LLM 实跑** = D 直接启动并验证 → **已完成**（§2.1/§2.2，四场景实测通过）。

**未决（需用户拍板）**

4. **OpenAI 兼容门面**：`server/openai_compat/` 空目录（2026-09-08 决策不做）。第四周汇报若不需要"生态兼容"证据，建议删除空目录。
5. **缺口 W1 处置**（`source_url` 未进 wire，HTML 引用点不回原文）：
   - 方案 A（推荐，契约正确解）：会签新增可选第 8 字段 `source_url`（HTML 非空 / PDF 为 null）——D 起草提案 + 改 `api.md`，B 改 `SOURCE_REF_FIELDS` 投影、C 改 citation 组装、E 加前端跳转。四人均需动手，周五前完成取决于 B/C/E。
   - 方案 B（D 单方可做，权宜）：SSE 契约不动，仅在 `GET /sources/{rid}` 持久化记录里附带 `source_url`，E 从回查接口取 URL 渲染链接。代价 = 同一引用两处字段不一致。
   - 方案 C：本周记为已知缺口，Demo 只展示 HTML 引用显示文件名。

## 7. Week 4 验收对照（指南 §19）· 本版现状

| 通过标准 | 现状 | 依据 |
|---|---|---|
| Hybrid Retrieval 可运行 | ✅ | PR#30 实验通路 + **本版新增 live 服务通路实测**（RRF 分数 0.0276~0.0318、引用制零重建，§2.2） |
| Reranker 有实验数据 | ❌ 未开始 | B 域 `hybrid_rerank` 仍抛 NotImplementedError（§5） |
| Unknown/Abstention 可工作 | ✅ **本版补实测** | 两条"确证无证据"题（E1003 不存在 / 第 300 页越界）live 通路均明确拒答且不虚构（§2.2）；20 题专项口径仍待 C 定版 |
| 有 Citation | ◌ **降档** | 双页码/来源分型/`/sources` 回查均达标；**但 `source_url` 未进 wire，HTML 引用跳不回原文**（W1，§2.3；同时更正第三周口径） |
| 有自动/半自动 Evaluation | ◌ 本版推进 | 检索侧自动化闭环（§1，可比性闸门 + 退出码）；回答侧待 C 的 runner |
| 有最终 Demo | ◕ 本版落地 | `docs/demo-runbook.md` v0.1 + 四场景本机实测通过；剩余缺口是 reranker 与 W1（§6 决策 5） |
