# RAG4ZRDDS API 契约（v0.7 · 弱证据阈值定标 D）

> 维护人：成员 D。前端（成员 E）以此文档对接；字段变更会同步更新本页。
> 模式现状（2026-08-31）：`mock`=确定性假数据（前端联调随时可用）；`live`=**检索与生成均已真实**（B 检索 + C 生成，需先 `make index` 并在 `.env` 填好 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`）。`sources` 事件为真实引用（SourceRef 7 字段；正文 text 仅生成侧使用，下发前由服务端投影剥离），随后 `token` 流式回答。接口形状两模式不变。

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

## POST /query —— 流式问答（SSE）

### 请求

```json
{ "question": "如何创建 DataWriter？", "top_k": 5 }
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| question | string | 是 | 1~2000 字符；纯空白会被拒绝 |
| top_k | int | 否 | 1~20；缺省取服务端 `QUERY_TOP_K`（默认 5） |

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
| score | 相关性得分，越高越相关。**量纲依实验配置的 `retrieval.mode` 而变，跨模式不可比**：`vector` 为 cosine 相似度（实测 301 块语料落在 0.46~0.78）；`bm25` 为未归一化原始 BM25 分数（同一语料实测 7.70~56.43）。只能在同一模式内比较与排序 |

> **score 阈值（2026-09-07 会签决议：按 mode 分别定标，待 C/E/B 例会追认）**：`vector` 模式弱证据阈值 **0.35** 起试（实测正常命中 0.46~0.78、无证据题 top1 约 0.52；0.35 只拦真正的低分尾，待真实标注产出后校准）；`bm25` 原始分量纲随语料漂移，**不设绝对阈值**——弱证据判定改用「返回条数少于 `top_k` / 空 `sources`」信号（bm25 侧零词面重叠候选已在检索层过滤，空结果即无词面证据）。**前端「弱证据」弱化展示仅在 `vector` 模式启用**。字段形状未变，前端解析无需改动。

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
  "sources": [ …同上 SourceRef… ]
}
```

未命中：HTTP 404，`error` 说明可能不存在或已超出缓存范围。

## 变更记录

| 版本 | 变更 |
|---|---|
| v0.8 | 2026-09-08：检索级日志落地（B 字段定义 `docs/retrieval-log-schema.md` v0.1 + D 接线）——live 模式每次检索追加一条记录到 `{LOG_DIR}/retrievals.jsonl`（含富引用正文，仅落本地不入 Git；`request_id` 可与 `requests.jsonl` 关联）。**API 响应形状与路径无任何变化，前端无需改动**；warmup/脚本直调的检索也会入日志（`request_id` 为 null） |
| v0.7 | 2026-09-07：弱证据阈值定标（D 会签决议，待 C/E/B 例会追认）——按 `retrieval.mode` 分别定标：`vector` 阈值 **0.35** 起试（实测正常命中 0.46~0.78、无证据题 top1 约 0.52；待真实标注产出后校准）；`bm25` 不设绝对阈值，弱证据判定改用「返回条数少于 top_k / 空 sources」信号；前端「弱证据」弱化展示仅 `vector` 模式启用。C 会签第 5 题建议的单一阈值 0.5 作废（在 bm25 下永不触发、在 vector 下误伤约一半正常命中）。字段无增删，前端解析无需改动 |
| v0.6 | 2026-09-07：`score` 量纲澄清（D）。B 于 PR#17 接入 `bm25` 检索模式后，`score` 出现两种互不可比量纲——`vector` 为 cosine 相似度（实测 0.46~0.78）、`bm25` 为未归一化原始分（同一语料实测 7.70~56.43）。本版在字段说明中写明量纲依 `retrieval.mode` 而变、只可同模式内比较，并把 Citation 会签第 5 题的「弱证据阈值」标为待按 mode 分别定标（单一阈值 0.5 在 bm25 下永不触发）。`bm25` 侧零词面重叠候选已在检索层过滤，故**返回空 `sources` 是该模式唯一的无证据硬信号**。字段无增删，前端无需改解析；「弱证据」弱化展示请等阈值定标后再接 |
| v0.5 | 2026-08-31：live 接线 C 生成（`generation/` 包，OpenAI 兼容流式）。live 模式需 `.env` 填 `LLM_*`；检索器改返富引用（含 text 正文供生成组装 context），`/query` 下发前投影回 SourceRef 7 字段——**接口形状不变，前端无需改动**。Prompt v0 落地两条硬规则（仅依据检索作答 / 给出来源） |
| v0.4 | 2026-08-30：第二周日志设施（骨架）——请求级 JSONL 日志 `{LOG_DIR}/requests.jsonl`（request_id/method/path/status/耗时）；`/sources` 由内存环形缓存改为持久化 `{LOG_DIR}/sources.jsonl`（重启可回查）；新增 `LOG_DIR`、`SOURCES_CACHE_SIZE` 环境变量。响应形状与路径均不变，前端无需改动；检索/回答级日志字段待 B/C 会签 |
| v0.3 | 2026-08-29：双页码真值修正——`page_print = page_physical − 6`（页眉印刷数字逐页核对；手册前 6 页为封面/罗马数字前言），物理页码统一 1 基；v0.2 的 +7 约定作废。字段无增删，前端无需改解析，仅展示数值变化 |
| v0.2 | 2026-08-28：live 接线 B 检索（真实 sources）；双页码约定定为 +7；新增 `RAG_EXPERIMENT_CONFIG`；生成待 C（PendingAnswerStream 可读缺口） |
| v0.1 | 骨架：/healthz、/query(SSE)、/sources 回查；mock/live 双模式 |

## 已知边界（后续版本）

- `/v1/chat/completions`（OpenAI 兼容门面）与 MCP 工具：第三周交付
- 回答的 Grounding/拒答行为：C 的 Prompt v0 已落地两条硬规则（仅依据检索作答 / 给出来源）；正式 Grounding/Abstention 细化与 Citation 字段定版在第二周（指南 §6.3 / §6.4）
