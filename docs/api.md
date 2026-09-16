# RAG4ZRDDS API 契约（v0.16 · 本地文档原文 + 节点详情按来源格式 + 中止语义）

> 维护人：成员 D。前端（成员 E）以此文档对接；字段变更会同步更新本页。
> 模式现状（2026-09-14）：`mock`=确定性假数据（前端联调随时可用）；`live`=**检索与生成均已真实**（B 检索 + C 生成，需先 `make index` 并在 `.env` 填好 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`，三者缺一即启动期报错）。生成后端已实测两种：云端 OpenAI 兼容 API，与本地 Ollama（经 `models/llm_gateway.py` 网关，见 `docs/demo-runbook.md`）。`sources` 事件为真实引用（SourceRef 7 字段；正文 text 仅生成侧使用，下发前由服务端投影剥离），随后 `token` 流式回答。接口形状两模式不变。

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

v0.14 起附带知识库统计与可用实验（F1/F4，review §4.1）：

```json
{
  "status": "ok", "mode": "live",
  "kb": {
    "experiment": "struct_multisrc_v1",
    "retrieval_mode": "vector",
    "index_dirname": "struct_bge-m3_d57f695e",
    "node_total": 1606,
    "top_k": 5,
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
  `top_k`（**v0.17 新增**）＝**运行时**单次回答最多带几条引用（`QUERY_TOP_K`，默认 5），前端工具栏 chip 应显示此值而非写死——
  注意它**不是**实验配置里的 `retrieval.top_k`：请求不带 `top_k` 时 `POST /query` 用的是 `settings.default_top_k`，配置里那个只作用于离线实验，两者可以不等。
- `experiments`：可用实验 ID 白名单（= `configs/experiments/*.yaml` 文件名 stem），与 `/query` 的 `experiment` 参数同源；前端可据此渲染检索通路选择器（F4）。
- `experiment_modes`（**v0.16 新增**）：实验 ID → 检索模式（读不到的配置跳过，如模板文件）。**用途是让前端按模式决定"分数怎么显示"**：
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
| experiment | string | 否 | **v0.14 新增**：实验 ID（`configs/experiments/*.yaml` 文件名 stem），live 模式下本次请求改用该实验的检索管线（服务端懒组装并缓存，首次切换需加载模型/索引，数秒~数十秒）；白名单见 `/healthz` 的 `experiments`，未知 ID 返回 422 并列出可用值。**mock 模式忽略该参数**；缺省用服务端启动配置（零破坏） |

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
| page_physical | PDF 物理页码（1 基，与阅读器页码一致）；**约定 page_print = page_physical − 6**（2026-08-29 以 PDF 页眉印刷数字逐页核对定值；旧 +7 约定为方向错误，已作废） |
| score | 相关性得分，越高越相关。**量纲依实验配置的 `retrieval.mode` 而变，跨模式不可比**：`vector` 为 cosine 相似度（实测 301 块语料落在 0.46~0.78）；`bm25` 为未归一化原始 BM25 分数（同一语料实测 7.70~56.43）；`hybrid` 为 RRF 融合分（k=60 时理论 0~2/61≈0.033，双路一致命中取最高）；`hybrid_rerank` 为交叉编码器精排分（bge-reranker-v2-m3，**sigmoid 后 0~1**——B 实测 120 题 0.084~0.991，2026-09-14 定死；输入按 512 token 截断，`retrieval/rerank.py::build_reranker`）。另注意：实验配置 `retrieval.params.version_pref` 生效时，score 改为**候选池内 min-max 归一化排序分 + 版本加成**（PR#34 设计 §3.2）——此时任何模式下 score 都不再具有跨查询、跨配置可比性，只能在同一次响应内部比较排序。只能在同一模式、同一配置内比较与排序 |

> **score 阈值（2026-09-07 会签决议：按 mode 分别定标，待 C/E/B 例会追认；2026-09-13 补 hybrid；2026-09-14 补 hybrid_rerank 与 version_boost 配置，PR#34 会签）**：`vector` 模式弱证据阈值 **0.35** 起试（实测正常命中 0.46~0.78、无证据题 top1 约 0.52；0.35 只拦真正的低分尾，待真实标注产出后校准）；`bm25` 原始分量纲随语料漂移，**不设绝对阈值**——弱证据判定改用「返回条数少于 `top_k` / 空 `sources`」信号（bm25 侧零词面重叠候选已在检索层过滤，空结果即无词面证据）；`hybrid` 融合分为 RRF 分（`Σ 1/(rrf_k+rank)`，k=60 时单路命中 1/61~1/90、双路一致最高 2/61≈0.0328），与 cosine/bm25 均不可比，**不设绝对阈值**——弱证据判定沿用「返回条数少于 `top_k` / 空 `sources`」信号；`hybrid_rerank` 精排分为 sigmoid 0~1（B 实测 0.084~0.991），与 `vector` 的 cosine 数值区间形似但语义不同，**不设绝对阈值**——弱证据判定沿用「返回条数少于 `top_k` / 空 `sources`」信号。**凡 `version_pref`/`version_boost` 生效的配置，score 为池内归一化排序分，任何模式下都不适用绝对阈值**（弱证据信号同上）。**前端「弱证据」弱化展示仅在 `vector` 模式启用**。字段形状未变，前端解析无需改动。

> 展示建议（指南 §20）：来源卡片形如"《ZRDDS用户手册》，第 54 页，9.3.1 节"，优先展示 `page_print` 与 `section`。

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

### 客户端中止（v0.16 明确语义）

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

回看某次问答的完整记录（问题 + 答案 + 引用），供来源卡片渲染与排障。v0.4 起记录持久化到 `{LOG_DIR}/sources.jsonl`（默认 `logs/`，不入 Git），**服务重启后仍可回查**；内存仅保留最近 `SOURCES_CACHE_SIZE` 条作为读取窗口——路径与响应形状不变。

```json
{
  "request_id": "a1b2c3d4e5f6",
  "question": "如何创建 DataWriter？",
  "answer": "…",
  "sources": [ …SourceRef 7 字段 + source_url… ]
}
```

未命中：HTTP 404，`error` 说明可能不存在或已超出缓存范围。

### v0.11：回查记录里的 `source_url`（缺口 W1 的过渡方案）

| 字段 | 出现位置 | 取值 |
|---|---|---|
| `source_url` | **仅 `/sources/{rid}`（及 MCP `get_sources`）的 `sources[]`** | HTML 来源 = 该 Node 的原文页 URL；PDF 来源 = `null` |

- 为什么只加在回查侧：`SourceRef` 七字段是与前端会签过的 **wire 契约**，扩第 8 字段需 B（投影）/C（citation 组装）/E（渲染）会签；在会签完成前，SSE 事件**不带**该字段，接口形状不变。
- 数据来源：服务端启动时从本实验的 Node 产物建 `node_id → source_url` 表（`node_id ← chunk_id` 映射已锁定），查不到即为 `null`。启动日志会打印装载规模。
- 前端可**无条件读该键**（恒存在，值可为 null）；MCP 侧 `get_sources` 同语义。URL 的正式值仍待例会确认（现为文档站占位 base_url）。

## GET /nodes/{node_id} —— 单节点详情回查（v0.14 新增 · v0.15 扩跨实验查找）

按 node_id 返回单个 Node 的**原文正文与元数据**，供前端"节点详情"展示该条引用的原文（F3，review §4.1）。数据来自服务端 Node 产物表（默认实验启动时装载，其余实验首次回查时按需装载并缓存）。

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

**v0.16 字段修正（重要）**：页码字段此前误用 SourceRef 的命名（`page_print`/`page_physical`），而 Node 产物的 metadata 契约是
`printed_page_start|end`、`physical_page_start|end`——导致"节点详情"里 PDF 的页码恒为 `—`。现按产物契约取值，并额外给出 `*_end`
（**一个节点可以跨页**，前端显示区间如 `印刷页 127–128`）。HTML 来源的页字段在产物里是字面量字符串 `"None"`，服务端归一为 `null`；
**前端按 `source_type` 分格式渲染**：PDF 显示印刷页/物理页 + 正文；HTML 不显示页码，改显示 `source_file`/`title` + 章节路径 + 原文外链。

- **`experiment`（v0.15 新增）**：该 node_id 实际命中的实验 ID。**切换检索模式后的 node_id 不再 404**（v0.15 修复）——此前只查默认实验的产物表，配合 `/query` 的 `experiment` 参数会 404，即"能切模式"与"能看原文"两个功能无法并存（本机实测复现）。现按实验白名单顺序查找，命中即返回；同一 Node 集被多个实验共享时（如同 hash8 的 `final_v1` 与 `struct_multisrc_v1`）返回先命中的实验名，**该字段仅作标识，不影响 text 内容**。
- **正文出网范围（待 B/C/E 会签追认）**：SSE wire 仍为 SourceRef 7 字段不变，chunk 原文不进 `sources` 事件与 `sources.jsonl`；本端点是既有"正文不下发"立场的**定向放宽**——按需、单节点、仅回查方向。
- **404**：`mock` 模式（无 Node 产物）或 node_id 不在任何已索引实验的产物中，`error` 均给出可读说明。node_id 以 `/query` 的 `sources` 事件为准。
- `text` 长度上限即分块上限（默认 2500 字符）；页码/`section_path`/`source_url` 可为 null。
- **`source_url` 现在是本服务的可打开地址**（见下节 `/documents`）：产物里存的是配置中的占位外部域名（`https://docs.zrtechnology.com/…`，实测不可达），
  服务端启动时改写为 `/documents/{source_id}/{file}`；文件不存在时保留原值（不把"打不开"换成"404"）。

## GET /documents/{source_id}/{filename} —— 本地文档原文（v0.16 新增）

打开引用对应的**原始文档快照**（如 Doxygen HTML 页），供前端"打开原文"外链使用。文件从实验配置 `sources[].path` 声明的本地目录读取
（即 A 的 ingest 用的同一份快照，离线可用）。

- **白名单**：来源目录在服务启动时从**全部实验配置**合并登记（跨实验可用——默认实验只有 PDF 时，多来源实验产生的 HTML 链接依然能打开）；
  未登记的 `source_id` → 404；只接受单层文件名，含路径分隔符或 `..` 的请求一律拒绝（400/404），解析后必须仍在来源目录内。
- **媒体类型**：按扩展名推断（`.html` → `text/html`），其余回退 `application/octet-stream`。
- 这是"引用可溯源到原文页"的落地形态；**Node 产物里的分块正文仍只经 `/nodes/{node_id}` 出网**，SSE wire 仍为 SourceRef 7 字段。

```bash
curl -I "http://127.0.0.1:8000/documents/zrdds_dev_guide/group___c_publication.html"   # 200 + text/html
```

## POST /feedback —— 回答反馈落库（v0.10 新增 · D 侧提案，待 E/C 会签）

指南 §8 成员 E 任务「有帮助/无帮助反馈按钮与数据落库」的落库侧。前端只需按本契约发一次 POST，存储与聚合归 D 的日志设施。

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

## 变更记录

| 版本 | 变更 |
|---|---|
| v0.17 | 2026-09-16：**前端 chip 去写死**（D）——`GET /healthz` 的 `kb` 新增 **`top_k`**（运行时 `QUERY_TOP_K`，即请求未带 `top_k` 时实际返回的引用条数上限）。前端工具栏原先静态显示 `Top-K 5`，改 `QUERY_TOP_K` 后即与后端实际条数不符（F4 同类静态装饰）。既有字段零增删，前端不改也能跑 |
| v0.16 | 2026-09-16：**演示可用性三项 + 语义澄清**（D）——①新增 **`GET /documents/{source_id}/{filename}`**本地文档原文端点；产物里的占位外部域名统一改写为该本地地址（`/nodes`、`/sources/{rid}`、MCP 一并生效）；②`GET /nodes/{node_id}` **字段修正**：页码改按产物契约（`printed/physical_page_start|end`，此前恒空）+ 新增 `source_type`/`source_file`/`title`（前端按来源格式渲染）；③`/healthz` 新增 **`experiment_modes`**（前端按模式决定分数显示口径：bm25/hybrid 不可比，改用池内相对 + 位次）；④明确**客户端中止语义**（生成器取消、上游流关闭、部分答案留档）。既有字段零增删，前端不改也能跑 |
| v0.15 | 2026-09-16：**`GET /nodes/{node_id}` 扩为跨实验查找**（D，演示可用性修复）——切换检索模式后拿到的 node_id 不再 404（此前只查默认实验的产物表，与 F4 的 experiment 参数互斥）；响应新增 **`experiment`** 字段标识实际命中的实验。既有字段零增删，前端不改也能跑 |
| v0.14 | 2026-09-15：**F1/F3/F4 后端三件**（D，2026-09-15 前端实测四项问题 review §4.1；E 域前端接线待 E）——①`GET /healthz` 新增 `kb`（启动实验的知识库统计：experiment/retrieval_mode/index_dirname/node_total/sources[{id,version,chunks}]；mock 为 null）与 `experiments`（可用实验 ID 白名单）②新增 **`GET /nodes/{node_id}`**：单节点原文+元数据按需回查（F3）；**chunk 原文经此端点出网属"正文不下发"立场的定向放宽，待 B/C/E 会签追认**；SSE wire 7 字段不变 ③`POST /query` 请求体新增可选 **`experiment`**（F4，live 按请求切换检索实验，白名单外 422，registry 懒组装缓存 LRU≤3；mock 忽略）。既有端点既有字段零变化，前端不改也能继续跑 |
| v0.13 | 2026-09-14：**B 回写 `hybrid_rerank` 精排分量纲实测**（PR#34 会签事项 2 闭环）——交叉编码器分 sigmoid 0~1（120 题实测 0.084~0.991），输入按 512 token 截断（不截断时按模型上限 8192 处理、单题 30 候选慢 3 倍）。仍不设绝对阈值，弱证据判定沿用「返回条数少于 top_k / 空 sources」信号。字段无增删，前端无需改解析 |
| v0.12 | 2026-09-14：`hybrid_rerank` 精排分量纲条目 + `version_boost` 生效时的 score 语义（D，PR#34 会签事项 2）——`hybrid_rerank` 为交叉编码器精排分（bge-reranker-v2-m3，具体量纲 sigmoid 0~1 或原始 logits 待 B 冒烟实测定死后回写）；凡 `retrieval.params.version_pref` 生效的配置，score 改为**候选池内 min-max 归一化排序分 + 版本加成**，不再具跨查询/跨配置可比性；`hybrid_rerank` 不设绝对阈值，弱证据判定沿用「返回条数少于 top_k / 空 sources」信号。字段无增删，前端无需改解析 |
| v0.11 | 2026-09-14：缺口 W1 的过渡处置（用户拍板方案 B，D 单方落地）——`GET /sources/{rid}` 与 MCP `get_sources` 的每条引用新增 **`source_url`**（HTML 非空 / PDF 为 `null`），取自本实验 Node 产物（启动时建 `node_id → source_url` 表；多来源实测 1606 条映射 / 1305 条带 URL）。**SSE 的 `sources`/`done` 事件仍是 7 字段、不含该键**（实测确认），因此前端解析零破坏；E 要用 HTML 跳转就从回查接口取。正式扩进 wire 仍需 B/C/E 会签 |
| v0.10 | 2026-09-14：新增 `POST /feedback`（D 侧实现 + 契约提案，**待 E/C 会签后才动前端**）——两档 `rating` 绑定 `request_id` 落 `{LOG_DIR}/feedback.jsonl`，未知 rid 一律 404 拒绝（不产孤儿反馈），`node_ids` 越界 400。**既有 `/query`、`/sources`、`/healthz` 的路径与响应形状零变化，前端不改也能继续跑**；前端接入时只需在答案卡片上加两个按钮 + 一次 POST |
| v0.9 | 2026-09-13：`hybrid` 融合分量纲条目（D，PR#30 落地后补）——RRF 分 `Σ 1/(rrf_k+rank)`（k=60 时单路 1/61~1/90、双路一致最高 2/61≈0.0328），与 cosine/bm25 互不可比；不设绝对阈值，弱证据判定沿用「返回条数少于 top_k / 空 sources」信号；前端「弱证据」弱化展示仍仅 vector 模式启用。字段无增删，前端无需改解析 |
| v0.8 | 2026-09-08：检索级日志落地（B 字段定义 `docs/retrieval-log-schema.md` v0.1 + D 接线）——live 模式每次检索追加一条记录到 `{LOG_DIR}/retrievals.jsonl`（含富引用正文，仅落本地不入 Git；`request_id` 可与 `requests.jsonl` 关联）。**API 响应形状与路径无任何变化，前端无需改动**；warmup/脚本直调的检索也会入日志（`request_id` 为 null） |
| v0.7 | 2026-09-07：弱证据阈值定标（D 会签决议，待 C/E/B 例会追认）——按 `retrieval.mode` 分别定标：`vector` 阈值 **0.35** 起试（实测正常命中 0.46~0.78、无证据题 top1 约 0.52；待真实标注产出后校准）；`bm25` 不设绝对阈值，弱证据判定改用「返回条数少于 top_k / 空 sources」信号；前端「弱证据」弱化展示仅 `vector` 模式启用。C 会签第 5 题建议的单一阈值 0.5 作废（在 bm25 下永不触发、在 vector 下误伤约一半正常命中）。字段无增删，前端解析无需改动 |
| v0.6 | 2026-09-07：`score` 量纲澄清（D）。B 于 PR#17 接入 `bm25` 检索模式后，`score` 出现两种互不可比量纲——`vector` 为 cosine 相似度（实测 0.46~0.78）、`bm25` 为未归一化原始分（同一语料实测 7.70~56.43）。本版在字段说明中写明量纲依 `retrieval.mode` 而变、只可同模式内比较，并把 Citation 会签第 5 题的「弱证据阈值」标为待按 mode 分别定标（单一阈值 0.5 在 bm25 下永不触发）。`bm25` 侧零词面重叠候选已在检索层过滤，故**返回空 `sources` 是该模式唯一的无证据硬信号**。字段无增删，前端无需改解析；「弱证据」弱化展示请等阈值定标后再接 |
| v0.5 | 2026-08-31：live 接线 C 生成（`generation/` 包，OpenAI 兼容流式）。live 模式需 `.env` 填 `LLM_*`；检索器改返富引用（含 text 正文供生成组装 context），`/query` 下发前投影回 SourceRef 7 字段——**接口形状不变，前端无需改动**。Prompt v0 落地两条硬规则（仅依据检索作答 / 给出来源） |
| v0.4 | 2026-08-30：第二周日志设施（骨架）——请求级 JSONL 日志 `{LOG_DIR}/requests.jsonl`（request_id/method/path/status/耗时）；`/sources` 由内存环形缓存改为持久化 `{LOG_DIR}/sources.jsonl`（重启可回查）；新增 `LOG_DIR`、`SOURCES_CACHE_SIZE` 环境变量。响应形状与路径均不变，前端无需改动；检索/回答级日志字段待 B/C 会签 |
| v0.3 | 2026-08-29：双页码真值修正——`page_print = page_physical − 6`（页眉印刷数字逐页核对；手册前 6 页为封面/罗马数字前言），物理页码统一 1 基；v0.2 的 +7 约定作废。字段无增删，前端无需改解析，仅展示数值变化 |
| v0.2 | 2026-08-28：live 接线 B 检索（真实 sources）；双页码约定定为 +7；新增 `RAG_EXPERIMENT_CONFIG`；生成待 C（PendingAnswerStream 可读缺口） |
| v0.1 | 骨架：/healthz、/query(SSE)、/sources 回查；mock/live 双模式 |

## 已知边界（现状与后续）

- **OpenAI 兼容门面 `/v1/chat/completions`：经决策不做**（前端 E 走自研轻量页，指南 §7 的触发条件未成立）。原预留的空目录 `server/openai_compat/` 已于 2026-09-14 删除。
- **MCP 工具已交付**：`server/mcp_server.py`（stdio，两工具 `query_knowledge_base` / `get_sources`），契约见 `docs/mcp.md`；与本文的引用语义一致（含 v0.11 的回查附带 `source_url`）。
- **缺口 W1**：`source_url` 目前只在**回查通道**（`/sources/{rid}`、MCP `get_sources`）附带，SSE `sources`/`done` 仍是 7 字段 wire；正式扩第 8 字段需 B/C/E 会签（`docs/week4-delivery-review.md` §2.3/§4.6）。
- **回答级日志与回答质量指标**：`POST /feedback`（v0.10）为 D 侧提案待 E/C 会签；`response_metrics` 需成员 C 的 `evaluation/runners/answer_eval.py`，接入前 `run_experiment` 仍拒绝非空 `response_metrics`。
- **Citation 字段定版**：仍按 `docs/citation-contract-draft.md` 与 C/E 会签推进（section 截断落点、弱证据阈值按 mode 定标已落在 v0.7/v0.9）。
