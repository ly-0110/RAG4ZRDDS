# RAG4ZRDDS

> **交付说明**：本分支为**成果交付版**——只含可运行系统、数据产物、评测结果与使用/契约类文档。

**ZRDDS 产品知识库构建与开发调试问答系统** —— 以《ZRDDS用户手册.pdf》（295 页）为第一知识源、ZRDDS v2.4.0 Doxygen 开发文档（436 个 HTML 页面）为第二知识源，面向开发调试场景提供问答服务：检索 + 引用溯源（双页码 / 来源分型）+ 无证据拒答 + 指标化评测。

系统架构见 [`docs/architecture.md`](./docs/architecture.md)，接口契约见 [`docs/api.md`](./docs/api.md)，实验结论见 [`docs/experiment-results.md`](./docs/experiment-results.md)。

---

## 快速开始

### 方式一：Docker（推荐）

后端镜像自包含——代码、依赖、统一 Node 产物、六套索引、PDF 与 HTML 原文、模型权重都在镜像内。目标机器上只需要 Docker 与一个 OpenAI 兼容的 LLM 服务，不必安装 Python/Node，也不必准备任何数据目录。

```bash
cp .env.example .env      # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（见「LLM 配置」）
docker compose up -d      # 首次会构建镜像，之后直接启动
```

> **拿到已构建镜像包时**：先载入镜像再起栈，跳过构建（也不需要本机有模型权重）——
> `docker load -i images/rag4zrdds-images.tar` 之后执行 `docker compose up -d`。见下方「迁移到另一台机器」。

> 自行构建镜像时会从本机已有的模型缓存拷入权重；构建机没有这些缓存时，同样走上面的镜像载入方式，或见「精简镜像」。

| 入口 | 地址 |
|---|---|
| 问答界面 | <http://127.0.0.1:5173> |
| 后端健康检查 | <http://127.0.0.1:8000/healthz> |

验收与日常运维：

```bash
make docker-smoke     # 冒烟：健康检查 + 前端反代 + 一次真实问答，全过则退出码 0
make docker-ps        # 容器状态
make docker-logs      # 后端日志（含启动期模型预热）
make docker-stop      # 停栈
```

**迁移到另一台机器**：镜像即交付物，`docker save` / `load` 搬过去即可，目标机不需要任何本机目录，Windows / Linux / macOS 均可。导出文件约 4.4GB（镜像内层以压缩形式存储，展开后约 13GB）。

```bash
docker save rag4zrdds-backend:latest rag4zrdds-frontend:latest -o rag4zrdds-images.tar   # 构建机
docker load -i rag4zrdds-images.tar                                                      # 目标机
docker compose up -d
```

### 方式二：从源码运行

需要 Python 3.13 与 GNU Make（Windows 可 `choco install make`，macOS/Linux 自带）。

```bash
cp .env.example .env
make setup                                  # 建 .venv 并安装依赖
make ingest && make index && make serve     # 入库 → 建索引 → 起服务
```

`make ingest` 把原始文档转成统一 Node 产物；`make index` 建索引，向量索引在 CPU 上较慢，多来源全量配置需数十分钟；`make serve` 在监听端口前完成模型预热，对外提供 REST + SSE。

问答走 SSE，事件序列固定为 `sources → token×N → done`：

```bash
curl -N -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question":"DurabilityQosPolicy 的 kind 字段默认值是什么？","top_k":5}'
```

中文问题请用 UTF-8 客户端发送（Git Bash 的 curl 会按 GBK 编码 body，服务端 JSON 解码会失败）。

## LLM 配置

系统按 **OpenAI 兼容协议**调用大模型，任何实现该协议的服务都可直接接入。换服务商或换模型只改 `.env` 三项：

| 变量 | 说明 |
|---|---|
| `LLM_BASE_URL` | 服务基址，含版本段，如 `https://<服务商>/api/v1` |
| `LLM_API_KEY` | 密钥，只写在 `.env`（不入库、不进镜像） |
| `LLM_MODEL` | 模型名 |

两点约定：

