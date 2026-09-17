# RAG4ZRDDS API 契约

> 本文是前后端对接的契约基准；字段变更会同步更新本页。
> 模式：`mock`=确定性假数据（前端联调随时可用）；`live`=**检索与生成均已真实**（需先 `make index` 并在 `.env` 填好 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`，三者缺一即启动期报错）。生成后端支持任意 OpenAI 兼容服务：云端 API 或本地 Ollama（经 `models/llm_gateway.py` 网关）。`sources` 事件为真实引用（SourceRef **8 字段**，含 `source_url`；正文 text 仅生成侧使用，下发前由服务端投影剥离），随后 `token` 流式回答。接口形状两模式不变。

## 启动

```bash
make serve                       # 默认 127.0.0.1:8000；可用 APP_HOST/APP_PORT 覆盖
curl http://127.0.0.1:8000/healthz
```

模式由 `.env` 的 `RAG_MODE` 控制：`mock`=假数据（默认）｜`live`=真实检索 + 生成（需先 `make index`，并在 `.env` 填好 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`）。live 模式按 `RAG_EXPERIMENT_CONFIG`（默认 `configs/experiments/struct_v1.yaml`）定位索引目录与 embedding；找不到索引或 LLM 未配置时启动即报可读错误。

## 通用约定

- 每个响应都带 `X-Request-ID` 头（12 位十六进制），排障时引用它。
- 流开始前的错误：HTTP 状态码 + JSON 体 `{"error": "人类可读说明"}`。
- 流开始后的错误：SSE `error` 事件（HTTP 已是 200，无法改状态码）。
- 中文一律 UTF-8 原样传输。

---

## GET /healthz

存活检查，不依赖任何下游组件。

```json
{ "status": "ok", "mode": "mock" }
```

附带知识库统计与可用实验：

```json
{
  "status": "ok", "mode": "live",
  "kb": {
    "experiment": "struct_multisrc_v1",
    "retrieval_mode": "vector",
    "index_dirname": "struct_bge-m3_d57f695e",
    "node_total": 1606,
    "sources": [
      { "id": "user_manual", "version": "2.0", "chunks": 301 },
      { "id": "zrdds_dev_guide", "version": "2.4", "chunks": 1305 }
    ]
  },
  "experiments": ["struct_v1", "struct_bm25", "semantic_v1", "…"],
  "experiment_modes": { "struct_v1": "vector", "struct_bm25": "bm25", "struct_hybrid": "hybrid", "…": "…" }
}
```

- `kb`：**当前启动配置**的知识库统计（`experiments[].id`/`version` 来自实验配置 `sources[]`，`chunks` 按启动时 Node 产物逐来源实数）；`mock` 模式为 `null`。
- `experiments`：可用实验 ID 白名单（= `configs/experiments/*.yaml` 文件名 stem），与 `/query` 的 `experiment` 参数同源；前端可据此渲染检索通路选择器（F4）。
- `experiment_modes`：实验 ID → 检索模式（读不到的配置跳过，如模板文件）。**用途是让前端按模式决定"分数怎么显示"**：
  `vector`（cosine 0~1）与 `hybrid_rerank`（sigmoid 0~1）的分数量纲可跨查询比较；`bm25`（原始词面分，无上界）与 `hybrid`（RRF，~0.03）
  不可比——前端对后两者改用"池内相对进度 + 位次 + 不可比说明"，不渲染成相关度百分比。

## POST /query —— 流式问答（SSE）

### 请求

