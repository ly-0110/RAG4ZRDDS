# 第四周 B 检索实施计划：Hybrid+Reranker 通路 + Version-aware 加权 + 四组对比实验

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地指南 §8 成员 B 两项任务——Hybrid+Reranker 检索通路（第四组对比实验）与 Version-aware 版本加权，产出四组对比证据链并写入 `docs/evaluation.md`。

**Architecture:** 精排为独立通路类 `HybridRerankRetriever`（内部组合 RRF 融合 + CrossEncoder 精排，走原始 hit 通路以保住 metadata）；版本加权为纯函数 `apply_version_boost`（候选池 min-max 归一 + 加成），四种检索模式统一接线；两者均不新增 schema 字段、不建新索引（引用制）。

**Tech Stack:** Python 3 / sentence-transformers 6.0（CrossEncoder）/ chroma 1.5.9 / rank_bm25 / pydantic / pytest

**Spec:** `docs/superpowers/specs/2026-09-14-week4-retrieval-design.md`

## Global Constraints

- 所有 Python 命令用 `.venv/Scripts/python`（全局 python 无 pytest 等依赖）。
- 测试前台运行，勿后台执行（历史事故：后台执行计时异常，473s vs 实际 1.63s）。
- 每次 `git commit` 必须带身份参数（本机无全局 git identity）：
  `git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "..."`
- 模型下载**勿设 HF_ENDPOINT**（本机走 hf-mirror 拉文件必失败，直连 huggingface.co）。
- 多来源配置维持 `expected_sources: null`（宁缺毋滥协议：循环论证标注不产指标）。
- 不新增 schema 固定字段：新参数只进 `retrieval.params`（Owner 自由区）。
- 实现分支：从 develop 切 `feature/week4-hybrid-rerank`；设计文档在 `docs/week4-retrieval-design`（PR#34，互不依赖）。
- 提交信息用中文、前缀风格与既有仓库一致（feat/fix/docs/test/exp）。

---

### Task 1: 模型解析公共化 + 精排工厂 `retrieval/rerank.py`

**Files:**
- Modify: `retrieval/embeddings.py`（`_resolve_model` → `resolve_model` 公共化；别名表增补）
- Create: `retrieval/rerank.py`
- Test: `tests/unit/test_rerank.py`（新建）；`tests/unit/test_retrieval.py`（更新 3 处旧函数名引用）

**Interfaces:**
- Consumes: `retrieval.embeddings.MODEL_DIR`（已存在，模块级）。
- Produces: `embeddings.resolve_model(name: str) -> str`；`rerank.build_reranker(cfg) -> Callable[[str, list[str]], list[float]]`（Task 3/8 消费）。

- [ ] **Step 1: 建分支并把本计划入库**（计划文件此前未跟踪，切分支后仍在工作区）

```bash
cd "C:/Users/huziy/Desktop/软工实训/RAG4ZRDDS"
git checkout develop && git checkout -b feature/week4-hybrid-rerank
git add docs/superpowers/plans/2026-09-14-week4-hybrid-rerank.md
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "docs(plan): 第四周 B 实施计划（Hybrid+Reranker + Version-aware）"
```

> 注：本计划刻意与设计文档分支分离——照第三周惯例，计划随实现 PR 走（设计 PR#34 只含设计，计划在其合入前后都无冲突：同内容文件）。

- [ ] **Step 2: 写失败测试 `tests/unit/test_rerank.py`**

```python
"""精排工厂（rerank.py）与精排通路（HybridRerankRetriever）单元测试。

工厂用假 CrossEncoder 替换（monkeypatch 模块属性——rerank.py 内的
`from sentence_transformers import CrossEncoder` 在调用时解析属性，可被拦截），
不加载真模型。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from retrieval.rerank import build_reranker


class FakeCrossEncoder:
    """替身：分数 = 文本长度，构造可预期的排序。"""

    init_calls = 0
    init_args: tuple = ()

    def __init__(self, model_name, device=None):
        type(self).init_calls += 1
        FakeCrossEncoder.init_args = (model_name, device)

    def predict(self, pairs):
        return [float(len(t)) for _, t in pairs]


def test_build_reranker_is_lazy_and_resolves_local_model(tmp_path, monkeypatch):
    import sentence_transformers
    from retrieval import embeddings

    monkeypatch.setattr(embeddings, "MODEL_DIR", tmp_path)
    (tmp_path / "bge-reranker-v2-m3").mkdir()
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeCrossEncoder)
    FakeCrossEncoder.init_calls = 0

    cfg = SimpleNamespace(
        retrieval=SimpleNamespace(rerank_model="bge-reranker-v2-m3"),
        embedding=SimpleNamespace(device="cpu"),
    )
    rerank_fn = build_reranker(cfg)
    assert callable(rerank_fn)
    assert FakeCrossEncoder.init_calls == 0          # 构造阶段不加载模型

    scores = rerank_fn("查询", ["ab", "abcd"])
    assert scores == [2.0, 4.0]
    assert FakeCrossEncoder.init_args == (str(tmp_path / "bge-reranker-v2-m3"), "cpu")

    rerank_fn("查询", ["x"])
    assert FakeCrossEncoder.init_calls == 1          # 懒加载只发生一次
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_rerank.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.rerank'`

- [ ] **Step 4: 实现 `retrieval/rerank.py`**

```python
"""精排模型工厂：实验配置 → 交叉编码器打分函数。

与 embeddings.py 同款约定：懒加载、models/ 本地目录优先、否则按 HF 别名
拉取（本机直连 huggingface.co，勿设 HF_ENDPOINT——hf-mirror 拉文件必失败）。

rerank_fn(question, texts) -> list[float] 为交叉编码器原始分，与 cosine /
BM25 / RRF 量纲均不可比——任何 score 阈值必须按 retrieval.mode 分别定标。
"""
from __future__ import annotations

from collections.abc import Callable

from retrieval.embeddings import resolve_model


def build_reranker(cfg) -> Callable[[str, list[str]], list[float]]:
    """懒加载 CrossEncoder；返回 (question, texts) -> scores 闭包。"""
    _model = None
    model_name = cfg.retrieval.rerank_model

    def rerank(question: str, texts: list[str]) -> list[float]:
        nonlocal _model
        if _model is None:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(resolve_model(model_name), device=cfg.embedding.device)
        return [float(s) for s in _model.predict([(question, t) for t in texts])]

    return rerank
```

- [ ] **Step 5: 改 `retrieval/embeddings.py`**

三处小改：

```python
HF_REPO_ALIASES = {
    "bge-m3": "BAAI/bge-m3",
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}


def resolve_model(name: str) -> str:      # 原 _resolve_model，公共化供 rerank.py 复用
    local = MODEL_DIR / name
    if local.exists():
        return str(local)
    return HF_REPO_ALIASES.get(name, name)
```

并把 `build_embedding` 内的调用改为 `model_name=resolve_model(cfg.embedding.model)`。