- **不要选长推理模型**（deepseek-r1、o1 一类）。本系统要求"仅依据检索内容作答"，长推理会显著拖慢首字并削弱接地性。
- LLM 未配置或不可达时，服务在启动期给出可读拒绝；请求过程中的失败以 SSE `error` 事件透传，不静默降级——检索侧已下发的引用仍可经 `/sources/{request_id}` 回查。

## 系统组成

三条运行链路：

- **入库**：原始 PDF / HTML → 清洗 → 章节树 → 分块 → 统一 Node 产物（`data/processed/`）。产物先过跨来源契约校验与质检，通过才落盘。
- **检索**：四种模式按实验切换——`vector`（bge-m3 + chroma）· `bm25`（字符 bigram，ASCII 词整体保留）· `hybrid`（RRF 融合）· `hybrid_rerank`（RRF Top30 → bge-reranker-v2-m3 精排 → Top5）；版本加权经 `retrieval.params` 配置。
- **生成**：引用先以 `sources` 事件下发，再逐 token 流式出词，最后 `done`。Prompt 含无证据拒答与多来源冲突披露规则。

引用契约：7 字段 wire（`node_id` / `source_id` / `source_name` / `section` / `page_print` / `page_physical` / `score`），加第 8 字段 `source_url`（HTML 来源指向本地原文，PDF 为 `null`）。正文不下发，需要时经 `/nodes/{node_id}` 取。PDF 双页码满足 **印刷页 = 物理页 − 6**，印刷页码以页眉印刷数字为地面真值。

| 目录 | 说明 |
|---|---|
| `server/` | 服务门面：REST + SSE、MCP Server（stdio）、日志设施 |
| `retrieval/` | Embedding / 向量索引 / BM25 / Hybrid(RRF) / 精排 / 检索器 |
| `generation/` | Prompt 版本 / Context 组装 / LLM 客户端 / 拒答判定 |
| `data_pipeline/` | 解析 / 清洗 / 章节树 / 三方案 chunker（含 HTML loader） |
| `evaluation/` | 问题集、标注、错误案例、判分、实验与回归报告 |
| `configs/experiments/` | 一次实验一个 yaml |
| `scripts/` | 入库、建索引、实验流水线、回归矩阵等入口 |
| `web/` | 问答界面（Vue 3 + Vite） |
| `data/processed/` | 统一 Node 集（入库） |
| `data/raw/` · `data/cleaned/` · `indexes/` · `logs/` | 本机产物，不入 Git |

## 配置驱动的实验

一切分块 / 检索 / 生成 / 评测实验都经由 `configs/experiments/*.yaml` 切换：文件名即实验 ID，未知字段报错并给拼写建议——换实验只改配置，不改代码。

- 索引目录按 `{method}_{embed}_{hash8}` 命名，`hash8` **只由索引身份段派生**（`chunking` / `embedding` / `index` / `retrieval.mode|params|filters`）——改生成或评测段不会让已有索引失效。
- 复用索引前硬校验产物指纹 `nodes_file_sha12`（CRLF 归一化后计算）：产物变了而配置没变的脏索引会被拒绝复用并提示重建。
- hybrid 走**引用制**（`retrieval.components: {vector: <实验名>, bm25: <实验名>}`），运行时融合、无需重建索引。
- 现存 13 个配置，覆盖基线、分块对照、检索模式消融、多来源与精排；多来源统一 Node 集 1638 条（PDF 301 + HTML 1337）。

逐参数说明见 [`configs/experiments/README.md`](./configs/experiments/README.md)。

## 评测与回归

```bash
make test                                                       # 单测全套（452 项）
make audit                                                      # 标注真值核对（指标闸门的前置）
make regression                                                 # 回归矩阵（全部实验）
make regression REG_ARGS=--changed-only                          # 按 git 变更推断范围
make regression REG_ARGS="--only struct_v1,struct_bm25 --promote"  # 提基准锚点
```

