# RAG4ZRDDS

> **交付说明**：本分支为**成果交付版**——只含可运行系统、数据产物、评测结果与使用/契约类文档。

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
| `make setup` | 视网络 | `.venv/`（此后所有 make 目标自动改用该 venv 的解释器；新 venv 内 `pytest tests/` 448/448、`make ingest` 产物与 Git 版本零差异） |
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
| 只看检索不要生成 | `RAG_MODE=live` 且 LLM 未配置 | 启动即给可读拒绝；SSE 会先下发真实 `sources` 再以 `error` 事件说明原因，不静默降级 |

live 模式用哪套索引由 `RAG_EXPERIMENT_CONFIG`（默认 `configs/experiments/struct_v1.yaml`）决定。

## make 目标一览

| 目标 | 作用 | 常用参数 |
|---|---|---|
| `setup` | 建 venv + 装依赖 | `PIP_INDEX=`（默认清华源） |
| `ingest` | raw → cleaned → processed（含分块）六步全链路 | `CFG=configs/experiments/<实验>.yaml` |
| `index` | 建索引（幂等，先删后建）+ manifest + 产物指纹 | `CFG=`；`--list` 盘点与回切 |
| `experiment` | 单实验：保障索引就绪 → 全量题检索 → 报告落盘 | `CFG=` / `--rebuild` / `--fake-embed` / `--sample N` |
| `regression` | **一键回归矩阵**：跑相关实验并与历史/基准比对 | `REG_ARGS='--only a,b'` / `--changed-only` / `--with-metrics` / `--promote` |
| `audit` | **标注真值核对**（判据只来自产物，不调检索器）；是 `--with-metrics` 的前置门禁 | 参数直传脚本，如 `--emit-abstention` |
| `test` | pytest 全套单测 | — |
| `serve` | FastAPI（REST + SSE） | `APP_HOST=` `APP_PORT=` |
| `inspect` | Node 产物质检与抽查（分来源统计） | — |
| `mcp` / `smoke-mcp` | MCP Server（stdio）与其端到端冒烟 | — |
| `docker-build` / `docker-serve` | **Docker 打包**：构建镜像、一键起后端 + 前端容器栈 | `BACKEND_PORT=` `WEB_PORT=` `CONTAINER_RAG_MODE=mock` |
| `docker-smoke` / `docker-ps` / `docker-logs` / `docker-stop` / `docker-clean` | 容器形态冒烟与运维 | — |

解释器规则：存在 `.venv` 时全部目标自动使用 `.venv` 内的 python，否则回退系统 python；`make help` 会打印当前选中的解释器。

## Docker 打包与部署

容器形态与 make 链路等价，差别在**镜像只装代码与依赖**：模型权重、六套索引、HTML 原始快照全部经 `docker-compose.yml` 挂载复用宿主。因此重建镜像不需要重新下载模型，也不需要重建索引（单套 8~25 分钟）。Dockerfile 也据此分层——`requirements.txt` 与代码各占一层，改代码不触发重装依赖。

```bash
cp .env.example .env          # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
make docker-serve             # = docker compose up -d --build
make docker-smoke             # 容器形态冒烟（15 项，全过退出码 0）
```

起好后：问答界面 <http://127.0.0.1:5173>，后端健康检查 <http://127.0.0.1:8000/healthz>。

两个容器：`backend`（FastAPI REST + SSE，容器内 8000）、`frontend`（nginx 托管 Vite 产物 + 反代后端 6 条 API 路径，容器内 80）。前端 API 调用全走相对路径，开发态由 Vite proxy 转发、容器态由 nginx 转发，两态行为一致。

`make docker-smoke` 专测容器栈特有的三类风险并核对真值：

