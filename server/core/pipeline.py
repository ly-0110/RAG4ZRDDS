"""检索/生成的接入缝隙（seam）—— D 只定义协议并接线，不实现算法。

两个协议即两份会签草案：
  * Retriever   → 成员 B 落地（retrieval/ 包），输入问题返回引用片段
  * AnswerStream → 成员 C 落地（generation/ 包），基于引用片段产出答案增量

RAG_MODE=mock（默认）时使用本文件的确定性假实现：
  * 无需 A/B/C 的任何产物即可启动服务，供 E 的前端联调与周五冒烟
  * 同一问题永远返回相同结果，便于测试断言
RAG_MODE=live 加载 B 的真实检索（retrieval/，按 RAG_EXPERIMENT_CONFIG 定位索引）；
生成侧待成员 C 的 generation/ 包合入，当前以 PendingAnswerStream 给出可读缺口。
"""

from __future__ import annotations

import hashlib
from typing import AsyncIterator, Protocol

MOCK_ANSWER = """【Mock 模式回答】这是集成平台的确定性示例答案，用于前端联调与链路冒烟。

结论
使用 `create_datawriter()` 前需先创建 Publisher，再由其创建 DataWriter。

示例
```c
DDS_DataWriter writer = DDS_Publisher_create_datawriter(pub, topic, dw_qos, NULL, 0);
```

注意事项
- 本答案来自 mock 管线，不代表真实知识库内容。
- 切换 RAG_MODE=live 后将返回真实检索与生成结果。

来源
[1] 《ZRDDS用户手册》第 {page_print} 页 {section} 节"""


class Retriever(Protocol):
    """成员 B 实现此协议（retrieval/ 包）。"""

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        """返回至多 top_k 条引用 dict，字段同 schema.SourceRef。node_id 全局唯一。"""
        ...  # pragma: no cover


class AnswerStream(Protocol):
    """成员 C 实现此协议（generation/ 包）。"""

    def stream(self, question: str, chunks: list[dict]) -> AsyncIterator[str]:
        """基于检索结果异步产出答案文本增量。"""
        ...  # pragma: no cover


class MockRetriever:
    """确定性假检索：结果由问题的哈希决定，双页码演示 print = physical − 6。"""

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        digest = hashlib.md5(question.encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16)
        physical_page = 42 + seed % 90  # 物理页码落在 42~131
        results: list[dict] = []
        for i in range(max(1, top_k)):
            page = physical_page + i // 2
            results.append(
                {
                    "node_id": f"mock-{digest[:8]}-{i:02d}",
                    "source_id": "user_manual",
                    "source_name": "ZRDDS用户手册.pdf",
                    "section": f"9.{seed % 8 + 1}.{i + 1}",
                    "page_print": page - 6,
                    "page_physical": page,
                    "score": round(max(0.30, 0.95 - i * 0.07), 4),
                }
            )
        return results


class MockAnswerStream:
    """确定性假生成：把固定答案切成小块模拟流式输出。"""

    async def stream(self, question: str, chunks: list[dict]) -> AsyncIterator[str]:
        page_print = chunks[0]["page_print"] if chunks else 48
        section = chunks[0]["section"] if chunks else "9.1.1"
        text = MOCK_ANSWER.format(page_print=page_print, section=section)
        step = 24
        for i in range(0, len(text), step):
            yield text[i : i + step]


class Pipeline:
    """一条问答管线 = 一个检索器 + 一个生成流。D 负责组装，算法归 B/C。"""

    def __init__(self, retriever: Retriever, answer_stream: AnswerStream) -> None:
        self.retriever = retriever
        self.answer_stream = answer_stream


class PendingAnswerStream:
    """C 的 generation/ 包合入前的占位：检索引用照常下发，答案通道给可读缺口。"""

    async def stream(self, question: str, chunks: list[dict]) -> AsyncIterator[str]:
        raise RuntimeError(
            "生成实现尚未合入：等待成员 C 的 generation/ 包实现 AnswerStream 协议"
            f"（本次已下发 {len(chunks)} 条真实检索引用，见 sources 事件）"
        )
        yield ""  # pragma: no cover  # 使本函数成为 async generator


def build_pipeline(mode: str, experiment_config: str | None = None) -> Pipeline:
    """按 RAG_MODE 组装管线；接线问题一律给出可读错误而非静默降级。"""
    if mode == "mock":
        return Pipeline(MockRetriever(), MockAnswerStream())
    if mode == "live":
        # B 已交付 retrieval/；生成侧暂挂 PendingAnswerStream（C 第二周接入）
        from pathlib import Path

        from retrieval._bootstrap import experiment_config as ec
        from retrieval.retriever import build_retriever

        repo_root = Path(__file__).resolve().parents[2]
        cfg_path = repo_root / (experiment_config or "configs/experiments/struct_v1.yaml")
        if not cfg_path.exists():
            raise RuntimeError(
                f"RAG_MODE=live 启动失败：实验配置不存在 {cfg_path}"
                "（检查 RAG_EXPERIMENT_CONFIG）"
            )
        try:
            retriever = build_retriever(ec.load(cfg_path))
        except (FileNotFoundError, NotImplementedError) as e:
            raise RuntimeError(f"RAG_MODE=live 启动失败：{e}") from e
        _warmup_retriever(retriever)
        return Pipeline(retriever, PendingAnswerStream())
    raise RuntimeError(f"未知 RAG_MODE={mode!r}，可选值：mock | live")


def _warmup_retriever(retriever) -> None:
    """启动期一次性预热：触发 embedding 模型加载并跑通 Chroma 查询路径。

    bge-m3 权重冷加载需数~数十秒；不预热则该开销落在第一个真实请求上，
    且同步 CPU 推理会阻塞事件循环（期间 healthz 都无响应）。预热失败即拒绝
    启动——把接线/索引/模型问题暴露在启动阶段，而非首个用户请求。
    """
    import asyncio
    import time

    t0 = time.perf_counter()
    print("[server] live 模式预热：加载 embedding 模型（启动一次性）…", flush=True)
    try:
        asyncio.run(retriever.retrieve("warmup", top_k=1))
    except Exception as e:
        raise RuntimeError(
            f"RAG_MODE=live 预热失败，无法保证首问正常响应："
            f"{type(e).__name__}: {e}"
        ) from e
    print(f"[server] live 模式预热完成，耗时 {time.perf_counter() - t0:.1f}s", flush=True)