- **标注闸门**：`make audit` 的判据只来自 Node 产物与章节树（不调检索器），用于识别"标注 = 检索结果回显"这类自证循环与题面损坏；退出码非 0 时不得启用指标通道。
- **双通道**：默认只比检索明细（top-K 重合率、rank-1 一致率、空结果数、耗时），与标注无关即可发现退化；指标通道需 `--with-metrics` 显式启用。
- **可比性闸门**：比对前核 `config_hash8` 与 Node 集 / 问题集 / 标注集三份指纹；输入变了判 `incomparable` 而非"回归"。
- 退出码非 0 = 存在 `regression` / `failed`，可直接挂 CI 或用作合并前门禁。
- 报告落 `evaluation/reports/`：`regression_latest.md` 为矩阵摘要，`baseline/` 为人工提定的基准锚点。

评测资产：120 题标注集 · 12 题跨来源集 · 20 题拒答专项 · 70 例真实错误案例；检索指标 hit@5 / mrr@5 / precision@5 / recall@5，回答侧 faithfulness / answer_relevance / correctness / citation_accuracy。

## Docker 部署说明

### 镜像内外的边界

| 在镜像内（自带） | 在镜像外（外部依赖） |
|---|---|
| 代码与 Python 依赖（torch 为 CPU 轮子） | LLM 服务（OpenAI 兼容），靠 `.env` 指向 |
| `data/processed/` 统一 Node 产物（1638 条） | `logs/`——运行期输出，挂载到宿主便于回查 |
| `indexes/` 六套索引（向量 / BM25 / hybrid 子索引） | — |
| `data/raw/` PDF 与 HTML 原文（`/documents/{source_id}/{file}` 打开原文靠它） | — |
| 模型权重：bge-m3（embedding）+ bge-reranker-v2-m3（精排） | — |

两个容器：`backend`（FastAPI REST + SSE，容器内 8000）与 `frontend`（nginx 托管前端产物并反代后端 6 条 API 路径，容器内 80）。前端 API 调用全走相对路径，开发态由 Vite proxy 转发、容器态由 nginx 转发，两态行为一致。

### 构建期需要权重来源

权重约 4.4GB，不适合进 Git，构建镜像时从本机已有的模型缓存拷入（compose 的 `additional_contexts` 声明）。这是**构建期**依赖，镜像构建完成后不再需要：

| 权重 | 默认来源 | 说明 |
|---|---|---|
| bge-m3（embedding） | `%LOCALAPPDATA%\llama_index\llama_index\Cache` | LlamaIndex 的 `HuggingFaceEmbedding` 会显式传自己的 `cache_dir`，权重落在 LlamaIndex 缓存而非 HF 缓存 |
| bge-reranker-v2-m3（精排） | `%USERPROFILE%\.cache\huggingface\hub` | `CrossEncoder` 走 HF 默认缓存 |

缓存不在默认位置或构建机不是 Windows：`LLAMA_INDEX_CACHE_HOST=<路径> HF_CACHE_HOST=<路径> make docker-serve`。

### 精简镜像（不拷权重，容器自行下载）

构建机没有权重缓存、而目标机可联网时，改用不带权重的镜像：

```bash
IMAGE_TARGET=slim HF_OFFLINE=0 docker compose up -d --build
```

此形态需给后端挂两个命名卷持久化权重（`model-llama:/root/.cache/llama_index`、`model-hf:/root/.cache/huggingface`），否则容器重建即丢。

### 改产物不重建镜像

默认形态下知识库在镜像内，改了 `data/processed` 或 `indexes/` 需重建镜像。做实验时可叠加覆盖文件改为读宿主目录（前提：宿主跑过 `make ingest && make index`）：

```bash
make docker-serve MOUNTS=1        # 对应 docker-compose.mounts.yml
```

注意它会**遮住**镜像内自带的知识库与权重——若宿主目录为空，服务端会以可读错误拒绝启动，不会静默降级。

`make docker-clean` 停栈并删除本机构建的镜像。

## 注意事项

