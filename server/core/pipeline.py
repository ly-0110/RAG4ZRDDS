"""检索/生成的接入缝隙（seam）—— D 只定义协议并接线，不实现算法。

两个协议即两份会签草案：
  * Retriever   → 成员 B 落地（retrieval/ 包），输入问题返回引用片段
  * AnswerStream → 成员 C 落地（generation/ 包），基于引用片段产出答案增量

RAG_MODE=mock（默认）时使用本文件的确定性假实现：
  * 无需 A/B/C 的任何产物即可启动服务，供 E 的前端联调与周五冒烟
  * 同一问题永远返回相同结果，便于测试断言
RAG_MODE=live 加载 B 的真实检索（retrieval/，按 RAG_EXPERIMENT_CONFIG 定位索引）
与 C 的真实生成（generation/，LLM 配置来自 .env）。
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import OrderedDict
from pathlib import Path
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
        """基于检索结果异步产出答案文本增量。

        chunks 为富引用（含 text 正文与 SourceRef 字段），供组装 context；
        下发前端前由 query 层投影去掉 text（见 retrieval.retriever.to_source_refs）。
        """
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
                    "source_url": None,  # Mock 模式无原文 URL，Live 模式下由后端填充
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
    """一条问答管线 = 一个检索器 + 一个生成流。D 负责组装，算法归 B/C。

    `source_urls` 是 node_id → 原文 URL 的映射（HTML 来源有、PDF 来源为 None），
    只用于 `/sources/{rid}` 回查记录补 `source_url` 字段——`SourceRef` 七字段是
    与前端会签过的 wire 契约，扩字段须走会签（缺口 W1，docs/week4-delivery-review.md §2.3）。
    """

    def __init__(self, retriever: Retriever, answer_stream: AnswerStream,
                 source_urls: dict[str, str | None] | None = None,
                 node_details: dict[str, dict] | None = None,
                 kb_stats: dict | None = None,
                 source_roots: dict[str, Path] | None = None) -> None:
        self.retriever = retriever
        self.answer_stream = answer_stream
        self.source_urls = source_urls or {}
        # F1/F3（docs/week4-delivery-review.md §4.1）：kb_stats 供 /healthz 下发
        # 知识库统计（mock 为 None）；node_details 供 GET /nodes/{node_id} 按需
        # 回查单节点原文。chunk 原文只经 /nodes 端点出网，SSE wire 仍 7 字段。
        self.node_details = node_details or {}
        self.kb_stats = kb_stats
        # 本地文档根（source_id → 目录）：GET /documents/{source_id}/{file} 的
        # 读取白名单，来源是实验配置的 sources[].path（PDF 目录同样登记，但只有
        # HTML 来源会被前端当原文打开）。
        self.source_roots = source_roots or {}


def _as_int(value) -> int | None:
    """产物里的页字段可能是 int / 字符串数字 / 字符串 "None" / 空串——统一成 int|None。

    HTML 来源的 printed/physical 页字段在产物里是字面量 "None"（A 的 ingest 写入
    形态），直接当页码下发会让前端把"无页面概念"渲染成数字。
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def load_nodes_artifacts(nodes_file) -> tuple[dict[str, str | None], dict[str, dict], list[dict]]:
    """一次遍历实验 Node 产物，产出（回查 URL 表，节点详情表，来源统计）。

    文件缺失返回全空（mock 兼容、产物缺失不拒启动）；坏行与无 chunk_id 的
    记录跳过不中断（node_id ← chunk_id 映射已会签锁定）。
    """
    import json

    urls: dict[str, str | None] = {}
    details: dict[str, dict] = {}
    per_source: dict[str, dict] = {}
    if not nodes_file or not Path(nodes_file).exists():
        return urls, details, []
    with Path(nodes_file).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            meta = rec.get("metadata") or {}
            node_id = rec.get("chunk_id") or meta.get("chunk_id")
            if not node_id:
                continue
            url = rec.get("source_url") or meta.get("source_url")
            urls[node_id] = url
            sid = meta.get("source_id") or "unknown"
            agg = per_source.setdefault(sid, {"chunks": 0, "version": meta.get("version")})
            agg["chunks"] += 1
            if agg["version"] is None:
                agg["version"] = meta.get("version")
            # 页码字段名以 A 的 metadata 契约为准（printed/physical_page_start|end）；
            # HTML 来源在产物里写的是字符串 "None"，统一归一为 None。
            # 2026-09-16 修复：此前误用 SourceRef 的 page_print/page_physical 命名，
            # 导致"节点详情"里 PDF 的页码恒为空。
            details[node_id] = {
                "source_id": sid,
                "source_type": meta.get("source_type") or "pdf",
                "version": meta.get("version"),
                "title": meta.get("title"),
                "source_file": meta.get("source_file"),
                "section_path": meta.get("section_path"),
                "page_print": _as_int(meta.get("printed_page_start")),
                "page_print_end": _as_int(meta.get("printed_page_end")),
                "page_physical": _as_int(meta.get("physical_page_start")),
                "page_physical_end": _as_int(meta.get("physical_page_end")),
                "text": rec.get("text"),
                "source_url": url,
            }
    stats = [{"id": k, "version": v["version"], "chunks": v["chunks"]}
             for k, v in sorted(per_source.items())]
    return urls, details, stats


