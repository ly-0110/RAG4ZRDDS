# RAG4ZRDDS

> **交付说明**：本分支（`deliverable`）是**成果交付版**——只含可运行系统、数据产物、评测结果
> 与使用/契约类文档。过程性内容（周度交付审查、项目规划指南、会签草案、一次性修复脚本、
> 历史回归快照、团队协作配置）已剔除；完整开发过程见 `feature/server-platform` 分支与 Git 历史。
> 下文与各文档中若出现 `week*-delivery-review.md`、`product_rag_implementation_guide.md`、`*-draft.md` 等
> 过程文档的指引，同样属于开发分支内容（本分支不含）。

**ZRDDS 产品知识库构建与开发调试问答系统** —— 以《ZRDDS用户手册.pdf》（295 页）为第一知识源、ZRDDS v2.4.0 Doxygen 开发文档（436 个 HTML）为第二知识源，构建可运行、可调试、可评价的 RAG 问答系统：检索 + 引用溯源（双页码 / 来源分型）+ 无证据拒答 + 指标化评测。

系统架构见 [`docs/architecture.md`](./docs/architecture.md)，接口契约见 [`docs/api.md`](./docs/api.md)，实验结论见 [`docs/experiment-results.md`](./docs/experiment-results.md)。

---

## 三行命令跑起来