- **端口**：默认前端 5173、后端 8000，与源码运行的 `make serve` / Vite 开发服务器是同一批端口，二者不要同时使用。要并跑：`BACKEND_PORT=8001 WEB_PORT=18080 make docker-serve`。
- **端口被占用**：宿主端口已被其他进程占用时，容器仍会正常启动但端口不转发，表现为"容器健康、页面打不开"。换一个端口即可。
- **离线环境**：权重随镜像提供，容器内默认离线（`HF_HUB_OFFLINE=1`），不会因联网取模型而卡住。
- **依赖下载**：构建镜像时基础镜像来自 Docker Hub；`npm ci` 默认走 npmmirror、pip 走清华源，可用 `NPM_REGISTRY` / `PIP_INDEX` 覆盖。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`architecture.md`](./docs/architecture.md) | **系统架构**：分层视图、三条运行链路、对外契约、关键不变量、部署形态 |
| [`api.md`](./docs/api.md) | REST + SSE 契约：事件协议、Citation 字段、score 量纲按 mode 定标、错误双通道 |
| [`experiment-results.md`](./docs/experiment-results.md) | **实验结果分析**：分块 / 检索 / 多来源 / 精排对比、回答侧四指标、拒答专项、错误案例与结论 |
| [`reliability-report.md`](./docs/reliability-report.md) | 可靠性与拒答专项结果 |
| [`ingest-pipeline.md`](./docs/ingest-pipeline.md) | 入库链路、多来源注册表、跨来源契约校验 |
| [`html-loader.md`](./docs/html-loader.md) | Doxygen HTML 解析接口与产物口径 |
| [`retrieval-log-schema.md`](./docs/retrieval-log-schema.md) | 检索日志字段定义 |
| [`index-rebuild-drill.md`](./docs/index-rebuild-drill.md) | 索引重建与回切流程 |
| [`mcp.md`](./docs/mcp.md) | MCP Server 工具契约与 stdio 使用说明 |

## 能力与现状

- **检索**：向量 / BM25 / Hybrid(RRF) / Hybrid+精排 四种模式，版本加权可配。
- **回答**：Prompt v2（多来源 + 冲突披露 + 来源优先级）、流式输出、引用溯源（双页码 / 来源分型 / 原文链接）、无证据拒答。
- **评测**：120 题标注集 + 12 题跨来源集 + 20 题拒答专项 + 70 例真实错误案例；回答侧四指标；回归矩阵与三指纹可比性闸门。
- **服务**：REST + SSE、MCP Server（stdio）、四级日志（请求 / 检索 / 回答 / 引用回查）。

## make 目标一览

| 目标 | 作用 | 常用参数 |
|---|---|---|
| `setup` | 建 venv + 装依赖 | `PIP_INDEX=`（默认清华源） |
| `ingest` | raw → cleaned → processed（含分块）六步全链路 | `CFG=configs/experiments/<实验>.yaml` |
| `index` | 建索引（幂等，先删后建）+ manifest + 产物指纹 | `CFG=`；`--list` 盘点与回切 |
| `experiment` | 单实验：保障索引就绪 → 全量题检索 → 报告落盘 | `CFG=` / `--rebuild` / `--fake-embed` / `--sample N` |
| `regression` | 一键回归矩阵：跑相关实验并与历史/基准比对 | `REG_ARGS='--only a,b'` / `--changed-only` / `--with-metrics` / `--promote` |
| `audit` | 标注真值核对（判据只来自产物，不调检索器） | 参数直传脚本，如 `--emit-abstention` |
| `test` | 单测全套 | — |
| `serve` | FastAPI（REST + SSE） | `APP_HOST=` `APP_PORT=` |
| `inspect` | Node 产物质检与抽查（分来源统计） | — |
| `mcp` / `smoke-mcp` | MCP Server（stdio）与其端到端冒烟 | — |
| `docker-build` / `docker-serve` | 构建镜像、一键起后端 + 前端容器栈 | `BACKEND_PORT=` `WEB_PORT=` `IMAGE_TARGET=slim` `MOUNTS=1` |
| `docker-smoke` / `docker-ps` / `docker-logs` / `docker-stop` / `docker-clean` | 容器形态冒烟与运维 | — |

解释器规则：存在 `.venv` 时全部目标自动使用 `.venv` 内的 python，否则回退系统 python；`make help` 会打印当前选中的解释器。
