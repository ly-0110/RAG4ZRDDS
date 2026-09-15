# RAG4ZRDDS

**ZRDDS 产品知识库构建与开发调试问答系统** —— 以《ZRDDS用户手册.pdf》（295 页）为第一知识源、ZRDDS v2.4.0 Doxygen 开发文档（436 个 HTML）为第二知识源，构建可运行、可调试、可评价的 RAG 问答系统：检索 + 引用溯源（双页码 / 来源分型）+ 无证据拒答 + 指标化评测。

权威计划与分工见 [`product_rag_implementation_guide.md`](./product_rag_implementation_guide.md)（唯一权威，改计划只改这里）。

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
| `make setup` | 视网络 | `.venv/`（此后所有 make 目标自动改用该 venv 的解释器） |
| `make ingest` | ~1.4s | `data/processed/struct_v1.jsonl`（301 chunk，metadata 21+ 字段，质检全 0） |
| `make index` | **约 8 分钟** | `indexes/struct_bge-m3_<hash8>/`（多来源 1606 节点约 25 分钟） |
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
- 现存配置：`struct_v1`（结构分块 + 向量，基线）· `struct_bm25` · `struct_hybrid` · `semantic_v1` · `hybrid_v1` · `struct_multisrc_v1` / `_bm25` / `_hybrid`（PDF+HTML 统一 Node 集 1606 条）。

规范与逐参数说明见 [`configs/experiments/README.md`](./configs/experiments/README.md)。

## 回归与评测

```bash
make audit                                                    # 标注真值核对（指标闸门的前置门禁）
make regression                                                 # 全部实验
make regression REG_ARGS=--changed-only                         # 按 git 变更推断范围
make regression REG_ARGS="--only struct_v1,struct_bm25 --promote"   # 提基准锚点
```

- **标注闸门**：`make audit` 的判据**只来自 A 的产物与章节树**（不调检索器），因此能抓出"标注 = 检索 top-1 回显"的自证循环；退出码非 0 时不得启用 `--with-metrics`。2026-09-15 现状：E 重标（PR#36）后**首次 pass**（循环指纹 4/120）；遗留六题题干编码损坏（P0）与宽区间 keyword 语义复核（P1），修复前暂不开正式指标（见 `docs/week4-delivery-review.md` §10）。

- **双通道**：默认只比"检索明细"（top-K 重合率 / rank-1 一致率 / 空结果数 / 耗时），与标注无关即可发现退化；指标通道需 `--with-metrics` 显式启用（当前标注未定版，见下）。
- **可比性闸门**：比对前核 `config_hash8` 与 Node 集 / 问题集 / 标注集三份指纹；输入变了判 `incomparable` 而非"回归"。
- 退出码非 0 = 存在 `regression`/`failed`，可直接挂 CI 或作为合并前门禁。
- 报告落 `evaluation/reports/`：`regression_latest.md` 为矩阵摘要，`baseline/` 为人工提定的紧凑基准锚点。

## 文档索引（`docs/`）

| 文档 | 内容 |
|---|---|
| [`api.md`](./docs/api.md) | REST + SSE 契约（事件协议、Citation 字段、score 量纲按 mode 定标、错误双通道） |
| [`ingest-pipeline.md`](./docs/ingest-pipeline.md) | 入库六步链路、多来源注册表、跨来源契约校验 |
| [`html-loader.md`](./docs/html-loader.md) | Doxygen HTML 解析接口与产物口径（A 域） |
| [`retrieval-log-schema.md`](./docs/retrieval-log-schema.md) | 检索日志字段定义与会签结论（B/D） |
| [`citation-contract-draft.md`](./docs/citation-contract-draft.md) | Citation 契约与待决问题（C/E 会签中） |
| [`source-priority-draft.md`](./docs/source-priority-draft.md) | 多来源优先级草案（C 域） |
| [`index-rebuild-drill.md`](./docs/index-rebuild-drill.md) | 索引重建/回切演练与实测计时表 |
| [`mcp.md`](./docs/mcp.md) | MCP Server 工具契约与 stdio 注意事项 |
| [`demo-runbook.md`](./docs/demo-runbook.md) | 最终 Demo 演练手册（四场景实测值与真值判据） |
| [`chunking-defect-report.md`](./docs/chunking-defect-report.md) | 分块缺陷清单与修复记录 |
| [`week2-`](./docs/week2-delivery-review.md) · [`week3-`](./docs/week3-delivery-review.md) · [`week4-delivery-review.md`](./docs/week4-delivery-review.md) | 各周交付审查与验收对照 |

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

系统状态（2026-09-15）：`make test` 全套绿（合并 PR#36 后 345 用例口径，含 E 新增 3 例审计测试）；`make ingest / index / experiment / regression / audit / serve` 全链路本机实测；live 通路真实检索 + LLM 出词的四场景演示通过（见 `docs/demo-runbook.md`）。

以下限制如实登记，请勿在汇报中当作已完成：

- **Reranker 未实现**：`retrieval` 对 `hybrid_rerank` 仍抛 `NotImplementedError`（B 域第四周任务），"Vector / BM25 / Hybrid / Hybrid+Reranker"四组对比缺最后一档。
- **正式指标暂不开启**：`make audit` 已首次 pass（E PR#36 重标，循环指纹 44/120 → 4/120），但六题题干编码损坏（P0）与宽区间标注的 keyword 语义复核（P1）未完成——修复前回归只走明细通道，六份历史报告的 metrics 仍视同 void，待定版后由 D 统一重跑刷新。
- **SSE wire 第 8 字段**：HTML 引用的 `source_url` 已可经 `GET /sources/{rid}`（及 MCP `get_sources`）回查获得（api.md v0.11），前端（PR#36）已消费该通道并渲染外链；SSE 的 `sources` 事件仍是 7 字段，正式扩进 wire 需 B/C/E 会签。
- **容器化未验证**：交付环境本机无 Docker，快速开始以 `make` 链路为准；Docker 方案的验证状态见 `docs/week4-delivery-review.md`。
