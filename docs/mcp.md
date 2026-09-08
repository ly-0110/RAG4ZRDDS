# MCP Server（指南 §7 任务 2 · 成员 D · v0.1）

把知识库问答以 MCP（Model Context Protocol）工具暴露给 IDE/Agent 客户端——
"前端三路线"中的 MCP 封装路线打底，与自研页（E）和 REST/SSE（`POST /query`）并行。

## 工具

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `query_knowledge_base` | `question`（必填）、`top_k`（0=服务默认） | `{request_id, answer, sources[], error?}` | `sources` 为 SourceRef 7 字段（node_id/source_id/source_name/section/page_print/page_physical/score），无正文泄漏；生成失败时 `answer=null` + 可读 `error`，已取得的引用不丢 |
| `get_sources` | `request_id` | `{question, answer, sources[]}` | 引用回查，与 HTTP `GET /sources/{rid}` 同源（`{LOG_DIR}/sources.jsonl` 持久化） |

## 启动与接入

```bash
make mcp                        # = python -m server.mcp_server（RAG_MODE 默认 mock）
RAG_MODE=live make mcp          # 真实检索+生成（需先 make index；启动期预热与 HTTP 服务同款）
```

客户端（Claude Desktop / IDE MCP 配置）：

```json
{
  "mcpServers": {
    "zrdds-kb": {
      "command": "python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "<仓库根>"
    }
  }
}
```

环境变量透传 `RAG_MODE` / `RAG_EXPERIMENT_CONFIG` / `LLM_*`（live 生成侧需要）。

## 与 HTTP 通路的共享约定

- **同一套装配**：`build_pipeline`（mock/live 一处切换）+ `PersistentSourcesStore`；
  mock 不落盘检索日志，live 落 `retrievals.jsonl`（B/D 会签文档）。
- **request_id 空间**：MCP 侧前缀 `mcp-`（12 hex），HTTP 侧为纯 12 hex——
  日志关联与 `/sources` 回查互不混淆。
- **X3 语义一致**：引用一经取得即持久化（answer 暂 null），生成完成后二次覆盖。

## 实现与测试

- `server/mcp_server.py`：工具实现层（`*_impl`）与 MCP 协议层（`@mcp.tool()`）解耦，
  便于单测直接驱动实现层；SDK 用官方 `mcp==2.2.0`（v2 起 FastMCP 更名 `MCPServer`，
  stdio 为默认传输）。
- 单测 `tests/unit/server/test_mcp_server.py` 6 例：工具注册、返回契约、空白拒绝、
  X3（生成失败引用可回查）、未知 id 可读错误、retrievals.jsonl 的 mcp-rid 关联。
- 端到端 stdio 冒烟：`python scripts/smoke_mcp.py`（正式验证入口，退出码 0 = 通过；
  起子进程走完整协议：initialize → list_tools → 两工具调用 → 引用回查）。

## 开放项

- live 生成侧依赖 C 的 `generation/`（已合入）；`generation.enabled` 配置语义待与 C 定（议题同 week2）。
- E 若确认切 MCP 封装路线，再评估资源类封装（如把 section_tree 暴露为资源）——当前仅两个工具打底。