def _load_source_urls(nodes_file) -> dict[str, str | None]:
    """兼容入口：只要 URL 表（完整三产物见 load_nodes_artifacts）。"""
    return load_nodes_artifacts(nodes_file)[0]


def build_pipeline(mode: str, experiment_config: str | None = None) -> Pipeline:
    """按 RAG_MODE 组装管线；接线问题一律给出可读错误而非静默降级。"""
    if mode == "mock":
        return Pipeline(MockRetriever(), MockAnswerStream())
    if mode == "live":
        from generation.query_engine import build_answer_stream
        from retrieval._bootstrap import experiment_config as ec
        from retrieval.retriever import build_retriever

        # 直接调用（脚本/外部集成）不经过 server.main 的模块级 create_app，
        # 必须在此保证 .env 已导出，否则 generation 侧 os.getenv 读不到 LLM_*
        from server.core.settings import load_env_file
        load_env_file()

        repo_root = Path(__file__).resolve().parents[2]
        cfg_path = repo_root / (experiment_config or "configs/experiments/struct_v1.yaml")
        if not cfg_path.exists():
            raise RuntimeError(
                f"RAG_MODE=live 启动失败：实验配置不存在 {cfg_path}"
                "（检查 RAG_EXPERIMENT_CONFIG）"
            )
        cfg = ec.load(cfg_path)
        try:
            retriever = build_retriever(cfg)
        except (FileNotFoundError, NotImplementedError) as e:
            raise RuntimeError(f"RAG_MODE=live 启动失败：{e}") from e
        # 检索日志接线（docs/retrieval-log-schema.md，B/D 会签）：包装在 pipeline
        # 层，预热/脚本直调也入日志（request_id=null）；HTTP 路径由 query 层经
        # request_log_scope 注入关联 id。mock 模式不落盘（B 文档 §1 仅 live）。
        from server.core.request_log import JsonlLog, LoggedRetriever
        from server.core.settings import settings

        retriever = LoggedRetriever(
            retriever,
            JsonlLog(repo_root / settings.log_dir / "retrievals.jsonl"),
            experiment=cfg.experiment.name,
            config_hash8=ec.config_hash8(cfg),
            index_dirname=ec.index_dirname(cfg),
            mode=cfg.retrieval.mode,
            filters=cfg.retrieval.filters or None,
        )
        # 生成侧：读 .env 的 LLM 配置；缺失时在此拒绝启动（可读错误），
        # 而非等首个请求才报错（与 D 的"接线问题在启动期暴露"一致）。
        # 回答级日志接线（docs/answer-log-schema-draft.md，2026-09-17 会签定版）：
        # 与检索日志同层（HTTP 与 MCP 两条入口都覆盖），mock 模式不落盘。
        from server.core.request_log import JsonlLog, LoggedAnswerStream

        answer_stream = LoggedAnswerStream(
            build_answer_stream(cfg),
            JsonlLog(repo_root / settings.log_dir / "answers.jsonl"),
            experiment=cfg.experiment.name,
            config_hash8=ec.config_hash8(cfg),
            prompt_version=cfg.generation.prompt_version,
            model=os.getenv(f"{cfg.generation.llm_env_prefix}MODEL", "unknown"),
        )
        _warmup_retriever(retriever)
        # 单一装载入口：产物详情 + URL 本地化（产物里的 source_url 指向配置里的
        # 占位外部域名 docs.zrtechnology.com，实际不可达；改写成本服务的
        # /documents/{source_id}/{file}，文件从该来源配置的本地根目录读取）。
        source_urls, node_details, source_stats, source_roots = load_nodes_for_config(cfg, repo_root)
        localized = sum(1 for v in source_urls.values() if isinstance(v, str) and v.startswith("/documents/"))
        with_url = sum(1 for v in source_urls.values() if v)
        print(f"[server] 引用回查 URL 表：{len(source_urls)} 节点，其中 {with_url} 条带原文 URL"
              f"（{localized} 条已改写为本地文档地址 /documents/…；PDF 为 null）", flush=True)
        kb_stats = {
            "experiment": cfg.experiment.name,
            "retrieval_mode": cfg.retrieval.mode,
            "index_dirname": ec.index_dirname(cfg),
            "node_total": len(node_details),
            "sources": source_stats,
        }
        return Pipeline(retriever, answer_stream, source_urls,
                        node_details=node_details, kb_stats=kb_stats,
                        source_roots=source_roots)
    raise RuntimeError(f"未知 RAG_MODE={mode!r}，可选值：mock | live")