- **静态托管与反代**：前端首页、`/healthz`、`/sources/{rid}` 经 nginx 全通；
- **SSE 经反代增量下发**：按 token 到达时间戳判定（实测首 token 5.09s → 结束 9.66s）。若 `proxy_buffering` 没关，token 会攒到末尾同一瞬间到达，前端的打字机效果与"停止生成"都会失效；
- **真值核对**：`10.7 DurabilityQosPolicy` 引用印刷页 127 / 物理页 133、双页码差恒 6、wire 8 字段且无正文泄漏。

### 容器侧配置（都已在 compose 内处理）

- **默认 live**：宿主 `.env` 的 `RAG_MODE=mock` 会被覆盖为 live（mock 是给前端脱离后端联调用的）；要起 mock：`CONTAINER_RAG_MODE=mock make docker-serve`。
- **启动默认实验**由 `.env` 的 `RAG_EXPERIMENT_CONFIG` 决定；起服务后界面还能逐请求切实验（F4 选择器），前提是对应索引已在 `indexes/` 里。
- **本地 Ollama 后端**：容器里的 `127.0.0.1` 指容器自身，用 `.env.docker` 覆盖（该文件同样不入 Git）：

  ```bash
  # .env.docker —— 只放"宿主与容器配置不同"的项，避免来回改 .env
  LLM_BASE_URL=http://host.docker.internal:11500/v1
  ```

  compose 的 `env_file` 顺序是 `.env` → `.env.docker`（后者优先），`host.docker.internal` 已映射到宿主。用云端 API 时不需要这个文件。
- **日志**：请求 / 检索 / 引用回查 / 反馈四级日志落在宿主 `logs/`（挂载），容器重建不丢。

```bash
make docker-ps        # 容器状态
make docker-logs      # 跟后端日志（含启动期 bge-m3 预热）
make docker-stop      # 停栈（不动挂载的宿主目录）
make docker-clean     # 停栈并删除本机构建的镜像
```

### 挂载来源

| 挂载 | 宿主来源 | 说明 |
|---|---|---|
| `indexes/` | 仓库（`make index` 产出） | 读写挂载：chroma 打开持久化集合要写 sqlite 日志，只读挂载会失败。索引缺失时服务端按配置在容器内重建（单套 8~25 分钟） |
| `data/raw/` | 仓库 | 只读。`/documents/{source_id}/{file}` 的"打开原文"靠它（实测返回 200 / 176KB 真实 Doxygen 页）；未挂载时引用链接退回配置里的占位地址，不报错也不静默改语义 |
| `logs/` | 仓库 | 四级日志落宿主 |
| embedding 权重 | `%LOCALAPPDATA%\llama_index\llama_index\Cache` | **bge-m3 在 LlamaIndex 缓存，不在 HF 缓存**——LlamaIndex 的 `HuggingFaceEmbedding` 会显式传自己的 `cache_dir`（实测把 HF_HOME 指向空目录后模型照常加载，权重根本不在 HF 缓存里） |
| 精排权重 | `%USERPROFILE%\.cache\huggingface` | `bge-reranker-v2-m3` 走 sentence-transformers `CrossEncoder`，用 HF 默认缓存 |

两个权重缓存均只读挂载（实测可正常加载）。非 Windows 或缓存在他处：`LLAMA_INDEX_CACHE_HOST=<路径> HF_CACHE_HOST=<路径> docker compose up -d`。容器内默认离线（`HF_HUB_OFFLINE=1`）：缓存未命中即以可读错误拒绝启动，不会静默联网卡住。

