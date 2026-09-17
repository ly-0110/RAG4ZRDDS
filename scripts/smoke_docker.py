#!/usr/bin/env python3
"""scripts/smoke_docker.py — 容器形态端到端冒烟（经前端容器 nginx 走真实链路）。

容器形态与 make 链路只是"怎么起"不同，对外契约不变；所以本脚本只从**容器暴露的入口**
发请求，覆盖容器栈特有的三类风险：

  ① nginx 静态托管：Vite 构建产物可访问（dist 未挂载/构建失败会立刻暴露）
  ② nginx 反代：/healthz、/sources 等非流式路径可通
  ③ SSE 经反代的流式下发：/query 必须逐事件到达（proxy_buffering 没关会把 token 攒成
     一坨再下发，前端的打字机效果与"停止生成"都会失效）——脚本用到达时间戳判定增量性

顺带核对真值：10.7 DurabilityQosPolicy 的引用页码应为印刷 127 / 物理 133
（2026-08-29 以 PDF 页眉印刷数字定的地面真值，双页码差恒 6）。

用法: python scripts/smoke_docker.py [--base http://127.0.0.1:5173] [--question TEXT]
前置: make docker-serve（或 docker compose up -d --build）
退出码 0 = 全部通过。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:5173"
DEFAULT_QUESTION = "DurabilityQosPolicy 的 kind 字段默认值是什么？"
TRUTH_PAGE_PRINT = 127
TRUTH_PAGE_PHYSICAL = 133

# 下发契约：SourceRef 7 字段 + v0.16 起随 sources 事件一并下发的第 8 字段 source_url
WIRE_FIELDS = (
    "node_id",
    "source_id",
    "source_name",
    "section",
    "page_print",
    "page_physical",
    "score",
    "source_url",
)

_failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[smoke] {'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)
    return ok


def _get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def sse_query(url: str, question: str, top_k: int = 5, timeout: float = 600.0):
    """发一次 /query，按 SSE 帧解析。返回 [(event, payload, 到达时刻), ...]。"""
    body = json.dumps({"question": question, "top_k": top_k}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/query",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    events: list[tuple[str, dict, float]] = []
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        event = ""
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                events.append((event, payload, time.monotonic() - started))
    return events


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG4ZRDDS 容器形态冒烟")
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"容器入口地址（默认 {DEFAULT_BASE}）")
    ap.add_argument("--question", default=DEFAULT_QUESTION, help="提问内容")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    print(f"[smoke] 入口 {base}")

    # ---- ① 前端静态产物 ----
    try:
        status, html = _get(f"{base}/")
    except urllib.error.URLError as exc:
        print(f"[smoke] 无法连接 {base}：{exc}")
        print("[smoke] 先起容器栈：make docker-serve")
        return 2
    check("前端首页可访问（nginx 托管 Vite 产物）",
          status == 200 and 'id="app"' in html, f"HTTP {status}, {len(html)} 字节")

    # ---- ② nginx 反代 ----
    status, raw = _get(f"{base}/healthz")
    health = json.loads(raw)
    check("nginx 反代 /healthz 通", status == 200 and health.get("status") == "ok",
          f"HTTP {status}, status={health.get('status')}, mode={health.get('mode')}")
    experiments = health.get("experiments") or []
    check("实验白名单非空（F4 选择器数据源）", bool(experiments), f"{len(experiments)} 个实验")
    kb = health.get("kb")
    if health.get("mode") == "live":
        check("live 模式已装载知识库产物（kb.node_total>0）",
              bool(kb) and (kb.get("node_total") or 0) > 0,
              f"experiment={kb.get('experiment') if kb else None}, "
              f"node_total={kb.get('node_total') if kb else None}, "
              f"index={kb.get('index_dirname') if kb else None}")
    else:
        print(f"[smoke] 当前为 mock 模式（kb=None）；真实检索/生成的核对项将跳过")

    # ---- ③ SSE 流式问答经反代 ----
    events = sse_query(base, args.question, args.top_k)
    kinds = [e for e, _, _ in events]
    check("SSE 首帧是 sources（evidence-first）", bool(kinds) and kinds[0] == "sources", f"event 序列={kinds[:3]}…")

    sources: list[dict] = []
    rid = ""
    for event, payload, _ in events:
        if event == "sources":
            sources = payload.get("sources") or []
            rid = payload.get("request_id") or ""

    check("sources 非空", bool(sources), f"{len(sources)} 条引用")
    if sources:
        top = sources[0]
        check("首条引用含 8 字段 wire 契约",
              all(k in top for k in WIRE_FIELDS),
              f"缺字段={[k for k in WIRE_FIELDS if k not in top] or '无'}")
        check("每条引用不含正文 text（正文不下发）",
              all("text" not in s for s in sources))
        bad = [
            s for s in sources
            if s.get("page_print") is not None and s.get("page_physical") is not None
            and s["page_physical"] - s["page_print"] != 6
        ]
        check("PDF 双页码差恒 6（印刷页 = 物理页 − 6）", not bad,
              f"越界 {len(bad)} 条")
        top_page = top.get("page_print")
        check(f"真值核对：top-1 印刷页 == {TRUTH_PAGE_PRINT}（10.7 DurabilityQosPolicy）",
              top_page == TRUTH_PAGE_PRINT,
              f"实际 {top_page}（物理 {top.get('page_physical')}）"
              + ("" if top_page == TRUTH_PAGE_PRINT else "；若换了 --question 请忽略本项"))

    error_events = [p.get("error") for e, p, _ in events if e == "error"]
    token_times = [t for e, _, t in events if e == "token"]
    done = next((p for e, p, _ in events if e == "done"), None)

    if error_events:
        check("SSE 全流程无 error 事件", False, f"error={error_events[0]}")
        if any(k in str(error_events[0]) for k in ("Connection error", "APIConnectionError", "ConnectError")):
            print(
                "[smoke] 提示：连接类错误通常来自 LLM 后端不可达。容器里的 127.0.0.1 指容器自身——\n"
                "        用本地 Ollama / 网关时，.env 的 LLM_BASE_URL 要写 "
                "http://host.docker.internal:11500/v1；\n"
                "        用云端 API 时检查 .env 的 LLM_BASE_URL / LLM_API_KEY 与容器网络。\n"
                "        检索侧与容器栈本身已通过（上方 sources 各项即证据），此失败不影响引用溯源。"
            )
    else:
        check("SSE 全流程无 error 事件", True)

    check("流式出词（token 事件 > 0）", bool(token_times), f"{len(token_times)} 个 token 事件")
    if done is not None:
        answer = done.get("answer") or ""
        check("done 事件带非空答案", bool(answer.strip()), f"{len(answer)} 字符")

    # 增量性判定：若 nginx 攒缓冲，所有 token 的到达时刻会挤在末尾同一瞬间。
    if token_times and done is not None:
        total = max(t for e, _, t in events if e == "done")
        first = token_times[0]
        spread = total - first
        check("SSE 增量下发（未被 nginx 缓冲）", spread > 0.5,
              f"首 token {first:.2f}s → 结束 {total:.2f}s，跨度 {spread:.2f}s")

    # ---- 引用回查 ----
    if rid:
        status, raw = _get(f"{base}/sources/{rid}")
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            record = {}
        check("引用可回查 /sources/{rid}", status == 200 and bool(record.get("sources")),
              f"HTTP {status}, question={record.get('question')!r}")

    print()
    if _failures:
        print(f"[smoke] 未通过 {len(_failures)} 项：{_failures}")
        return 1
    print("[smoke] 全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