def _attr(obj, key):
    """配置项取字段：sources 元素是 SourceCfg 对象，测试夹具可能是 dict。"""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _resolve_source_roots(repo_root: Path, sources) -> dict[str, Path]:
    """实验配置的 sources[] → {source_id: 本地文档根目录}（只登记存在的目录）。

    PDF 来源的 path 指向文件本身（不是目录），故按目录过滤——本地文档服务只
    服务 HTML 快照这类目录型来源。**sources 元素是 SourceCfg 对象而非 dict**
    （2026-09-16 实测踩过：按 isinstance(dict) 过滤会把他们全跳过，URL 本地化
    静默失效）。
    """
    roots: dict[str, Path] = {}
    for src in sources:
        sid, path = _attr(src, "id"), _attr(src, "path")
        if not sid or not path:
            continue
        root = (repo_root / str(path)).resolve()
        if root.is_dir():
            roots[str(sid)] = root
    return roots


def load_nodes_for_config(cfg, repo_root: Path) -> tuple[dict, dict, list, dict]:
    """按实验配置装载 Node 产物（详情表 + URL 表 + 来源统计 + 本地文档根）。

    **单一装载入口**：启动期管线与 NodeDetailIndex 的按需装载都走这里，避免
    两条路径行为不一致——2026-09-16 实测踩过：按需装载绕过了 URL 本地化，
    切实验后"打开原文"又退回不可达的外部占位域名。
    """
    from retrieval._bootstrap import experiment_config as ec

    urls, details, stats = load_nodes_artifacts(ec.nodes_path(cfg))
    roots = _resolve_source_roots(repo_root, getattr(cfg, "sources", None) or [])
    _localize_doc_urls(urls, details, roots)
    return urls, details, stats, roots


