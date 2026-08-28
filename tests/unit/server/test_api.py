"""server 骨架冒烟测试：httpx ASGI 直连应用，不占端口、不依赖外部服务。

覆盖四类行为：
  1. /healthz 存活检查
  2. /query SSE 事件序列与双页码约定
  3. 空白问题的可读 400 错误
  4. 检索器故障 → SSE error 事件（而非静默断流）
附带验证 /sources/{request_id} 回查。

说明：用例刻意只使用纯函数 + assert（不依赖 pytest 特性），因此既可由
`python -m pytest` 执行，也可在无 pytest 的机器上用简易运行器跑。
"""

from __future__ import annotations

import asyncio
import json

import httpx

from server.core.settings import Settings
from server.main import create_app


def _mock_settings() -> Settings:
    s = Settings()
    s.rag_mode = "mock"
    return s


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """把完整 SSE 文本解析为 [(event, data_json), ...]，保持顺序。"""
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        events.append((name, data))
    return events


def test_healthz():
    async def go():
        async with _client(create_app(_mock_settings())) as c:
            r = await c.get("/healthz")
        return r

    r = asyncio.run(go())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"
    assert r.headers.get("x-request-id")


def test_query_sse_flow_and_dual_page_numbers():
    async def go():
        async with _client(create_app(_mock_settings())) as c:
            return await c.post("/query", json={"question": "如何创建 DataWriter？", "top_k": 3})

    r = asyncio.run(go())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    names = [name for name, _ in events]
    # 序列：sources 先于全部 token，最后是 done，且中途没有 error
    assert names[0] == "sources"
    assert names[-1] == "done"
    assert "error" not in names
    assert set(names[1:-1]) == {"token"}

    _, sources_ev = events[0]
    _, done_ev = events[-1]
    rid = sources_ev["request_id"]
    assert rid == done_ev["request_id"] == r.headers["x-request-id"]

    sources = sources_ev["sources"]
    assert len(sources) == 3
    for s in sources:  # 双页码约定：印刷页码 = 物理页码 + 7（2026-08-28 会签定值）
        assert s["page_print"] == s["page_physical"] + 7
        assert s["node_id"] and s["source_name"]

    token_text = "".join(data["text"] for n, data in events if n == "token")
    assert done_ev["answer"] == token_text
    assert done_ev["sources"] == sources


def test_blank_question_returns_readable_400():
    async def go():
        async with _client(create_app(_mock_settings())) as c:
            return await c.post("/query", json={"question": "   \n\t "})

    r = asyncio.run(go())
    assert r.status_code == 400
    assert "空白" in r.json()["error"]
    assert r.json()["request_id"]


def test_gbk_encoded_body_gets_readable_hint():
    """中文 Windows 终端按 GBK 发送请求体时的真实故障形态：必须给出可读修复指引。"""

    async def go():
        async with _client(create_app(_mock_settings())) as c:
            return await c.post(
                "/query",
                content='{"question": "如何创建 DataWriter？"}'.encode("gbk"),
                headers={"Content-Type": "application/json"},
            )

    r = asyncio.run(go())
    assert r.status_code == 400
    body = r.json()
    assert "UTF-8" in body["error"]          # 明确指出编码问题
    assert "chcp 65001" in body["error"]     # 给出可执行的解法
    assert body["request_id"]


def test_error_becomes_sse_error_event_not_silent_drop():
    class BoomRetriever:
        async def retrieve(self, question: str, top_k: int) -> list[dict]:
            raise RuntimeError("检索器故障（测试注入）")

    app = create_app(_mock_settings())
    app.state.pipeline.retriever = BoomRetriever()

    async def go():
        async with _client(app) as c:
            return await c.post("/query", json={"question": "E1003 是什么错误码？"})

    r = asyncio.run(go())
    assert r.status_code == 200  # 流已开始，HTTP 层无法回头
    events = _parse_sse(r.text)
    names = [name for name, _ in events]
    # 检索第一步就失败：不应有 sources/token/done，必须有一个携带原因的 error
    assert names == ["error"]
    errors = [data for n, data in events if n == "error"]
    assert len(errors) == 1
    assert "检索器故障" in errors[0]["error"]
    assert errors[0]["request_id"]


def test_sources_lookup_roundtrip_and_404():
    async def go():
        async with _client(create_app(_mock_settings())) as c:
            r = await c.post("/query", json={"question": "QoS 配置方法"})
            done = [d for n, d in _parse_sse(r.text) if n == "done"][0]

            ok = await c.get(f"/sources/{done['request_id']}")
            missing = await c.get("/sources/nonexistent123")
        return done, ok, missing

    done, ok, missing = asyncio.run(go())
    assert ok.status_code == 200
    body = ok.json()
    assert body["request_id"] == done["request_id"]
    assert body["answer"] == done["answer"]
    assert body["sources"] == done["sources"]
    assert missing.status_code == 404