再更新 `tests/unit/test_retrieval.py` 三处旧名引用（grep `_resolve_model` 定位：约 240/241 行、249 行、572/573 行），全部改为 `embeddings.resolve_model`。

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_rerank.py tests/unit/test_retrieval.py -v`
Expected: 全部 PASS（test_retrieval 中 3 个 resolve_model 测试在新名下通过）

- [ ] **Step 7: 提交**

```bash
git add retrieval/rerank.py retrieval/embeddings.py tests/unit/test_rerank.py tests/unit/test_retrieval.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): 精排工厂 rerank.py + 模型解析公共化（第四周 §8.2）"
```

---

### Task 2: `HybridRerankRetriever` 精排通路类

**Files:**
- Modify: `retrieval/retriever.py`（新增类，置于 `HybridRetriever` 之后；顶部增 `from collections.abc import Callable`）
- Test: `tests/unit/test_rerank.py`（追加）

**Interfaces:**
- Consumes: `fuse_hits`（已有）、`_to_source_ref`（已有）、Task 1 的 `rerank_fn` 类型约定。
- Produces: `HybridRerankRetriever(vector_store, bm25_store, rerank_fn, rrf_k=DEFAULT_RRF_K, candidate_top_k=30, filters=None)`（Task 3/5 消费）。

- [ ] **Step 1: 写失败测试（追加到 `tests/unit/test_rerank.py`）**

```python
class FakeStore:
    """记录调用参数的假 store；返回原始 hit（含 metadata）。"""

    def __init__(self, hits: list[dict]):
        self.hits = hits
        self.calls: list[tuple] = []

    def query(self, question, top_k, filters=None):
        self.calls.append((question, top_k, filters))
        return [dict(h) for h in self.hits[:top_k]]


def _raw_hit(node_id: str, text: str, version: str = "2.0", score: float = 0.5) -> dict:
    return {
        "node_id": node_id,
        "text": text,
        "metadata": {"version": version, "source_id": "user_manual"},
        "score": score,
    }


def test_hybrid_rerank_orders_by_rerank_score_and_replaces_score():
    from retrieval.retriever import HybridRerankRetriever

    vec = FakeStore([_raw_hit("n_a", "短"), _raw_hit("n_b", "很长很长")])
    retriever = HybridRerankRetriever(vec, FakeStore([]), lambda q, texts: [1.5, 9.0])

    out = asyncio.run(retriever.retrieve("q", top_k=2))

    assert [h["node_id"] for h in out] == ["n_b", "n_a"]
    assert out[0]["score"] == 9.0 and out[1]["score"] == 1.5   # score 被精排分替换
    assert out[0]["text"] == "很长很长"
    assert out[0]["source_id"] == "user_manual"                 # 仍投影为富引用