Windows 前置：装一次 GNU Make 并保证 `make --version` 可用（`choco install make` / winget / [GnuWin32](https://sourceforge.net/projects/ezwinports/)）；macOS/Linux 自带。

```bash
cp .env.example .env      # 填运行配置与密钥引用（.env 不入库）
make setup                # 建 .venv 并装 requirements.txt（默认国内 pip 源）
make ingest && make index && make serve    # 入库 → 建索引 → 起服务
```

预期与耗时（本机实测，CPU + bge-m3）：

| 步骤 | 耗时 | 产物 / 结果 |
|---|---|---|
| `make setup` | 视网络（2026-09-17 实测成功） | `.venv/`（此后所有 make 目标自动改用该 venv 的解释器；新 venv 内 `pytest tests/` 430/430、`make ingest` 产物与 Git 版本零差异） |
| `make ingest` | ~1.4s | `data/processed/struct_v1.jsonl`（301 chunk，metadata 21+ 字段，质检全 0） |
| `make index` | **约 8 分钟** | `indexes/struct_bge-m3_<hash8>/`（多来源 1638 节点约 25 分钟） |
| `make serve` | 启动期预热 | `http://127.0.0.1:8000/healthz` → `{"status":"ok","mode":"live"}` |

> **两个坑（本机实测，务必照做）**
> 1. HuggingFace 权重已在本地缓存时，导出 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`；否则 SentenceTransformer 初始化会对每个配置文件反复联网，看起来像"卡死"。
> 2. 需要下载权重时请**直连** huggingface.co。设 `HF_ENDPOINT` 走镜像在本机实测会 `FileMetadataError`（embedding 场景尤其如此）。

问答（SSE，事件序列固定 `sources → token×N → done`）：

```bash
curl -N -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question":"DurabilityQosPolicy 的 kind 字段默认值是什么？","top_k":5}'
```

中文问题请用 UTF-8 客户端发送（Git Bash 的 curl 会按 GBK 编码 body，服务端 JSON 解码会失败）。

### 选哪种后端跑 live

`.env.example` 默认 `RAG_MODE=mock`（确定性假数据，供前端独立联调）。要真实检索 + 真实出词，**首选云端 OpenAI 兼容 API**（`.env.example` 已预填 OpenRouter 免费档示例）：

| 后端 | `.env` 关键项 | 说明 |
|---|---|---|
| 云端 OpenAI 兼容 API（默认） | `RAG_MODE=live`、`LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | 任何 OpenAI 兼容服务商均可；密钥只写进 `.env`，仓库里只引 env 名 |
| 本地 Ollama（可选） | `RAG_MODE=live`、`LLM_BASE_URL=http://127.0.0.1:11500/v1`、`LLM_MODEL=<本地模型名>` | 需自备 Ollama（11434）与 `models/llm_gateway.py` 网关（转原生 `/api/chat` 强制关思考）。**`models/` 不入 Git，属本机个人研究**——仓库不含此文件，仅作离线演示备选 |
| 只看检索不要生成 | `RAG_MODE=live` 且 LLM 未配置 | 启动即给可读拒绝；SSE 会先下发真实 `sources` 再以 `error` 事件说明缺口，不静默降级 |

live 模式用哪套索引由 `RAG_EXPERIMENT_CONFIG`（默认 `configs/experiments/struct_v1.yaml`）决定。

## make 目标一览

| 目标 | 作用 | 常用参数 |
|---|---|---|
| `setup` | 建 venv + 装依赖 | `PIP_INDEX=`（默认清华源） |
| `ingest` | raw → cleaned → processed（含分块）六步全链路 | `CFG=configs/experiments/<实验>.yaml` |
| `index` | 建索引（幂等，先删后建）+ manifest + 产物指纹 | `CFG=`；`--list` 盘点与回切 |
| `experiment` | 单实验：保障索引就绪 → 全量题检索 → 报告落盘 | `CFG=` / `--rebuild` / `--fake-embed` / `--sample N` |
| `regression` | **一键回归矩阵**（指南 §10）：跑相关实验并与历史/基准比对 | `REG_ARGS='--only a,b'` / `--changed-only` / `--with-metrics` / `--promote` |
| `audit` | **标注真值核对**（判据只来自产物，不调检索器）；是 `--with-metrics` 的前置门禁 | 参数直传脚本，如 `--emit-abstention` |
| `test` | pytest 全套单测 | — |
| `serve` | FastAPI（REST + SSE） | `APP_HOST=` `APP_PORT=` |
| `inspect` | Node 产物质检与抽查（分来源统计） | — |
| `mcp` / `smoke-mcp` | MCP Server（stdio）与其端到端冒烟 | — |

解释器规则：存在 `.venv` 时全部目标自动使用 `.venv` 内的 python，否则回退系统 python；`make help` 会打印当前选中的解释器。

## 配置驱动：一次实验一个 yaml

一切分块 / 检索 / 生成 / 评测实验都经由 `configs/experiments/*.yaml` 切换（文件名即实验 ID，未知字段报错并给拼写建议），禁止改代码换实验。

- 索引目录派生命名 `{method}_{embed}_{hash8}`。**hash8 只由索引身份段派生**（`chunking` / `embedding` / `index` / `retrieval.mode|params|filters`）——改生成、评测、报告段不会孤儿化索引。
- 复用前硬校验产物指纹 `nodes_file_sha12`（CRLF 归一化后计算）：产物变了而配置没变的脏索引会被拒绝复用并提示 `--rebuild`。
- hybrid 走**引用制**：`retrieval.components: {vector: <实验名>, bm25: <实验名>}`，运行时融合、零重建。
- 现存配置：`struct_v1`（结构分块 + 向量，基线）· `struct_bm25` · `struct_hybrid` · `semantic_v1` · `hybrid_v1` · `struct_multisrc_v1` / `_bm25` / `_hybrid` / `_hybrid_ver20` / `_hybrid_ver24` · `struct_multisrc_hybrid_rerank`（精排）· `final_v1`（产品态：Prompt v2 + source_priority + 回答侧四指标）。多来源统一 Node 集 **1638 条**（PDF 301 + HTML 1337）。
- 四种检索模式均可跑：`vector`（bge-m3 + chroma）· `bm25`（字符 bigram + ASCII 词整体保留）· `hybrid`（RRF 融合，引用制）· `hybrid_rerank`（RRF Top30 → bge-reranker-v2-m3 精排 → Top5）；版本加权经 `retrieval.params` 配置（`version_pref` / `version_boost`）。

规范与逐参数说明见 [`configs/experiments/README.md`](./configs/experiments/README.md)。

## 回归与评测

```bash
make audit                                                    # 标注真值核对（指标闸门的前置门禁）
make regression                                                 # 全部实验
make regression REG_ARGS=--changed-only                         # 按 git 变更推断范围
make regression REG_ARGS="--only struct_v1,struct_bm25 --promote"   # 提基准锚点
```

- **标注闸门**：`make audit` 的判据**只来自 A 的产物与章节树**（不调检索器），因此能抓出"标注 = 检索 top-1 回显"的自证循环，也能抓出题面本身的损坏（如写入环节的有损转码）；退出码非 0 时不得启用 `--with-metrics`。2026-09-17 现状：判定 **pass**——循环论证指纹 **0/120**、题面乱码 0 处、阻断项 0（历史 44/120 → 48 题 → 4 题 → 0）；指标通道已随 `--with-metrics` 启用。

- **双通道**：默认只比"检索明细"（top-K 重合率 / rank-1 一致率 / 空结果数 / 耗时），与标注无关即可发现退化；指标通道需 `--with-metrics` 显式启用（当前标注未定版，见下）。
- **可比性闸门**：比对前核 `config_hash8` 与 Node 集 / 问题集 / 标注集三份指纹；输入变了判 `incomparable` 而非"回归"。
- 退出码非 0 = 存在 `regression`/`failed`，可直接挂 CI 或作为合并前门禁。
- 报告落 `evaluation/reports/`：`regression_latest.md` 为矩阵摘要，`baseline/` 为人工提定的紧凑基准锚点。

## 文档索引（`docs/`）

| 文档 | 内容 |
|---|---|
| [`experiment-results.md`](./docs/experiment-results.md) | **实验结果分析**：分块/检索/多来源/精排对比、回答侧四指标、拒答专项、错误案例与结论 |
| [`architecture.md`](./docs/architecture.md) | **系统架构**：分层视图、三条运行链路、对外契约、关键不变量、评测与部署形态 |
| [`api.md`](./docs/api.md) | REST + SSE 契约（事件协议、Citation 字段、score 量纲按 mode 定标、错误双通道） |
| [`ingest-pipeline.md`](./docs/ingest-pipeline.md) | 入库六步链路、多来源注册表、跨来源契约校验 |
| [`html-loader.md`](./docs/html-loader.md) | Doxygen HTML 解析接口与产物口径（A 域） |
| [`evaluation.md`](./docs/evaluation.md) | 检索实验方法学与四组对比证据链（B 域） |
| [`reliability-report.md`](./docs/reliability-report.md) | 可靠性与拒答专项报告（C 域） |
| [`retrieval-log-schema.md`](./docs/retrieval-log-schema.md) | 检索日志字段定义与会签结论（B/D） |
| [`answer-log-schema.md`](./docs/answer-log-schema.md) | 回答级日志字段定义（v1.0 定版并已落地） |
| [`index-rebuild-drill.md`](./docs/index-rebuild-drill.md) | 索引重建/回切演练与实测计时表 |
| [`mcp.md`](./docs/mcp.md) | MCP Server 工具契约与 stdio 注意事项 |
| [`demo-runbook.md`](./docs/demo-runbook.md) | 最终 Demo 演练手册（四场景实测值与真值判据） |
| [`chunking-defect-report.md`](./docs/chunking-defect-report.md) | 分块缺陷清单与修复记录 |

## 目录与 Owner

| 目录 | Owner | 说明 |
|---|---|---|
| `data_pipeline/` | A | 解析 / 清洗 / 章节树 / 三方案 chunker（含 HTML loader） |
| `retrieval/` | B | Embedding / 向量索引 / BM25 / Hybrid(RRF) / 检索器 |
| `generation/` | C | Prompt 版本 / Context 组装 / LLM 客户端 / 判分 |
| `server/` · `scripts/` | D | API 门面、MCP Server、日志设施、入库与实验流水线、回归矩阵 |
| `web/` | E | 问答界面（自研轻量页：Vue 3 + Vite） |
| `evaluation/` | E 数据集 / C 判分 / D 报告 | 问题集、标注、错误案例、实验与回归报告 |
| `configs/experiments/` | D 定格式 | 一次实验一个 yaml |
| `data/raw/` · `data/cleaned/` · `indexes/` · `logs/` | — | 本机产物，不入 Git（`data/processed/` 入库） |

## 当前状态与已知限制

系统状态（2026-09-17）：`make test` **448/448 全绿**；`make ingest / index / experiment / serve / regression / audit` 全链路本机实测；多来源统一 Node 集 **1638 条**（H1 HTML 加载器丢正文缺陷修复后重生成），`indexes/` 六套索引经指纹核对**全部可复用（零重建）**；live 通路真实检索 + 真实出词的四场景演示通过（见 `docs/demo-runbook.md`）。系统架构见 [`docs/architecture.md`](./docs/architecture.md)。

以下限制如实登记，请勿在汇报中当作已完成：

- **检索正式指标已解冻（2026-09-17）**：`make audit` 判 **pass**（循环论证指纹 0/120、题面乱码 0、阻断项 0），`make regression --with-metrics` 已启用，**12 个实验 12/12 pass**；正式检索指标与逐题分析见 [`docs/experiment-results.md`](./docs/experiment-results.md)。
- **回答侧评测（2026-09-17 已实测）**：`final_v1`（Prompt v2 + source_priority）120 题终跑——faithfulness **0.8950** / answer_relevance **0.9883** / correctness **0.9633** / citation_accuracy **0.9583**（均 n=120、判分失败 0），拒答 29/120；**20 题拒答专项 = 20/20 全部不虚构**（16 题显式拒答 + 4 题"事实性否定 + 引用"，后者经会签计入合格）。注意报告 `response.answer_seconds` 才是回答侧墙钟（120 题约 84 分钟，本地 9B），`duration_seconds` 仍是检索阶段耗时。30 题人工抽检清单已生成、待签署。全部数字见 [`docs/experiment-results.md`](./docs/experiment-results.md)。
- **SSE wire 8 字段（已定版）**：`source_url` 已升为 wire 第 8 字段（api.md **v0.17**），`sources`/`done` 事件与 `/sources/{rid}`、MCP `get_sources` 三处同形——HTML 引用给本地 `/documents/…` 地址，PDF 为 `null`；既有 7 字段零变化。
- **三级日志全部落地**：请求级 `logs/requests.jsonl`、检索级 `logs/retrievals.jsonl`、**回答级 `logs/answers.jsonl`**（字段定义 [`docs/answer-log-schema.md`](./docs/answer-log-schema.md) v1.0，终态 stop/error/cancelled 各写一条）。
- **容器化未验证**：交付环境本机无 Docker，快速开始以 `make` 链路为准；Docker 方案的验证状态见 `docs/week4-delivery-review.md`。