def _localize_doc_urls(urls: dict[str, str | None],
                       details: dict[str, dict],
                       roots: dict[str, Path]) -> int:
    """把外部文档地址改写成本服务的本地地址，返回改写条数。

    文件名取产物 metadata 的 `source_file`（干净的文件名），缺失时退化为 URL
    末段；只有当该文件确实存在于来源根目录下才改写——不存在就保留原值，
    避免把"打不开"换成"404"。
    """
    if not roots:
        return 0
    changed = 0
    for node_id, url in list(urls.items()):
        rec = details.get(node_id) or {}
        sid = rec.get("source_id")
        root = roots.get(sid) if sid else None
        if root is None:
            continue
        filename = rec.get("source_file")
        if not filename and isinstance(url, str) and url:
            filename = url.rstrip("/").rsplit("/", 1)[-1]
        if not filename:
            continue
        try:
            target = (root / str(filename)).resolve()
        except OSError:
            continue
        if not target.is_file() or root not in target.parents:
            continue
        local = f"/documents/{sid}/{target.name}"
        urls[node_id] = local
        if node_id in details:
            details[node_id]["source_url"] = local
        changed += 1
    return changed


def available_source_roots(repo_root: Path | None = None) -> dict[str, Path]:
    """全局本地文档目录注册表：跨所有实验配置合并 {source_id: 目录}。

    单个实验的 sources 未必覆盖全部来源（如默认 struct_v1 只有 PDF 手册），
    而"打开原文"链接可能来自任意实验产生的引用（如多来源实验的 HTML 节点）。
    因此端点用的是全实验合并的白名单，而不是当前管线的 sources——否则切实验
    后链接就会 404（2026-09-16 实测踩过）。
    """
    from retrieval._bootstrap import experiment_config as ec

    root = (repo_root or Path(__file__).resolve().parents[2]) / "configs" / "experiments"
    roots: dict[str, Path] = {}
    for name in available_experiments():
        try:
            cfg = ec.load(root / f"{name}.yaml")
        except Exception:
            continue
        for sid, path in _resolve_source_roots(root.parents[1], getattr(cfg, "sources", None) or []).items():
            roots.setdefault(sid, path)
    return roots


def experiment_modes() -> dict[str, str]:
    """实验 ID → 检索模式（供 /healthz 下发；前端据此决定相关度指标怎么显示）。

    vector/hybrid_rerank 的分数量纲自带可比性（cosine / sigmoid 0~1），
    bm25（原始词面分 7~56）与 hybrid（RRF ~0.03）跨查询不可比——前端不能把
    它们当"相关度百分比"渲染。读不到的配置跳过（模板/未完成配置不影响服务）。
    """
    from retrieval._bootstrap import experiment_config as ec

    root = Path(__file__).resolve().parents[2] / "configs" / "experiments"
    modes: dict[str, str] = {}
    for name in available_experiments():
        try:
            cfg = ec.load(root / f"{name}.yaml")
            modes[name] = str(cfg.retrieval.mode)
        except Exception:
            continue
    return modes


def _warmup_retriever(retriever) -> None:
    """启动期一次性预热：触发 embedding 模型加载并跑通 Chroma 查询路径。

    bge-m3 权重冷加载需数~数十秒；不预热则该开销落在第一个真实请求上，
    且同步 CPU 推理会阻塞事件循环（期间 healthz 都无响应）。预热失败即拒绝
    启动——把接线/索引/模型问题暴露在启动阶段，而非首个用户请求。
    """
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


def available_experiments() -> list[str]:
    """configs/experiments/ 下已注册实验 ID（yaml 文件名 stem，文件名即实验 ID）。

    F4 /query experiment 参数的白名单单一事实源，也随 /healthz 下发供前端做
    选择器；按文件系统现状即时计算，新增实验配置无需重启服务。
    """
    root = Path(__file__).resolve().parents[2] / "configs" / "experiments"
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.glob("*.yaml"))