def test_hybrid_rerank_uses_candidate_top_k_as_pool():
    from retrieval.retriever import HybridRerankRetriever

    vec, bm = FakeStore([_raw_hit("n_a", "a")]), FakeStore([_raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, bm, lambda q, texts: [1.0], candidate_top_k=30)

    asyncio.run(retriever.retrieve("q", top_k=2))

    assert vec.calls[0][1] == 30      # 池 = max(top_k, candidate_top_k)
    assert bm.calls[0][1] == 30


def test_hybrid_rerank_empty_candidates_skips_rerank():
    from retrieval.retriever import HybridRerankRetriever

    def boom(q, texts):
        raise AssertionError("空候选不应调用精排")

    retriever = HybridRerankRetriever(FakeStore([]), FakeStore([]), boom)
    assert asyncio.run(retriever.retrieve("q", top_k=5)) == []


def test_hybrid_rerank_tie_breaks_by_node_id():
    from retrieval.retriever import HybridRerankRetriever

    vec = FakeStore([_raw_hit("n_z", "z"), _raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, FakeStore([]), lambda q, texts: [1.0, 1.0])

    out = asyncio.run(retriever.retrieve("q", top_k=5))

    assert [h["node_id"] for h in out] == ["n_a", "n_z"]


def test_hybrid_rerank_pushes_filters_to_both_stores():
    from retrieval.retriever import HybridRerankRetriever

    vec, bm = FakeStore([_raw_hit("n_a", "a")]), FakeStore([_raw_hit("n_a", "a")])
    retriever = HybridRerankRetriever(vec, bm, lambda q, texts: [1.0],
                                      filters={"source_type": "html"})

    asyncio.run(retriever.retrieve("q", top_k=1))

    assert vec.calls[0][2] == {"source_type": "html"}
    assert bm.calls[0][2] == {"source_type": "html"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_rerank.py -v`
Expected: FAIL — `ImportError: cannot import name 'HybridRerankRetriever'`

- [ ] **Step 3: 实现（`retrieval/retriever.py`，插在 `HybridRetriever` 类之后）**

```python
class HybridRerankRetriever:
    """多来源 Hybrid 粗排（RRF）+ 交叉编码器精排（指南 §8.2 Top30→Top5）。

    走原始 hit 通路：版本加权需要 metadata，而富引用经 _to_source_ref 投影后
    不再携带 metadata——加权必须在投影前、精排后完成，故本类直接持有两个
    store 而非包一层通用装饰器。
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        rerank_fn: Callable[[str, list[str]], list[float]],
        rrf_k: float = DEFAULT_RRF_K,
        candidate_top_k: int = 30,
        filters: dict | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._rerank_fn = rerank_fn
        self._rrf_k = rrf_k
        self._candidate_top_k = candidate_top_k
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        pool_k = max(top_k, self._candidate_top_k)
        vec_hits = self._vector_store.query(question, pool_k, filters=self._filters)
        bm_hits = self._bm25_store.query(question, pool_k, filters=self._filters)
        fused = fuse_hits([vec_hits, bm_hits], top_k=pool_k, k=self._rrf_k)
        if not fused:
            return []
        scores = self._rerank_fn(question, [h["text"] for h in fused])
        ranked = sorted(zip(fused, scores), key=lambda p: (-p[1], p[0]["node_id"]))
        return [_to_source_ref({**h, "score": float(s)}) for h, s in ranked[:top_k]]
```

顶部 import 增补：`from collections.abc import Callable`。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_rerank.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add retrieval/retriever.py tests/unit/test_rerank.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): HybridRerankRetriever 精排通路（原始 hit，保 metadata）"
```

---

### Task 3: `build_retriever` 分发 + 引用制 gate

**Files:**
- Modify: `retrieval/retriever.py`（抽 `_load_hybrid_stores`；增 hybrid_rerank 分支；签名加 `rerank_fn=None`；更新兜底报错信息）
- Modify: `retrieval/index.py`（hybrid gate 纳入 hybrid_rerank）
- Test: `tests/unit/test_hybrid_retriever.py`（追加）；`tests/unit/test_retrieval.py`（翻转拒绝断言、清理 `_write_config` 死分支）

**Interfaces:**
- Consumes: Task 2 的 `HybridRerankRetriever`；Task 1 的 `rerank.build_reranker`。
- Produces: `build_retriever(cfg, embed_fn=None, rerank_fn=None)`（Task 5/8/9 消费）。

- [ ] **Step 1: 写失败测试**

`tests/unit/test_hybrid_retriever.py` 顶部 import 增补 `HybridRerankRetriever`，并追加：

```python
HYBRID_RERANK_TEMPLATE = """schema_version: 1
experiment:
  name: {name}
  stage: ablation
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"
chunking:
  method: struct
  version: v1
embedding:
  provider: local
  model: bge-m3
retrieval:
  mode: hybrid_rerank
  top_k: 5
  candidate_top_k: 30
  rerank_model: bge-reranker-v2-m3
  params: {{rrf_k: 60}}
  components: {{vector: {vec}, bm25: {bm}}}
"""


def _write_hybrid_rerank(tmp_path: Path, vec: str, bm: str, name: str = "usage_hr") -> Path:
    d = tmp_path / "configs" / "experiments"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.yaml"
    p.write_text(HYBRID_RERANK_TEMPLATE.format(name=name, vec=vec, bm=bm), encoding="utf-8")
    return p


def test_build_retriever_hybrid_rerank_uses_injected_rerank_fn(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid_rerank(tmp_path, "comp_vec_v1", "comp_bm25_v1"))
    seen_texts: list[str] = []

    def fake_rerank(question, texts):
        seen_texts.extend(texts)
        return [float(len(t)) for t in texts]

    retriever = build_retriever(cfg, embed_fn=fake, rerank_fn=fake_rerank)

    assert isinstance(retriever, HybridRerankRetriever)
    results = asyncio.run(retriever.retrieve("alpha 连接", top_k=3))
    assert results and seen_texts            # 精排被调用且拿到候选文本
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_rerank_rejects_mismatched_node_sets(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch, bm_method="fixed")
    cfg = experiment_config.load(_write_hybrid_rerank(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(ValueError, match="节点集"):
        build_retriever(cfg, embed_fn=fake, rerank_fn=lambda q, t: [1.0] * len(t))


def test_hybrid_rerank_missing_subindex_raises_with_build_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    _write_component(tmp_path, "comp_vec_v1", "vector")
    _write_component(tmp_path, "comp_bm25_v1", "bm25")
    cfg = experiment_config.load(_write_hybrid_rerank(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(FileNotFoundError, match="make index"):
        build_retriever(cfg, embed_fn=FakeEmbedder(VECTORS),
                        rerank_fn=lambda q, t: [1.0] * len(t))


def test_build_index_rejects_hybrid_rerank_reference_mode(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid_rerank(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(ValueError, match="引用制"):
        build_index(cfg, embed_fn=fake)
```

`tests/unit/test_retrieval.py`：把 `test_build_retriever_rejects_unsupported_mode`（约 649-657 行）**整体替换**为：

```python
def test_build_retriever_rejects_unknown_mode_defensively(tmp_path, monkeypatch):
    # 四种合法模式均已实现；此分支只拦「绕过 schema 的运行时篡改」（model_copy 不校验）。
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    bad = cfg.model_copy(deep=True)
    bad.retrieval.mode = "bogus_mode"

    with pytest.raises(NotImplementedError, match="bogus_mode"):
        build_retriever(bad, embed_fn=FakeEmbedder({}))
```

并删除 `_write_config` 中已无消费方的 `elif retrieval_mode == "hybrid_rerank":` 分支（`components_block` 只保留 hybrid 一支）。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_hybrid_retriever.py tests/unit/test_retrieval.py -v -k "rerank or unknown_mode"`
Expected: FAIL — hybrid_rerank 分支缺失（NotImplementedError "待第四周实现"）等

- [ ] **Step 3: 实现**

`retrieval/retriever.py`——抽公共装载段（把现 hybrid 分支 105-144 行的主体移入），并改写分发：

```python
def _load_hybrid_stores(cfg, embed_fn):
    """hybrid/hybrid_rerank 引用制公共装载段：校验 components 并载入两个子索引。"""
    comps = cfg.retrieval.components or {}
    missing_roles = [role for role in ("vector", "bm25") if role not in comps]
    if missing_roles:
        raise ValueError(
            f"hybrid components 缺少角色: {missing_roles}"
            "（需要 vector 与 bm25 两类引用，见 configs/experiments/README.md）"
        )
    vec_cfg = experiment_config.load(
        experiment_config.experiment_yaml_path(comps["vector"]))
    bm25_cfg = experiment_config.load(
        experiment_config.experiment_yaml_path(comps["bm25"]))
    vec_nodes = experiment_config.nodes_path(vec_cfg)
    bm25_nodes = experiment_config.nodes_path(bm25_cfg)
    if vec_nodes != bm25_nodes:
        raise ValueError(
            f"hybrid 两路节点集不一致：vector={comps['vector']} → {vec_nodes.name}，"
            f"bm25={comps['bm25']} → {bm25_nodes.name}；"
            "RRF 按 node_id 融合要求 components 产出同一节点集（chunking+sources 相同）"
        )
    vec_path = experiment_config.index_dir(vec_cfg)
    bm25_path = experiment_config.index_dir(bm25_cfg)
    for role, path in (("vector", vec_path), ("bm25", bm25_path)):
        if not path.exists():
            raise FileNotFoundError(
                f"子索引不存在: {path}（role={role}，请先运行 "
                f"make index CFG=configs/experiments/{comps[role]}.yaml）"
            )
    if embed_fn is None:
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(vec_cfg)
    vector_store = VectorStore(
        embed_fn=embed_fn,
        persist_path=str(vec_path),
        metric=vec_cfg.index.metric,
        collection_name=sanitize_collection_name(
            experiment_config.index_dirname(vec_cfg)),
    )
    return vector_store, BM25Store.load(bm25_path)
```

`build_retriever` 签名与分支（原 hybrid 分支整体替换为）：

```python
def build_retriever(cfg, embed_fn=None, rerank_fn=None):
    """按实验配置组装：索引目录/集合名由 configs 派生命名（D 的约定）。"""
    index_path = experiment_config.index_dir(cfg)
    if cfg.retrieval.mode == "bm25":
        ...
    if cfg.retrieval.mode in ("hybrid", "hybrid_rerank"):
        vector_store, bm25_store = _load_hybrid_stores(cfg, embed_fn)
        rrf_k = float((cfg.retrieval.params or {}).get("rrf_k", DEFAULT_RRF_K))
        if cfg.retrieval.mode == "hybrid":
            return HybridRetriever(
                vector_store,
                bm25_store,
                rrf_k=rrf_k,
                candidate_top_k=cfg.retrieval.candidate_top_k,
                filters=cfg.retrieval.filters or None,
            )
        if rerank_fn is None:
            from retrieval.rerank import build_reranker

            rerank_fn = build_reranker(cfg)
        return HybridRerankRetriever(
            vector_store,
            bm25_store,
            rerank_fn,
            rrf_k=rrf_k,
            candidate_top_k=cfg.retrieval.candidate_top_k,
            filters=cfg.retrieval.filters or None,
        )
    if cfg.retrieval.mode != "vector":
        raise NotImplementedError(
            f"当前支持 vector/bm25/hybrid/hybrid_rerank 四种检索模式，"
            f"收到 mode={cfg.retrieval.mode!r}"
        )
    ...
```

（`bm25` 分支与 `vector` 分支主体不变。）

`retrieval/index.py` 顶部 gate：

```python
    if cfg.retrieval.mode in ("hybrid", "hybrid_rerank"):
        # 引用制无自有索引（PR#27 设计 §2.2）：子索引由各自配置管；
        # scripts/build_index.py 已提前短路，此处拦程序化误用
        raise ValueError(
            "hybrid/hybrid_rerank 为引用制、无自有索引：请分别构建 components 引用的子配置"
            "（make index CFG=configs/experiments/<子实验>.yaml）"
        )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_hybrid_retriever.py tests/unit/test_retrieval.py tests/unit/test_rerank.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add retrieval/retriever.py retrieval/index.py tests/unit/test_hybrid_retriever.py tests/unit/test_retrieval.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): build_retriever 分发 hybrid_rerank + 引用制 gate（公共装载段抽取）"
```

---

### Task 4: 版本加权纯函数 `retrieval/boosts.py`

**Files:**
- Create: `retrieval/boosts.py`
- Test: `tests/unit/test_version_boost.py`（新建）

**Interfaces:**
- Produces: `apply_version_boost(hits: list[dict], version_pref: str | None, boost: float) -> list[dict]`（Task 5 全模式接线消费）。

- [ ] **Step 1: 写失败测试 `tests/unit/test_version_boost.py`**

```python
"""版本加权（boosts.py）与其在四种检索模式上的接线测试。

纯函数部分不依赖任何 store；接线部分用假 store（原始 hit）与
EphemeralClient 内存向量库，不落盘、不加载模型。
"""
from __future__ import annotations

import asyncio

import pytest

from retrieval.boosts import apply_version_boost


def _h(node_id: str, score: float, version: str | None = None) -> dict:
    md = {} if version is None else {"version": version}
    return {"node_id": node_id, "text": "t", "metadata": md, "score": score}


def test_boost_floats_matched_above_adjacent_higher():
    hits = [_h("n_a", 0.90, "2.0"), _h("n_b", 0.88, "2.4"), _h("n_c", 0.60, "2.0")]

    out = apply_version_boost(hits, "2.4", 0.1)

    assert [r["node_id"] for r in out] == ["n_b", "n_a", "n_c"]
    assert out[0]["score"] == pytest.approx((0.88 - 0.60) / 0.30 + 0.1, abs=1e-6)


def test_unmatched_keep_relative_order_and_scores_normalized():
    hits = [_h("n_a", 10.0), _h("n_b", 5.0)]

    out = apply_version_boost(hits, "9.9", 0.5)   # 无任何命中：仍归一化

    assert [r["node_id"] for r in out] == ["n_a", "n_b"]
    assert out[0]["score"] == pytest.approx(1.0)
    assert out[1]["score"] == pytest.approx(0.0)


def test_inactive_boost_returns_input_untouched():
    hits = [_h("n_a", 0.9, "2.0"), _h("n_b", 0.1, "2.4")]

    assert apply_version_boost(hits, None, 0.5) is hits     # 未配 pref
    assert apply_version_boost(hits, "2.4", 0.0) is hits    # boost=0
    assert apply_version_boost(hits, "2.4", -0.1) is hits   # 负 boost 也是 no-op


def test_ties_break_by_node_id():
    hits = [_h("n_z", 1.0, "2.4"), _h("n_a", 1.0, "2.4")]

    out = apply_version_boost(hits, "2.4", 0.2)

    assert [r["node_id"] for r in out] == ["n_a", "n_z"]
    assert out[0]["score"] == pytest.approx(out[1]["score"])


def test_single_item_pool_and_empty_pool():
    assert apply_version_boost([], "2.4", 0.1) == []

    out = apply_version_boost([_h("n_a", 3.0, "2.4")], "2.4", 0.1)
    assert out[0]["score"] == pytest.approx(0.6)            # max==min → 0.5，命中 +0.1


def test_returns_new_list_input_not_mutated():
    hits = [_h("n_a", 1.0, "2.4"), _h("n_b", 0.5, "2.0")]

    out = apply_version_boost(hits, "2.4", 0.1)

    assert out is not hits
    assert hits[0]["score"] == 1.0                          # 原列表未被改分
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_version_boost.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.boosts'`

- [ ] **Step 3: 实现 `retrieval/boosts.py`**

```python
"""检索后加权：版本软偏好（指南 §8.3）——候选池内归一化 + 命中加成。

量纲免疫：cosine(0~1) / BM25(7.7~56.4) / RRF(~0.03) / 交叉编码器分（可负）
先做池内 min-max 归一（max==min 时全取 0.5），再给命中版本加 boost。
乘法在负分上会翻转顺序、加法在 RRF 量纲上会淹没原分，故两者都不用。

必须在截断 top_k 之前调用（池外候选没有上浮机会）；生效时 score 语义变为
「池内归一化排序分」（跨查询不可比，阈值口径按配置分别定标——见 api.md）。
"""
from __future__ import annotations


def apply_version_boost(
    hits: list[dict], version_pref: str | None, boost: float
) -> list[dict]:
    """命中 metadata.version == version_pref 的候选加 boost 后重排。

    未配置（pref 空 / boost<=0）或空列表时原样返回（同一对象，零回归）。
    """
    if not hits or not version_pref or boost <= 0:
        return hits
    scores = [float(h["score"]) for h in hits]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    out = []
    for h, s in zip(hits, scores):
        norm = 0.5 if span == 0 else (s - lo) / span
        if (h.get("metadata") or {}).get("version") == version_pref:
            norm += boost
        out.append({**h, "score": round(norm, 6)})
    out.sort(key=lambda r: (-r["score"], r["node_id"]))
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_version_boost.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add retrieval/boosts.py tests/unit/test_version_boost.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): 版本加权纯函数 apply_version_boost（池内归一化+加成）"
```

---

### Task 5: 四模式接线 version 参数 + `build_retriever` 参数流转

**Files:**
- Modify: `retrieval/retriever.py`（四个检索类接 `version_pref`/`version_boost`；`build_retriever` 从 params 取值下发）
- Test: `tests/unit/test_version_boost.py`（追加接线）；`tests/unit/test_hybrid_retriever.py`（追加 params 流转）

**Interfaces:**
- Consumes: Task 4 的 `apply_version_boost`；Task 2/3 的类与分发。
- Produces: 所有检索类构造签名 `(..., candidate_top_k=30, version_pref=None, version_boost=0.0)`；配置 `retrieval.params.version_pref / version_boost` 生效（Task 7 配置、Task 9 实验消费）。

- [ ] **Step 1: 写失败测试**

`tests/unit/test_version_boost.py` 追加（顶部补 import：`from retrieval.nodes import NodeRecord`、`from retrieval.vector_store import VectorStore`、`from retrieval.retriever import BM25Retriever, HybridRetriever, HybridRerankRetriever, VectorRetriever`）：

```python
class FakeEmbedder:
    def __init__(self, vectors, dim: int = 4):
        self.vectors = vectors
        self.dim = dim

    def __call__(self, texts):
        return [self.vectors.get(t, [0.0] * self.dim) for t in texts]


class FakeStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def query(self, question, top_k, filters=None):
        self.calls.append((question, top_k, filters))
        return [dict(h) for h in self.hits[:top_k]]


def _raw_hit(node_id: str, text: str, version: str = "2.0", score: float = 0.5) -> dict:
    return {"node_id": node_id, "text": text,
            "metadata": {"version": version, "source_id": "user_manual"},
            "score": score}


def _make_vector_store():
    import uuid

    vecs = {
        "q": [1.0, 0.0, 0.0, 0.0],
        "pdf 手册正文": [1.0, 0.0, 0.0, 0.0],
        "html 指南正文": [0.99, 0.141, 0.0, 0.0],
        "pdf 附录正文": [0.5, 0.866, 0.0, 0.0],
    }
    store = VectorStore(embed_fn=FakeEmbedder(vecs),
                        collection_name=f"boost_{uuid.uuid4().hex}")
    store.add_nodes([
        NodeRecord("n_pdf1", "pdf 手册正文", {"version": "2.0", "source_id": "user_manual"}),
        NodeRecord("n_html", "html 指南正文", {"version": "2.4", "source_id": "zrdds_dev_guide"}),
        NodeRecord("n_pdf2", "pdf 附录正文", {"version": "2.0", "source_id": "user_manual"}),
    ])
    return store


def test_vector_retriever_version_boost_floats_html_to_top():
    store = _make_vector_store()
    base = asyncio.run(VectorRetriever(store).retrieve("q", top_k=3))
    assert [r["node_id"] for r in base] == ["n_pdf1", "n_html", "n_pdf2"]

    boosted = asyncio.run(
        VectorRetriever(store, candidate_top_k=30, version_pref="2.4", version_boost=0.1)
        .retrieve("q", top_k=3))

    assert [r["node_id"] for r in boosted] == ["n_html", "n_pdf1", "n_pdf2"]


def test_vector_retriever_without_version_params_unchanged():
    store = _make_vector_store()
    a = asyncio.run(VectorRetriever(store).retrieve("q", top_k=2))
    b = asyncio.run(VectorRetriever(store, version_pref=None, version_boost=0.0)
                    .retrieve("q", top_k=2))

    assert [r["node_id"] for r in a] == [r["node_id"] for r in b]
    assert [r["score"] for r in a] == [r["score"] for r in b]


def test_bm25_retriever_version_boost_flips_ranking():
    from retrieval.bm25 import BM25Store

    store = BM25Store()
    store.add_nodes([
        NodeRecord("n_a", "alpha alpha alpha", {"version": "2.0", "source_id": "user_manual"}),
        NodeRecord("n_b", "alpha", {"version": "2.4", "source_id": "zrdds_dev_guide"}),
    ])
    base = asyncio.run(BM25Retriever(store).retrieve("alpha", top_k=2))
    assert [r["node_id"] for r in base] == ["n_a", "n_b"]

    boosted = asyncio.run(
        BM25Retriever(store, version_pref="2.4", version_boost=2.0).retrieve("alpha", top_k=2))

    assert [r["node_id"] for r in boosted] == ["n_b", "n_a"]


def test_hybrid_retriever_version_boost_and_pool():
    vec = FakeStore([_raw_hit("n_a", "a"), _raw_hit("n_b", "b", "2.4"),
                     _raw_hit("n_c", "c")])
    retriever = HybridRetriever(vec, FakeStore([]), candidate_top_k=10,
                                version_pref="2.4", version_boost=0.6)

    out = asyncio.run(retriever.retrieve("q", top_k=3))

    assert vec.calls[0][1] == 10                       # 池 = max(top_k, candidate_top_k)
    assert [h["node_id"] for h in out] == ["n_b", "n_a", "n_c"]


def test_hybrid_rerank_version_boost_applied_after_rerank():
    vec = FakeStore([_raw_hit("n_a", "a"), _raw_hit("n_b", "b", "2.4"),
                     _raw_hit("n_c", "c")])
    retriever = HybridRerankRetriever(
        vec, FakeStore([]), lambda q, texts: [9.0, 8.0, 5.0],
        candidate_top_k=10, version_pref="2.4", version_boost=0.3)

    out = asyncio.run(retriever.retrieve("q", top_k=3))

    assert [h["node_id"] for h in out] == ["n_b", "n_a", "n_c"]   # 精排后加权翻转
```

`tests/unit/test_hybrid_retriever.py` 追加：

```python
def test_build_retriever_passes_version_params(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))
    probe = cfg.model_copy(deep=True)
    probe.retrieval.params = {"rrf_k": 60, "version_pref": "2.4", "version_boost": 0.1}

    retriever = build_retriever(probe, embed_fn=fake)

    assert retriever._version_pref == "2.4"
    assert retriever._version_boost == 0.1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_version_boost.py tests/unit/test_hybrid_retriever.py -v -k "boost or version"`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'version_pref'`

- [ ] **Step 3: 实现（`retrieval/retriever.py`）**

顶部 import 增补 `from retrieval.boosts import apply_version_boost`。四个类统一改造：

```python
class VectorRetriever:
    def __init__(self, store, filters=None, candidate_top_k=30,
                 version_pref=None, version_boost=0.0):
        self._store = store
        self._filters = filters
        self._candidate_top_k = candidate_top_k
        self._version_pref = version_pref
        self._version_boost = version_boost
        self._boost_active = bool(version_pref) and version_boost > 0

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 第一周为同步实现（CPU 推理），直接放在 async 方法内；
        # D 服务端接线时若发现阻塞事件循环，用 anyio.to_thread 包裹。
        pool_k = max(top_k, self._candidate_top_k) if self._boost_active else top_k
        results = self._store.query(question, pool_k, filters=self._filters)
        results = apply_version_boost(results, self._version_pref, self._version_boost)
        return [_to_source_ref(r) for r in results[:top_k]]
```

`BM25Retriever` 同款（构造签名与 retrieve 结构一致）。

`HybridRetriever`：构造签名追加同两个参数（无需 `_boost_active`——融合池恒为 `sub_k`，截断后移）；retrieve 改为：

```python
    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 子检索各取候选池；top_k 大于池容量时以 top_k 兜底（防融合池不足）
        sub_k = max(top_k, self._candidate_top_k)
        vec_hits = self._vector_store.query(question, sub_k, filters=self._filters)
        bm_hits = self._bm25_store.query(question, sub_k, filters=self._filters)
        fused = fuse_hits([vec_hits, bm_hits], top_k=sub_k, k=self._rrf_k)
        fused = apply_version_boost(fused, self._version_pref, self._version_boost)
        return [_to_source_ref(r) for r in fused[:top_k]]
```

（融合目标由 top_k 改为 sub_k：fuse_hits 只做排序+截断，截断位变化不改变前 top_k 的顺序与分数——零回归。）

`HybridRerankRetriever`：构造签名追加同两个参数；retrieve 末段改为：

```python
        ranked = sorted(zip(fused, scores), key=lambda p: (-p[1], p[0]["node_id"]))
        hits = [{**h, "score": float(s)} for h, s in ranked]
        hits = apply_version_boost(hits, self._version_pref, self._version_boost)
        return [_to_source_ref(r) for r in hits[:top_k]]
```

`build_retriever` 顶部与各分支下发：

```python
def build_retriever(cfg, embed_fn=None, rerank_fn=None):
    """按实验配置组装：索引目录/集合名由 configs 派生命名（D 的约定）。"""
    params = cfg.retrieval.params or {}
    version_pref = params.get("version_pref")
    version_boost = float(params.get("version_boost", 0.0))
    index_path = experiment_config.index_dir(cfg)
    ...
```

四个 `return` 处一律追加 `candidate_top_k=cfg.retrieval.candidate_top_k, version_pref=version_pref, version_boost=version_boost`。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_version_boost.py tests/unit/test_hybrid_retriever.py tests/unit/test_rerank.py tests/unit/test_retrieval.py tests/unit/test_rrf.py -v`
Expected: 全部 PASS（含既有 hybrid/rrf 用例，证明零回归）

- [ ] **Step 5: 提交**

```bash
git add retrieval/retriever.py tests/unit/test_version_boost.py tests/unit/test_hybrid_retriever.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): 四模式接线版本加权 + build_retriever 参数流转"
```

---

### Task 6: D 脚本 gate 纳入 hybrid_rerank（会签项 1）

**Files:**
- Modify: `scripts/build_index.py`（`cmd_build` 与 `cmd_list`）
- Modify: `scripts/run_experiment.py`（`_ensure_index` 与 `_ensure_hybrid_subindexes` docstring）
- Test: `tests/unit/test_run_experiment.py`（追加两条）

**Interfaces:**
- Consumes: 无（纯条件分支扩展）。
- Produces: `make index` / `run_experiment` 对 hybrid_rerank 走引用制检查（Task 9 实验依赖）。

- [ ] **Step 1: 写失败测试（`tests/unit/test_run_experiment.py` 追加，紧随现有 `test_build_index_skips_hybrid` 之后）**

```python
def test_build_index_skips_hybrid_rerank(tmp_path, capsys):
    """引用制 gate 纳入 hybrid_rerank：make index 跳过、不写 manifest。"""
    import build_index as bi
    text = (REPO_ROOT / "configs" / "experiments" / "struct_v1.yaml").read_text(encoding="utf-8")
    text = text.replace("name: struct_v1", "name: struct_hr_t").replace(
        "mode: vector",
        "mode: hybrid_rerank\n  rerank_model: bge-reranker-v2-m3\n"
        "  components: {vector: struct_v1, bm25: struct_bm25}",
    )
    p = tmp_path / "struct_hr_t.yaml"
    p.write_text(text, encoding="utf-8")
    rc = bi.cmd_build(str(p), fake=False)
    out = capsys.readouterr().out
    assert rc == 0 and "无自有索引" in out and "struct_v1" in out


def test_ensure_index_hybrid_rerank_checks_subindexes(capsys):
    """run_experiment 对 hybrid_rerank 同 hybrid：只查子索引、不构建本配置索引。"""
    base = ec.load(REPO_ROOT / "configs" / "experiments" / "struct_v1.yaml")
    hr = base.model_copy(update={
        "retrieval": base.retrieval.model_copy(update={
            "mode": "hybrid_rerank",
            "rerank_model": "bge-reranker-v2-m3",
            "components": {"vector": "struct_v1", "bm25": "struct_bm25"},
        })
    })
    assert rx._ensure_index("configs/experiments/struct_v1.yaml", hr, False, False) == 0
    cap = capsys.readouterr()
    assert "子索引[vector] 复用" in cap.out + cap.err
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/unit/test_run_experiment.py -v -k "hybrid_rerank"`
Expected: FAIL — hybrid_rerank 未走引用制分支（cmd_build 会报 Node 集不存在 / _ensure_index 会尝试构建）

- [ ] **Step 3: 实现**

`scripts/build_index.py::cmd_build`：

```python
    if cfg.retrieval.mode in ("hybrid", "hybrid_rerank"):
        comps = cfg.retrieval.components or {}
        print(f"[index] mode={cfg.retrieval.mode} 无自有索引（引用制，PR#27 会签②）："
              "子索引由 components 引用的实验分别构建")
```

`scripts/build_index.py::cmd_list`：`if cfg.retrieval.mode == "hybrid":` → `if cfg.retrieval.mode in ("hybrid", "hybrid_rerank"):`（该分支的提示文案无需改）

`scripts/run_experiment.py::_ensure_index`：`if cfg.retrieval.mode == "hybrid":` → `if cfg.retrieval.mode in ("hybrid", "hybrid_rerank"):`

`scripts/run_experiment.py::_ensure_hybrid_subindexes` docstring 首行改为：
`"""hybrid / hybrid_rerank 引用制（PR#27 会签③；hybrid_rerank 第四周纳入）：只检查 components 引用的子索引是否存在。`

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/unit/test_run_experiment.py -v`
Expected: 全部 PASS（既有 hybrid 两条同跑）

- [ ] **Step 5: 提交**

```bash
git add scripts/build_index.py scripts/run_experiment.py tests/unit/test_run_experiment.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(scripts): 引用制 gate 纳入 hybrid_rerank（D 脚本，待会签）"
```

---

### Task 7: 三份实验配置 + 逐份自检

**Files:**
- Create: `configs/experiments/struct_multisrc_hybrid_rerank.yaml`
- Create: `configs/experiments/struct_multisrc_hybrid_ver24.yaml`
- Create: `configs/experiments/struct_multisrc_hybrid_ver20.yaml`

**Interfaces:**
- Consumes: Task 3/5 的 hybrid_rerank 分发与 version params；既有 struct_multisrc_v1 / struct_multisrc_bm25 子索引。
- Produces: Task 9 六次实验的配置入口。

- [ ] **Step 1: 建 `struct_multisrc_hybrid_rerank.yaml`**（照抄 struct_multisrc_hybrid.yaml，改 experiment 段与 retrieval 段）

```yaml
# =====================================================================
# RAG4ZRDDS 实验配置 · 第四周四组对比之四（Hybrid+Reranker，指南 §8.2）
# 引用制：components 引用 struct_multisrc_v1(vector) 与 struct_multisrc_bm25(bm25)，
# RRF 粗排 candidate_top_k=30 → bge-reranker-v2-m3 精排 top_k=5。
# =====================================================================
schema_version: 1

experiment:
  name: struct_multisrc_hybrid_rerank
  description: 第四周四组对比之四：多来源 Hybrid RRF 粗排 + bge-reranker-v2-m3 交叉编码器精排
  stage: ablation

sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"
  - id: zrdds_dev_guide
    type: html
    path: data/raw/developer-guides/cdoc_html
    version: "2.4"
    url: https://docs.zrtechnology.com/cdoc/html

ingest:
  cleaned_output: data/cleaned/pages.jsonl
  quality_check: true

chunking:                          # 与两个子配置一致（同一节点集）
  method: struct
  version: v1
  params:
    max_chunk_chars: 2500
    overlap_chars: 200
    large_section_thresh: 2500

embedding:
  provider: local
  model: bge-m3
  batch_size: 32
  device: cpu

index:
  backend: chroma
  metric: cosine

retrieval:
  mode: hybrid_rerank
  top_k: 5
  candidate_top_k: 30
  rerank_model: bge-reranker-v2-m3
  filters: {}
  params:
    rrf_k: 60
  components:
    vector: struct_multisrc_v1
    bm25: struct_multisrc_bm25

generation:
  enabled: false
  prompt_version: v0
  llm_env_prefix: LLM_

evaluation:
  dataset: evaluation/datasets/questions.jsonl
  expected_sources: null           # 宁缺毋滥：真值标注到位后翻回 expected_sources.jsonl 补指标
  retrieval_metrics: [hit_rate@5, mrr@5]
  response_metrics: []
  sample_size: null

report:
  dir: evaluation/reports
  compare_baseline: struct_multisrc_hybrid
```

- [ ] **Step 2: 建 `struct_multisrc_hybrid_ver24.yaml`**（同上，仅 experiment 段、retrieval.params、report 段变化，其余逐字一致）

```yaml
experiment:
  name: struct_multisrc_hybrid_ver24
  description: 第四周 Version-aware：多来源 Hybrid + v2.4 软偏好（version_pref/version_boost）
  stage: ablation

retrieval:
  mode: hybrid
  top_k: 5
  candidate_top_k: 30
  filters: {}
  params:
    rrf_k: 60
    version_pref: "2.4"
    version_boost: 0.1
  components:
    vector: struct_multisrc_v1
    bm25: struct_multisrc_bm25

report:
  dir: evaluation/reports
  compare_baseline: struct_multisrc_hybrid
```

- [ ] **Step 3: 建 `struct_multisrc_hybrid_ver20.yaml`**（同 Step 2，`name: struct_multisrc_hybrid_ver20`，描述改「v2.0 软偏好」，`version_pref: "2.0"`）

- [ ] **Step 4: 逐份自检**

Run:
```bash
.venv/Scripts/python scripts/experiment_config.py configs/experiments/struct_multisrc_hybrid_rerank.yaml
.venv/Scripts/python scripts/experiment_config.py configs/experiments/struct_multisrc_hybrid_ver24.yaml
.venv/Scripts/python scripts/experiment_config.py configs/experiments/struct_multisrc_hybrid_ver20.yaml
```
Expected: 三份均输出 `[配置有效]`，且 hybrid_rerank 的索引目录无 `[尚无]` 提示逻辑差异（引用制无自有索引目录，属正常）

- [ ] **Step 5: 提交**

```bash
git add configs/experiments/struct_multisrc_hybrid_rerank.yaml configs/experiments/struct_multisrc_hybrid_ver24.yaml configs/experiments/struct_multisrc_hybrid_ver20.yaml
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "exp(config): 第四周四组之 hybrid_rerank + 版本加权 ver24/ver20 配置"
```

---

### Task 8: 模型下载 + `scripts/smoke_rerank.py` + 真模型冒烟

**Files:**
- Create: `scripts/smoke_rerank.py`
- 产物：`models/bge-reranker-v2-m3/`（不入 Git）

**Interfaces:**
- Consumes: Task 3 的 `build_retriever(cfg)`（无注入 → 真模型）；Task 7 的配置。
- Produces: 真模型行为证据 + score 量纲结论（Task 10 写进 evaluation.md；api.md 条目交 D）。

- [ ] **Step 1: 后台启动模型下载**（约 2.3GB，直连 huggingface.co，勿设 HF_ENDPOINT）

```bash
cd "C:/Users/huziy/Desktop/软工实训/RAG4ZRDDS"
.venv/Scripts/python -c "from huggingface_hub import snapshot_download; p=snapshot_download('BAAI/bge-reranker-v2-m3', local_dir='models/bge-reranker-v2-m3'); print('done:', p)"
```
（用 run_in_background；下载期间继续 Task 1-7 的编码工作）

- [ ] **Step 2: 写 `scripts/smoke_rerank.py`**

```python
#!/usr/bin/env python3
"""scripts/smoke_rerank.py — 精排通路真模型冒烟（成员 B · 第四周 §8.2）

真实 bge-m3 向量 + bge-reranker-v2-m3 精排，跑少量探针题打印 top-5。
用于人工核验精排行为、score 量纲与来源漂移；产物记入 docs/evaluation.md。
不进 CI（模型加载占内存、耗时长）。

用法:
  .venv/Scripts/python scripts/smoke_rerank.py
  .venv/Scripts/python scripts/smoke_rerank.py --config configs/experiments/struct_multisrc_hybrid_ver24.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from retrieval._bootstrap import experiment_config as ec  # noqa: E402

PROBES = [
    "create_datawriter() 需要哪些参数？",
    "如何创建一个属于特定域的 DomainParticipant？",
    "v2.4 的 API 是否仍使用旧参数？",
]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="smoke_rerank", description=__doc__)
    parser.add_argument("--config",
                        default="configs/experiments/struct_multisrc_hybrid_rerank.yaml")
    args = parser.parse_args(argv)

    cfg = ec.load(args.config)
    from retrieval.retriever import build_retriever

    print(f"[smoke] 实验={cfg.experiment.name} mode={cfg.retrieval.mode}"
          "（首次加载真模型，请稍候）")
    retriever = build_retriever(cfg)
    for q in PROBES:
        print(f"\n[smoke] Q: {q}")
        hits = asyncio.run(retriever.retrieve(q, cfg.retrieval.top_k))
        for i, h in enumerate(hits, 1):
            print(f"  {i}. {h['node_id']}  score={h['score']:.6f}  "
                  f"source={h.get('source_id')}  section={h.get('section')}")
    print("\n[smoke] 核验点：score 量纲/范围、来源分布、API 类问题是否被拉向 dev guide")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 确认下载完成并冒烟**

```bash
ls models/bge-reranker-v2-m3 | head   # 应见 config.json / model.safetensors / tokenizer*
.venv/Scripts/python scripts/smoke_rerank.py
.venv/Scripts/python scripts/smoke_rerank.py --config configs/experiments/struct_multisrc_hybrid_ver24.yaml
```

Expected: 两次冒烟各 3 题输出 top-5；**记录 score 实际范围（sigmoid 0~1 或原始 logits）**——该结论写进 Task 10 的 evaluation.md 与 api.md 条目。

- [ ] **Step 4: 兼容性降级路径**（仅在冒烟加载失败时执行）

若 transformers 5.16 加载报错：改 `retrieval/rerank.py` 的加载为
`CrossEncoder(resolve_model(model_name), device=cfg.embedding.device, trust_remote_code=True)`；
仍失败则把配置的 `rerank_model` 换成 `bge-reranker-base`（同步改 Task 7 三份配置与 README 记录），
并在 evaluation.md 记录「模型降级 + 原因」。

- [ ] **Step 5: 提交脚本**

```bash
git add scripts/smoke_rerank.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(scripts): 精排真模型冒烟脚本（3 探针题，人工核验用）"
```

---

### Task 9: 六次实验运行 + 证据核验

**Files:**
- 产物：`evaluation/reports/struct_multisrc_hybrid_rerank.json`、`struct_multisrc_hybrid_ver24.json`、`struct_multisrc_hybrid_ver20.json`（vector/bm25/hybrid 三份视需要重跑刷新）

**Interfaces:**
- Consumes: Task 6 的 gate、Task 7 的配置、Task 8 的真模型。
- Produces: Task 10 的结论素材。

- [ ] **Step 1: 四组对比依次运行**（前台逐条，勿并行——CPU 互相拖慢；rerank 组预计 10~25 分钟）

```bash
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_v1.yaml
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_bm25.yaml
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_hybrid.yaml
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_hybrid_rerank.yaml
```

Expected: 每份输出 `✓ 完成` 与报告路径；`metrics` 为 n/a（无标注，协议内），`skipped_no_expected` = 全部题。

- [ ] **Step 2: 版本两组运行**

```bash
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_hybrid_ver24.yaml
.venv/Scripts/python scripts/run_experiment.py --config configs/experiments/struct_multisrc_hybrid_ver20.yaml
```

- [ ] **Step 3: 证据核验一——hybrid vs hybrid_rerank 的 top-1/top-3 漂移**

```bash
.venv/Scripts/python - <<'PY'
import json

def load(name):
    rep = json.load(open(f"evaluation/reports/{name}.json", encoding="utf-8"))
    return {e["id"]: [r["node_id"] for r in e["retrieved"]] for e in rep["per_question"]}

h, hr = load("struct_multisrc_hybrid"), load("struct_multisrc_hybrid_rerank")
qs = {json.loads(l)["id"]: json.loads(l) for l in open("evaluation/datasets/questions.jsonl", encoding="utf-8")}
top1 = [q for q in h if h[q][:1] != hr[q][:1]]
api_like = [q for q in top1 if qs[q]["type"] in ("api_use", "error_code")]
print(f"top-1 变化 {len(top1)}/{len(h)}；其中 api_use/error_code 题 {len(api_like)}")
for q in api_like[:5]:
    print(f"  {q} [{qs[q]['type']}] {qs[q]['question'][:40]}")
PY
```
Expected: 输出变化题数与示例（数值如实记录，不预设方向）。

- [ ] **Step 4: 证据核验二——版本加权两个方向的漂移**

```bash
.venv/Scripts/python - <<'PY'
import json

def load(name):
    rep = json.load(open(f"evaluation/reports/{name}.json", encoding="utf-8"))
    return {e["id"]: [r.get("source_id") for r in e["retrieved"]] for e in rep["per_question"]}

base, v24, v20 = (load("struct_multisrc_hybrid"), load("struct_multisrc_hybrid_ver24"),
                  load("struct_multisrc_hybrid_ver20"))

def guide_share(rep, name):
    n_guide = sum(1 for q in rep for s in rep[q] if s == "zrdds_dev_guide")
    n_all = sum(len(v) for v in rep.values())
    print(f"{name}: dev_guide 占比 {n_guide}/{n_all} = {n_guide / n_all:.3f}")

for rep, name in ((base, "baseline"), (v24, "ver24"), (v20, "ver20")):
    guide_share(rep, name)
print("期望方向：ver24 的 dev_guide 占比 > baseline > ver20")
PY
```
Expected: ver24 占比显著高于 baseline、ver20 低于 baseline；否则记录差异并检查 boost 配置是否生效。

- [ ] **Step 5: 提交报告**

```bash
git add evaluation/reports/struct_multisrc_hybrid_rerank.json evaluation/reports/struct_multisrc_hybrid_ver24.json evaluation/reports/struct_multisrc_hybrid_ver20.json
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "exp: 第四周四组对比 + 版本加权实验报告（证据链，指标待真值标注）"
```

---

### Task 10: `docs/evaluation.md` + 全量回归 + 收尾

**Files:**
- Create: `docs/evaluation.md`
- 更新：`configs/experiments/README.md`（会签项 3 的出稿，D 追认）

**Interfaces:**
- Consumes: Task 8/9 的全部证据。
- Produces: 指南 §8 要求「结论写入 docs/evaluation.md」的交付物；PR 素材。

- [ ] **Step 1: 写 `docs/evaluation.md`（B 检索部分）**

固定结构（内容用 Task 8/9 实测数字与输出填充，不预设结论）：

```markdown
# 检索评测记录

> 维护：成员 B（检索域）。指标口径按指南 §9.1；判对标准归 C，标注归 E。
> 更新：2026-09-14（第四周四组对比 + Version-aware）。

## 1. 方法学

- 语料：多来源（user_manual v2.0 PDF + zrdds_dev_guide v2.4 HTML），struct/v1 分块，1606 节点
- 四组定义：Vector(struct_multisrc_v1) / BM25(_bm25) / Hybrid(_hybrid, RRF k=60) / Hybrid+Reranker(_hybrid_rerank, candidate_top_k=30 → bge-reranker-v2-m3 → top_k=5)
- 题集：questions.jsonl 120 题（api_use 36 / config 30 / error_case 11 等）
- 指标状态：【真值标注待 E 交付，本轮为证据链模式（expected_sources: null，宁缺毋滥）】

## 2. 四组对比结果

（逐组：运行时长、top-1 漂移统计、典型案例；rerank 是否产生增益，如实记录——指南 §8.2）

## 3. Version-aware 结果

（ver24/ver20 的 dev_guide 占比对照、方向核验、score 量纲说明）

## 4. 局限与后续

- 真值标注未到位：翻配置即可补正式指标（hit_rate@5 / mrr@5）
- A 终版 Node 集未冻结：变更需重建索引后重跑
- 双版本同源场景当前不存在（版本与来源一一对应），机制泛化性未实测
```

- [ ] **Step 2: `configs/experiments/README.md` params 行补一句（会签项 3）**

在 retrieval 表格 `params` 行尾追加：
`B 域参数：bm25 的 k1/b、RRF 的 rrf_k、版本软偏好 version_pref/version_boost（命中版本在候选池内归一化分上加成，示例 0.1）。`

- [ ] **Step 3: 全量回归**

```bash
.venv/Scripts/python -m pytest tests/unit -q
```
Expected: 除既有已知失败（`test_real_error_cases.py` 的 REAL-NE-* 案例 id 失配，A/D 域待办）外全部通过；若出现新失败，回到对应 Task 修复。

- [ ] **Step 4: 提交**

```bash
git add docs/evaluation.md configs/experiments/README.md
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "docs(eval): 第四周四组对比与版本加权结论 + README params 说明（会签项 3）"
```

- [ ] **Step 5: 推分支、准备 PR**（推送前与用户确认）

```bash
git push fork feature/week4-hybrid-rerank
```

PR 正文需包含：spec 链接、四组对比与版本实验结论摘要、会签事项清单（D：三处 gate 补丁审查 + api.md 量纲 + README 追认；C：阈值口径 + 问题 6.1 答复；E：标注依赖）。

---

## 会签提醒（实现期间同步 D/C）

1. **D**：Task 6 动了 D 的两个脚本（沿用 PR#33「B 出补丁、D 审」先例）；api.md 量纲条目由 B 出稿（Task 8 Step 3 的量纲结论）。
2. **C**：`apply_version_boost` 生效时 score 为归一化排序分——弱证据阈值需按 mode/配置定标；source-priority-draft 问题 6.1 的答复见 spec §6。
3. **E/A**：标注与终版 Node 集是正式指标的前置（设计 §4.3/§7）。