```json
{ "question": "如何创建 DataWriter？", "top_k": 5 }
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| question | string | 是 | 1~2000 字符；纯空白会被拒绝 |
| top_k | int | 否 | 1~20；缺省取服务端 `QUERY_TOP_K`（默认 5） |
| experiment | string | 否 | 可选：实验 ID（`configs/experiments/*.yaml` 文件名 stem），live 模式下本次请求改用该实验的检索管线（服务端懒组装并缓存，首次切换需加载模型/索引，数秒~数十秒）；白名单见 `/healthz` 的 `experiments`，未知 ID 返回 422 并列出可用值。**mock 模式忽略该参数**；缺省用服务端启动配置（零破坏） |

### 响应事件流（`Content-Type: text/event-stream`）

顺序固定为 **sources → token×N → done**（引用先于答案）：

| event | data 内容 | 说明 |
|---|---|---|
| `sources` | `{request_id, sources[]}` | 检索完成即推送全部引用 |
| `token` | `{request_id, text}` | 答案文本增量，按序拼接即完整答案 |
| `done` | `{request_id, answer, sources[]}` | 正常结束标志；answer=全部 token 拼接 |
| `error` | `{request_id, error}` | 流中途出错；此后不会再有其他事件 |

帧格式示例：

```text
event: sources
data: {"request_id":"a1b2c3d4e5f6","sources":[{"node_id":"mock-1a2b3c4d-00","source_id":"user_manual","source_name":"ZRDDS用户手册.pdf","section":"9.3.1","page_print":54,"page_physical":48,"score":0.95}]}

event: token
data: {"request_id":"a1b2c3d4e5f6","text":"【Mock 模式回答】"}

event: done
data: {"request_id":"a1b2c3d4e5f6","answer":"…完整答案…","sources":[…]}
```

### 引用字段（SourceRef）

| 字段 | 说明 |
|---|---|
| node_id | Node 全局唯一 ID |
| source_id | 来源短名（对应实验配置 `sources[].id`），如 `user_manual` |
| source_name | 来源显示名，如 `ZRDDS用户手册.pdf` |
| section | 章节号，如 `3.4.2` |
| page_print | 印刷页码（手册纸面上印的数字；前言罗马数字页无印刷页码时为空） |
| page_physical | PDF 物理页码（1 基，与阅读器页码一致）；**约定 page_print = page_physical − 6**（以 PDF 页眉印刷数字为地面真值逐页核对） |
| source_url | **原始文档地址（第 8 字段）**：HTML 来源为本地 `/documents/{source_id}/{filename}` 地址（离线可直接打开原文，产物里的占位外部域名 `docs.zrtechnology.com` 在启动装载时统一改写为本地地址）；PDF 来源为 `null`。`sources`、`done` 事件与 `/sources/{rid}` 回查三处同形 |
| score | 相关性得分，越高越相关。**量纲依实验配置的 `retrieval.mode` 而变，跨模式不可比**：`vector` 为 cosine 相似度（实测 301 块语料落在 0.46~0.78）；`bm25` 为未归一化原始 BM25 分数（同一语料实测 7.70~56.43）；`hybrid` 为 RRF 融合分（k=60 时理论 0~2/61≈0.033，双路一致命中取最高）；`hybrid_rerank` 为交叉编码器精排分（bge-reranker-v2-m3，**sigmoid 后 0~1**——实测 120 题落在 0.084~0.991；输入按 512 token 截断，`retrieval/rerank.py::build_reranker`）。另注意：实验配置 `retrieval.params.version_pref` 生效时，score 改为**候选池内 min-max 归一化排序分 + 版本加成**——此时任何模式下 score 都不再具有跨查询、跨配置可比性，只能在同一次响应内部比较排序。只能在同一模式、同一配置内比较与排序 |

> **score 阈值**：`vector` 模式弱证据阈值 **0.35** 起试（实测正常命中 0.46~0.78、无证据题 top1 约 0.52；0.35 只拦真正的低分尾，待真实标注产出后校准）；`bm25` 原始分量纲随语料漂移，**不设绝对阈值**——弱证据判定改用「返回条数少于 `top_k` / 空 `sources`」信号（bm25 侧零词面重叠候选已在检索层过滤，空结果即无词面证据）；`hybrid` 融合分为 RRF 分（`Σ 1/(rrf_k+rank)`，k=60 时单路命中 1/61~1/90、双路一致最高 2/61≈0.0328），与 cosine/bm25 均不可比，**不设绝对阈值**——弱证据判定沿用「返回条数少于 `top_k` / 空 `sources`」信号；`hybrid_rerank` 精排分为 sigmoid 0~1（B 实测 0.084~0.991），与 `vector` 的 cosine 数值区间形似但语义不同，**不设绝对阈值**——弱证据判定沿用「返回条数少于 `top_k` / 空 `sources`」信号。**凡 `version_pref`/`version_boost` 生效的配置，score 为池内归一化排序分，任何模式下都不适用绝对阈值**（弱证据信号同上）。**前端「弱证据」弱化展示仅在 `vector` 模式启用**。

> 展示建议：来源卡片形如"《ZRDDS用户手册》，第 54 页，9.3.1 节"，优先展示 `page_print` 与 `section`。

### 调用示例

```bash
curl -N -X POST http://127.0.0.1:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "如何创建 DataWriter？"}'
# -N 关闭缓冲，逐事件实时打印
```

> ⚠️ **中文终端编码坑**：若返回 `请求体解析失败…UTF-8…`，说明终端把中文按 GBK 编码发出了。
> 解法任选：① 改用 Git Bash / Swagger UI；② cmd 下先 `chcp 65001` 再 curl；
> ③ 把请求体存成 UTF-8 文件后 `curl --data-binary @q.json`；④ 先用纯英文问题冒烟。

### 客户端中止

客户端直接断开连接（前端"停止生成"＝`AbortController.abort()`）即可中止生成：

- 服务端生成器被取消，**上游 LLM 流随之关闭**（`generation/llm.py` 在生成器收尾时关闭客户端，不会继续占用推理）；
- 已下发的引用保持有效（X3 语义），仍可经 `/sources/{rid}` 回查；
- 已产出的部分答案以 `…（已终止）` 标注写入回查记录（`answer` 字段），便于反馈归因；
- 中止不是错误：客户端不应展示 error 通道内容，服务端也不写 error 事件。

### 错误格式（流开始前）

所有流开始前的错误统一为：

```json
{ "error": "人类可读的中文说明（含可行解法）", "request_id": "a1b2c3d4e5f6" }
```

| 场景 | 状态码 |
|---|---|
| 问题为空白 | 400 |
| 请求体不是合法 UTF-8 JSON（含 GBK 编码的中文） | 400 |
| 字段不合法（如 top_k 超 20） | 422 |
| 引用记录不存在 | 404 |

## GET /sources/{request_id} —— 引用回查

回看某次问答的完整记录（问题 + 答案 + 引用），供来源卡片渲染与排障。记录持久化到 `{LOG_DIR}/sources.jsonl`（默认 `logs/`，不入 Git），**服务重启后仍可回查**；内存仅保留最近 `SOURCES_CACHE_SIZE` 条作为读取窗口——路径与响应形状不变。

```json
{
  "request_id": "a1b2c3d4e5f6",
  "question": "如何创建 DataWriter？",
  "answer": "…",
  "sources": [ …SourceRef 8 字段（含 source_url）… ]
}
```

未命中：HTTP 404，`error` 说明可能不存在或已超出缓存范围。

### 回查记录里的 `source_url`

| 字段 | 出现位置 | 取值 |
|---|---|---|
| `source_url` | **仅 `/sources/{rid}`（及 MCP `get_sources`）的 `sources[]`** | HTML 来源 = 该 Node 的原文页 URL；PDF 来源 = `null` |

- 该字段现已进入 wire 契约（见「引用字段」表），`sources`/`done` 事件、本回查接口与 MCP `get_sources` 三处同形。
- 数据来源：服务端启动时从本实验的 Node 产物建 `node_id → source_url` 表（`node_id ← chunk_id` 映射已锁定），查不到即为 `null`。启动日志会打印装载规模。
- 前端可**无条件读该键**（恒存在，值可为 null）；MCP 侧 `get_sources` 同语义。

## GET /nodes/{node_id} —— 单节点详情回查

按 node_id 返回单个 Node 的**原文正文与元数据**，供前端"节点详情"展示该条引用的原文。数据来自服务端 Node 产物表（默认实验启动时装载，其余实验首次回查时按需装载并缓存）。

```json
{
  "node_id": "struct_v1_00042",
  "experiment": "struct_v1",
  "source_id": "user_manual",
  "source_type": "pdf",
  "source_file": "ZRDDS用户手册.pdf",
  "title": "10.7 DurabilityQosPolicy",
  "version": "2.0",
  "page_print": 127,
  "page_print_end": 128,
  "page_physical": 133,
  "page_physical_end": 134,
  "section_path": ["10", "10.7", "DurabilityQosPolicy"],
  "text": "该 Node 的原文正文…",
  "source_url": null
}
```

**页码字段口径（重要）**：页码字段使用产物 metadata 的命名（`page_print`/`page_physical`），而 Node 产物的 metadata 契约是
`printed_page_start|end`、`physical_page_start|end`——导致"节点详情"里 PDF 的页码恒为 `—`。现按产物契约取值，并额外给出 `*_end`
（**一个节点可以跨页**，前端显示区间如 `印刷页 127–128`）。HTML 来源的页字段在产物里是字面量字符串 `"None"`，服务端归一为 `null`；
**前端按 `source_type` 分格式渲染**：PDF 显示印刷页/物理页 + 正文；HTML 不显示页码，改显示 `source_file`/`title` + 章节路径 + 原文外链。

- **`experiment`**：该 node_id 实际命中的实验 ID（按实验白名单顺序查找，命中即返回；同一 Node 集被多个实验共享时返回先命中的实验名，**该字段仅作标识，不影响 text 内容**）。
- **正文出网范围**：chunk 原文不进 `sources` 事件与 `sources.jsonl`；本端点是"正文不下发"立场的**定向放宽**——按需、单节点、仅回查方向。
- **404**：`mock` 模式（无 Node 产物）或 node_id 不在任何已索引实验的产物中，`error` 均给出可读说明。node_id 以 `/query` 的 `sources` 事件为准。
- `text` 长度上限即分块上限（默认 2500 字符）；页码/`section_path`/`source_url` 可为 null。
- **`source_url` 现在是本服务的可打开地址**（见下节 `/documents`）：产物里存的是配置中的占位外部域名（`https://docs.zrtechnology.com/…`，实测不可达），
  服务端启动时改写为 `/documents/{source_id}/{file}`；文件不存在时保留原值（不把"打不开"换成"404"）。

## GET /documents/{source_id}/{filename} —— 本地文档原文

打开引用对应的**原始文档快照**（如 Doxygen HTML 页），供前端"打开原文"外链使用。文件从实验配置 `sources[].path` 声明的本地目录读取
（即 A 的 ingest 用的同一份快照，离线可用）。

- **白名单**：来源目录在服务启动时从**全部实验配置**合并登记（跨实验可用——默认实验只有 PDF 时，多来源实验产生的 HTML 链接依然能打开）；
  未登记的 `source_id` → 404；只接受单层文件名，含路径分隔符或 `..` 的请求一律拒绝（400/404），解析后必须仍在来源目录内。
- **媒体类型**：按扩展名推断（`.html` → `text/html`），其余回退 `application/octet-stream`。
- 这是"引用可溯源到原文页"的落地形态；**Node 产物里的分块正文仍只经 `/nodes/{node_id}` 出网**，SSE wire 只下发引用字段。

```bash
curl -I "http://127.0.0.1:8000/documents/zrdds_dev_guide/group___c_publication.html"   # 200 + text/html
```

## POST /feedback —— 回答反馈落库

「有帮助/无帮助」反馈的落库侧：前端按本契约发一次 POST，存储与聚合由服务端日志设施负责。

### 请求

```json
{
  "request_id": "a1b2c3d4e5f6",
  "rating": "up",
  "comment": "第 2 条引用与问题无关",
  "node_ids": ["struct_v1_...00001"]
}
```

| 字段 | 必填 | 约束 | 说明 |
|---|---|---|---|
| `request_id` | ✅ | 1~32 字符 | 被评价那次回答的 `X-Request-ID`（或 SSE 事件里的 `request_id`） |
| `rating` | ✅ | `up` \| `down` | 两档；细化原因写进 `comment`，不扩枚举 |
| `comment` | — | ≤2000 字符 | 自由文本 |
| `node_ids` | — | ≤20 条 | 指向本次引用里的具体某几条；**必须属于该 `request_id` 的引用集** |

### 响应

- 成功：**201** `{"status":"recorded","feedback_id":"…","request_id":"…","rating":"up"}`
- **404**：`request_id` 无对应记录 → 拒绝并说明"无法归因"。**不留孤儿反馈**（宁可少收，也不收无法回溯到那次问答的反馈）。
- **400**：`node_ids` 含不属于该次回答的节点（防前端把 rid 与 node 配错对），`error` 会列出越界项。
- **422**：`rating` 非 `up|down`、缺 `request_id` 等字段校验失败。

### 落盘

追加到 `{LOG_DIR}/feedback.jsonl`（默认 `logs/`，不入 Git），与请求级 `requests.jsonl`、检索级 `retrievals.jsonl`、引用级 `sources.jsonl` 构成四级日志，均可按 `request_id` 关联。记录字段：

```
ts, feedback_id, request_id, rating, question, answer_present,
cited_nodes, comment?, node_ids?
```

刻意**不落答案正文**（已在 `sources.jsonl`），避免同一长答案被反复复制。