class NodeDetailIndex:
    """跨实验的节点详情按需索引（F3 × F4 整合修复，2026-09-16）。

    启动期只装载**默认实验**的 Node 详情表；前端经 F4 切到其它实验后拿到的
    node_id 不在这张表里，`/nodes/{node_id}` 就会 404——两个同批交付的功能
    各自可用、合起来不可用（本机实测复现）。

    本索引在缓存未命中时按需解析其余实验的 Node 产物并缓存：纯 JSONL 解析
    （无 embedding / 模型加载，1606 节点约亚秒级），因此懒装载代价可接受；
    失败的配置记入 `failures` 避免每次请求重试。表数上限 `max_tables`，超出
    时逐出最久未用的非默认实验表，避免多实验把内存撑大。
    """

    def __init__(self, default_key: str, default_details: dict[str, dict],
                 experiments: list[str] | None = None, max_tables: int = 3) -> None:
        self._default_key = default_key
        self._max_tables = max(2, max_tables)
        self._tables: OrderedDict[str, dict[str, dict]] = OrderedDict(
            [(default_key, default_details)]
        )
        self._order = [k for k in (experiments or []) if k != default_key]
        self._failures: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def loaded_experiments(self) -> list[str]:
        return list(self._tables)

    def lookup(self, node_id: str) -> tuple[str, dict] | None:
        """返回 (实验 ID, 节点记录)；未在任何实验产物中找到返回 None。"""
        with self._lock:
            for key, table in self._tables.items():
                rec = table.get(node_id)
                if rec is not None:
                    self._tables.move_to_end(key)
                    return key, rec
            for key in self._order:
                if key in self._tables or key in self._failures:
                    continue
                try:
                    table = self._load(key)
                except Exception as exc:  # 装载失败只记不抛：不能连累其它实验回查
                    self._failures[key] = f"{type(exc).__name__}: {exc}"
                    continue
                if table is None:
                    continue
                self._tables[key] = table
                self._evict()
                rec = table.get(node_id)
                if rec is not None:
                    return key, rec
        return None

    def _load(self, key: str) -> dict[str, dict] | None:
        try:
            from retrieval._bootstrap import experiment_config as ec

            repo_root = Path(__file__).resolve().parents[2]
            cfg = ec.load(repo_root / "configs" / "experiments" / f"{key}.yaml")
            # 与启动期同一装载入口：URL 本地化也在这里生效（否则切实验后
            # "打开原文"会退回不可达的外部占位域名——2026-09-16 实测踩过）
            _, details, _, _ = load_nodes_for_config(cfg, repo_root)
        except Exception as exc:  # 坏配置/产物缺失不阻断其它实验的回查
            self._failures[key] = f"{type(exc).__name__}: {exc}"
            return None
        return details

    def _evict(self) -> None:
        while len(self._tables) > self._max_tables:
            evictable = next((k for k in self._tables if k != self._default_key), None)
            if evictable is None:
                return
            self._tables.pop(evictable)


class PipelineRegistry:
    """F4：live 模式按实验 ID 懒组装并缓存 Pipeline（LRU，默认管线钉住不逐出）。

    组装（模型加载 + 预热，数秒~数十秒）在 worker 线程执行，事件循环保持
    响应；并发同键请求经 asyncio.Lock 合并为一次组装。max_size 为缓存管线
    总数上限（含默认，最小 2）——每个 live 管线各持一份 embedding/索引内存，
    演示机按 32GB 内存保守取值；逐出时尽力调检索器 close() 释放句柄。
    """

    def __init__(self, default_key: str, default_pipeline: Pipeline,
                 max_size: int = 3) -> None:
        self._default_key = default_key
        self._max_size = max(2, max_size)
        self._items: OrderedDict[str, Pipeline] = OrderedDict()
        self._items[default_key] = default_pipeline
        self._lock = asyncio.Lock()

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def get(self, key: str) -> Pipeline | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: str, pipeline: Pipeline) -> None:
        self._items[key] = pipeline
        self._items.move_to_end(key)
        while len(self._items) > self._max_size:
            evictable = next((k for k in self._items if k != self._default_key), None)
            if evictable is None:
                return
            old = self._items.pop(evictable)
            closer = getattr(old.retriever, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass  # 逐出尽力而为，清理失败不影响服务

    async def get_or_build(self, key: str, config_relpath: str) -> Pipeline:
        hit = self.get(key)
        if hit is not None:
            return hit
        async with self._lock:
            hit = self.get(key)
            if hit is not None:
                return hit
            pipeline = await asyncio.to_thread(build_pipeline, "live", config_relpath)
            self.put(key, pipeline)
            return pipeline