| 项 | 说明 |
|---|---|
| 前置 | Docker Desktop（实测 Docker 29.8 / Compose v5.5.1）+ `.env` 填好 LLM 配置 |
| 镜像体积 | 后端 2.74GB（torch 走 CPU 专用轮子，避免 CUDA 依赖再涨 2~3GB——实测镜像内 `torch 2.13.0+cpu`）；前端 102MB |
| 构建耗时 | 后端首建约 3 分钟（pip 装依赖 115s + 导出镜像 43s）；前端首建约 1 分钟。依赖层命中缓存后，改代码重建只需秒级 |
| 启动耗时 | live 启动期预热实测 7.8s（bge-m3 冷加载，容器内），在端口监听前完成 |
| 端口 | 与宿主 `make serve`(8000) / `vite`(5173) 是同一批端口，二选一；要并跑：`BACKEND_PORT=8001 WEB_PORT=18080 make docker-serve` |
| ⚠ 端口被别的进程占用时 | Docker Desktop **不报错**，容器照常 Up 但端口不转发，表现为"容器健康、浏览器 404/连不上"。实测踩过（8080 被宿主某 http 服务占用）——换端口即可 |
| 构建网络 | 首次拉基础镜像若遇 `auth.docker.io` 超时（IPv6 抖动）重试即可；`npm ci` 默认走 npmmirror（`NPM_REGISTRY` 可换），pip 走清华源（`PIP_INDEX` 可换） |

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

- **标注闸门**：`make audit` 的判据**只来自 Node 产物与章节树**（不调检索器），因此能抓出"标注 = 检索 top-1 回显"的自证循环，也能抓出题面本身的损坏（如写入环节的有损转码）；退出码非 0 时不得启用 `--with-metrics`。当前判定 **pass**——循环论证指纹 **0/120**、题面乱码 0 处、阻断项 0。

- **双通道**：默认只比"检索明细"（top-K 重合率 / rank-1 一致率 / 空结果数 / 耗时），与标注无关即可发现退化；指标通道需 `--with-metrics` 显式启用。
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
| [`html-loader.md`](./docs/html-loader.md) | Doxygen HTML 解析接口与产物口径 |
| [`reliability-report.md`](./docs/reliability-report.md) | 可靠性与拒答专项实测结果 |
| [`retrieval-log-schema.md`](./docs/retrieval-log-schema.md) | 检索日志字段定义 |
| [`index-rebuild-drill.md`](./docs/index-rebuild-drill.md) | 索引重建/回切流程与实测计时 |
| [`mcp.md`](./docs/mcp.md) | MCP Server 工具契约与 stdio 注意事项 |

## 目录

| 目录 | 说明 |
|---|---|
| `data_pipeline/` | 解析 / 清洗 / 章节树 / 三方案 chunker（含 HTML loader） |
| `retrieval/` | Embedding / 向量索引 / BM25 / Hybrid(RRF) / 精排 / 检索器 |
| `generation/` | Prompt 版本 / Context 组装 / LLM 客户端 / 拒答判定 |
| `server/` · `scripts/` | API 门面、MCP Server、日志设施、入库与实验流水线、回归矩阵 |
| `web/` | 问答界面（Vue 3 + Vite） |
| `evaluation/` | 问题集、标注、错误案例、判分、实验与回归报告 |
| `configs/experiments/` | 一次实验一个 yaml |
| `data/processed/` | 统一 Node 集（入库） |
| `data/raw/` · `data/cleaned/` · `indexes/` · `logs/` | 本机产物，不入 Git |

## 能力与现状

`make test` **448/448 全绿**；`make ingest / index / experiment / serve / regression / audit` 全链路本机实测；多来源统一 Node 集 **1638 条**，`indexes/` 六套索引指纹校验通过；live 通路真实检索 + 真实出词四场景演示通过。

- **检索**：向量 / BM25 / Hybrid(RRF) / Hybrid+精排 四种模式，版本加权可配；正式指标（hit@5 / mrr@5 / precision@5 / recall@5）见 [`docs/experiment-results.md`](./docs/experiment-results.md)。
- **回答**：Prompt v2（多来源 + 冲突披露 + 来源优先级）、流式输出、引用溯源（双页码 / 来源分型 / 原文链接）、无证据拒答。
- **评测**：120 题标注集 + 12 题跨来源集 + 20 题拒答专项 + 70 例真实错误案例；回答侧四指标；回归矩阵与三指纹可比性闸门。
- **服务**：REST + SSE、MCP Server（stdio）、四级日志（请求 / 检索 / 回答 / 引用回查）。
