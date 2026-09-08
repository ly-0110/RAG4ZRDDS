#!/usr/bin/env python3
"""scripts/smoke_mcp.py — MCP Server stdio 端到端冒烟（完整协议链路）。

以子进程启动 `python -m server.mcp_server`（强制 RAG_MODE=mock，不依赖索引与 LLM），
经官方 SDK 客户端走 stdio 协议：initialize → list_tools → call_tool ×2。
验收 docs/mcp.md 的两个工具在真实协议下可用。

用法: python scripts/smoke_mcp.py     # 退出码 0 = 通过
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


async def _run() -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.mcp_server"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "RAG_MODE": "mock", "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"query_knowledge_base", "get_sources"} <= names, names
            print(f"[smoke] list_tools ✓: {sorted(names)}")

            q = "如何创建 DataWriter？需要哪些前置实体？"
            res = await session.call_tool(
                "query_knowledge_base",
                {"question": q, "top_k": 2},
            )
            payload = getattr(res, "structuredContent", None) or json.loads(
                res.content[0].text
            )
            rid = payload["request_id"]
            assert rid.startswith("mcp-"), payload
            assert payload["answer"].strip(), payload
            assert 1 <= len(payload["sources"]) <= 2, payload
            src = payload["sources"][0]
            assert src["page_physical"] - src["page_print"] == 6, src
            print(f"[smoke] query_knowledge_base ✓: rid={rid}, "
                  f"{len(payload['sources'])} 条引用, "
                  f"答案 {len(payload['answer'])} 字符")

            res2 = await session.call_tool("get_sources", {"request_id": rid})
            payload2 = getattr(res2, "structuredContent", None) or json.loads(
                res2.content[0].text
            )
            assert payload2["answer"] == payload["answer"], payload2
            assert payload2["sources"] == payload["sources"], payload2
            print("[smoke] get_sources ✓: 引用回查一致")

    print("[smoke] ✓ MCP stdio 端到端通过")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(_run()))
