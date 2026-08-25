# RAG4ZRDDS API 契约（v0.1 · 骨架阶段）

> 维护人：成员 D。前端（成员 E）以此文档对接；字段变更会同步更新本页。
> 当前为 mock 模式：返回确定性假数据，用于前端联调与链路冒烟；`RAG_MODE=live` 后接口形状不变，仅数据变真。

## 启动

```bash
make serve                       # 默认 127.0.0.1:8000；可用 APP_HOST/APP_PORT 覆盖
curl http://127.0.0.1:8000/healthz
```

模式由 `.env` 的 `RAG_MODE` 控制：`mock`=假数据（默认）｜`live`=真实检索与生成（B/C 实现合入后启用）。

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
| page_print | 印刷页码（手册纸面上印的数字） |
| page_physical | PDF 物理页码；**约定 page_print = page_physical + 6** |
| score | 相关性得分，越高越相关 |

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

回看某次问答的完整记录（问题 + 答案 + 引用），供来源卡片渲染与排障。数据保存在内存环形缓存（最近 100 条），第二周日志设施落地后替换为持久化存储——路径与响应形状不变。

```json
{
  "request_id": "a1b2c3d4e5f6",
  "question": "如何创建 DataWriter？",
  "answer": "…",
  "sources": [ …同上 SourceRef… ]
}
```

未命中：HTTP 404，`detail` 说明可能不存在或已超出缓存范围。

## 变更记录

| 版本 | 变更 |
|---|---|
| v0.1 | 骨架：/healthz、/query(SSE)、/sources 回查；mock/live 双模式 |

## 已知边界（后续版本）

- `/v1/chat/completions`（OpenAI 兼容门面）与 MCP 工具：第三周交付
- 回答的 Grounding/拒答行为：依赖 C 的 Prompt 实现，当前 mock 文本仅演示目标格式（结论/示例/注意事项/来源）
