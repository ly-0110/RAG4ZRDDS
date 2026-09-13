# 第三周 B 检索实现计划（Hybrid RRF + 多来源过滤验证）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Hybrid RRF 检索（引用制融合 struct_v1+struct_bm25），构建多来源索引并完成 Metadata Filtering 与跨来源行为验证。

**Architecture:** RRF 为运行时融合层（`retrieval/rrf.py` 纯函数 + `HybridRetriever`），不建自有索引——`build_retriever` 按 `retrieval.components` 加载两个既有子索引；多来源验证通过新建 struct_multisrc_bm25/hybrid 配置 + 过滤校验脚本完成。

**Tech Stack:** Python 3.11+ · chromadb 1.5.9 · rank_bm25 · bge-m3（本地 CPU）· pytest

**Spec:** `docs/superpowers/specs/2026-09-11-week3-retrieval-design.md`（PR#27 已合并；D 已按 §6 会签①-④ 落地 components 字段/校验/跳过/不入身份段）

## Global Constraints

- 仓库根：`C:\Users\huziy\Desktop\软工实训\RAG4ZRDDS`；基线 `develop @ f4bba36`。
- 开始前建工作分支：`git checkout -b feature/hybrid-rrf`。
- **每次提交必须带身份参数**（本机未配置 git 身份）：
  `git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "..."`
- 注释/文档用中文，风格对齐既有文件（模块 docstring 写 WHY，不写 WHAT）。
- 每个新模块：`from __future__ import annotations`；类型注解完整。
- 测试命令：`python -m pytest tests/unit/<file> -v`；全量 `python -m pytest tests/unit -q`。
- 真实模型（bge-m3）CPU 加载约 1~3 分钟；**不设 `HF_ENDPOINT`**（直连，镜像必失败——见 `docs/week3-delivery-review.md` §5）。
- 已有事实（勿重建）：`struct_v1` → `indexes/struct_bge-m3_0a7830b7`（已建）；`struct_bm25` → `indexes/struct_bge-m3_677d777f`（已建）；`struct_multisrc_v1` → `indexes/struct_bge-m3_d57f695e`（**未建**，本计划建）。
- `evaluation.report.dir`/索引目录均已在 `.gitignore`（`indexes/*`）；报告 json 入库、索引不入库。
- 触及 D 域文件的小改动（`configs/experiments/README.md` 一行、`scripts/` 新增两个校验脚本）在 PR 描述里注明，供 D 会签。
- 指标协议：`expected_sources: null`（"宁缺毋滥"——标注 P0 整改前不产出循环论证指标，见 `week3-delivery-review.md` §2）；本计划不产出/不采信任何 hit_rate/mrr 数字。

---

### Task 1: RRF 融合纯函数

**Files:**
- Create: `retrieval/rrf.py`
- Test: `tests/unit/test_rrf.py`

**Interfaces:**
- Consumes: 无（纯函数，输入为既有 `[{node_id,text,metadata,score}]` 命中列表）
- Produces: `fuse_hits(hit_lists: list[list[dict]], top_k: int, k: float = 60.0) -> list[dict]`；常量 `DEFAULT_RRF_K = 60.0`。Task 2 的 `HybridRetriever` 依赖这两个符号。

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_rrf.py`：

```python
"""RRF 融合纯函数（retrieval/rrf.py）的单元测试。"""
from __future__ import annotations

import pytest

from retrieval.rrf import DEFAULT_RRF_K, fuse_hits


def hit(node_id: str, text: str = "") -> dict:
    return {"node_id": node_id, "text": text or f"{node_id} 正文",
            "metadata": {}, "score": 0.5}


def test_fuse_single_list_keeps_order_and_scores():
    fused = fuse_hits([[hit("a"), hit("b")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["a", "b"]
    assert fused[0]["score"] == pytest.approx(1 / 61, abs=1e-6)
    assert fused[1]["score"] == pytest.approx(1 / 62, abs=1e-6)


def test_fuse_consensus_node_gets_summed_ranks():
    # 两路都第 1 → 2/(k+1)；单路第 2 → 1/(k+2)
    fused = fuse_hits([[hit("a"), hit("b")], [hit("a")]], top_k=5)
    scores = {h["node_id"]: h["score"] for h in fused}
    assert [h["node_id"] for h in fused] == ["a", "b"]
    assert scores["a"] == pytest.approx(2 / 61, abs=1e-6)
    assert scores["b"] == pytest.approx(1 / 62, abs=1e-6)


def test_fuse_consensus_rank2_beats_single_path_rank1():
    # RRF 核心机制：两路第 2（2/62≈0.0323）> 单路第 1（1/61≈0.0164）
    fused = fuse_hits([[hit("solo"), hit("both")], [hit("both")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["both", "solo"]


def test_fuse_dedups_node_across_lists():
    fused = fuse_hits([[hit("a")], [hit("a")]], top_k=5)
    assert len(fused) == 1
    assert fused[0]["score"] == pytest.approx(2 / 61, abs=1e-6)


def test_fuse_top_k_truncates():
    fused = fuse_hits([[hit(str(i)) for i in range(10)]], top_k=3)
    assert [h["node_id"] for h in fused] == ["0", "1", "2"]


def test_fuse_tie_breaks_by_node_id_deterministically():
    # 完全对称（各在一路第 1，同分）→ node_id 升序，结果确定
    fused = fuse_hits([[hit("b")], [hit("a")]], top_k=5)
    assert [h["node_id"] for h in fused] == ["a", "b"]


def test_fuse_prefers_first_list_payload_when_node_in_both():
    # text/metadata 取首路（vector）——两路节点集相同时字段一致，取首路仅为确定性
    a_vec = hit("a", text="vector 路正文")
    a_bm = hit("a", text="bm25 路正文")
    fused = fuse_hits([[a_vec], [a_bm]], top_k=5)
    assert fused[0]["text"] == "vector 路正文"


def test_fuse_empty_inputs_return_empty():
    assert fuse_hits([[], []], top_k=5) == []
    assert fuse_hits([], top_k=5) == []


def test_default_rrf_k_is_60():
    assert DEFAULT_RRF_K == 60.0
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/unit/test_rrf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.rrf'`

- [ ] **Step 3: 实现**

创建 `retrieval/rrf.py`：

```python
"""RRF（Reciprocal Rank Fusion）融合 —— hybrid 检索的排名合并层。

score(node) = Σ_路 1/(rrf_k + rank_路(node))，rank 从 1 起（k 经典值 60）。
输入为各路已按相关度降序的命中列表（[{node_id,text,metadata,score},...]），
输出按融合分降序的 top_k；同分按 node_id 升序定序（确定性，避免并列抖动）。

text/metadata 取首个含该节点的路——hybrid 的 components 契约保证两路为同一
节点集（build_retriever 加载时校验），字段内容一致。RRF 分与两路子检索的
原始分（cosine 0~1 / BM25 无上界）量纲不同，仅用于本层排序，跨模式比较
无意义（沿用 bm25.py 既有约定；日志 score 字段无需改）。
"""
from __future__ import annotations

DEFAULT_RRF_K = 60.0


def fuse_hits(
    hit_lists: list[list[dict]], top_k: int, k: float = DEFAULT_RRF_K
) -> list[dict]:
    """多路命中 → RRF 融合排序；hit_lists 按「路」组织，每路内部已排序。"""
    scores: dict[str, float] = {}
    source_hit: dict[str, dict] = {}
    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            node_id = hit["node_id"]
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (k + rank)
            source_hit.setdefault(node_id, hit)
    ranked = sorted(scores, key=lambda nid: (-scores[nid], nid))[:top_k]
    return [{**source_hit[nid], "score": round(scores[nid], 6)} for nid in ranked]
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/unit/test_rrf.py -v`
Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add retrieval/rrf.py tests/unit/test_rrf.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): RRF 融合纯函数 fuse_hits（PR#27 设计 §2.3）"
```

---

### Task 2: HybridRetriever + build_retriever 分发

**Files:**
- Modify: `retrieval/retriever.py`（新增 `HybridRetriever` 类；`build_retriever` 增加 hybrid 分支；更新 unsupported-mode 报错文案）
- Modify: `tests/unit/test_retrieval.py`（`_write_config` 支持 hybrid_rerank；重写 `test_build_retriever_rejects_unsupported_mode`）
- Test: `tests/unit/test_hybrid_retriever.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `fuse_hits` / `DEFAULT_RRF_K`；D 的 `experiment_config.experiment_yaml_path(name) -> Path`、`RetrievalCfg.components: dict[str,str] | None`（均已在上游）。
- Produces: `HybridRetriever(vector_store, bm25_store, rrf_k=..., candidate_top_k=..., filters=None)`，`async retrieve(question, top_k) -> list[dict]`（同 `VectorRetriever` 契约）；`build_retriever` 对 `mode=hybrid` 返回 `HybridRetriever`。构建期校验：components 必须含 vector+bm25 两角色；两组件 `nodes_path` 必须一致；两子索引目录必须存在。

- [ ] **Step 1: 写失败测试（新建 test_hybrid_retriever.py）**

```python
"""Hybrid RRF 检索通路（HybridRetriever / build_retriever 分发）单元测试。

组件索引在 tmp 侧真实构建（chroma 落盘 + bm25.json），嵌入用确定性假向量，
不依赖 bge-m3；hybrid 引用制的节点集一致性由 build_retriever 加载时校验。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from retrieval._bootstrap import experiment_config
from retrieval.index import build_index
from retrieval.retriever import HybridRetriever, build_retriever


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]], dim: int = 4):
        self.vectors = vectors
        self.dim = dim

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors.get(t, [0.0] * self.dim) for t in texts]


COMPONENT_TEMPLATE = """schema_version: 1
experiment:
  name: {name}
  stage: ablation
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"
chunking:
  method: {method}
  version: v1
embedding:
  provider: local
  model: bge-m3
retrieval:
  mode: {mode}
  top_k: 5
"""

HYBRID_TEMPLATE = """schema_version: 1
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
  mode: hybrid
  top_k: 5
  candidate_top_k: 30
  params: {{rrf_k: 60}}
  components: {{vector: {vec}, bm25: {bm}}}
"""

NODES = [
    {"node_id": "n_a", "text": "alpha 连接说明",
     "metadata": {"source_type": "pdf", "version": "2.0", "source_id": "user_manual"}},
    {"node_id": "n_b", "text": "alpha alpha 重复词条",
     "metadata": {"source_type": "html", "version": "2.4", "source_id": "zrdds_dev_guide"}},
    {"node_id": "n_c", "text": "gamma 仅向量相关",
     "metadata": {"source_type": "pdf", "version": "2.0", "source_id": "user_manual"}},
]
VECTORS = {
    "alpha 连接说明": [1.0, 0.0, 0.0, 0.0],
    "alpha alpha 重复词条": [0.8, 0.6, 0.0, 0.0],
    "gamma 仅向量相关": [0.5, 0.5, 0.5, 0.5],
    "alpha 连接": [1.0, 0.0, 0.0, 0.0],
}


def _write_component(tmp_path: Path, name: str, mode: str, method: str = "struct") -> Path:
    d = tmp_path / "configs" / "experiments"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.yaml"
    p.write_text(COMPONENT_TEMPLATE.format(name=name, mode=mode, method=method),
                 encoding="utf-8")
    return p


def _write_hybrid(tmp_path: Path, vec: str, bm: str, name: str = "usage_hybrid") -> Path:
    d = tmp_path / "configs" / "experiments"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.yaml"
    p.write_text(HYBRID_TEMPLATE.format(name=name, vec=vec, bm=bm), encoding="utf-8")
    return p


def _write_nodes(tmp_path: Path, cfg) -> None:
    p = experiment_config.nodes_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in NODES) + "\n",
                 encoding="utf-8")


def _setup(tmp_path, monkeypatch, bm_method: str = "struct"):
    """tmp 隔离：写 2 个组件配置 + 节点文件 + 构建两个组件索引。"""
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    _write_component(tmp_path, "comp_vec_v1", "vector")
    _write_component(tmp_path, "comp_bm25_v1", "bm25", method=bm_method)
    fake = FakeEmbedder(VECTORS)
    vec_cfg = experiment_config.load(tmp_path / "configs" / "experiments" / "comp_vec_v1.yaml")
    _write_nodes(tmp_path, vec_cfg)
    build_index(vec_cfg, embed_fn=fake)
    bm_cfg = experiment_config.load(tmp_path / "configs" / "experiments" / "comp_bm25_v1.yaml")
    _write_nodes(tmp_path, bm_cfg)   # method 不同时落在不同路径，需各自有节点文件
    build_index(bm_cfg, embed_fn=fake)
    return fake


def test_hybrid_retriever_fuses_two_paths_with_consensus_priority(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    retriever = build_retriever(cfg, embed_fn=fake)
    assert isinstance(retriever, HybridRetriever)
    results = asyncio.run(retriever.retrieve("alpha 连接", top_k=5))

    # 向量路：n_a(1) n_b(2) n_c(3)；bm25 路（两词面命中）：n_a(1) n_b(2)
    # RRF：n_a=2/61，n_b=2/62，n_c=1/63 → n_b（共识第2）压过 n_c（单路第3）
    assert [r["node_id"] for r in results] == ["n_a", "n_b", "n_c"]
    scores = {r["node_id"]: r["score"] for r in results}
    assert scores["n_a"] == pytest.approx(2 / 61, abs=1e-5)
    assert scores["n_b"] == pytest.approx(2 / 62, abs=1e-5)
    assert scores["n_b"] > scores["n_c"]


def test_hybrid_retriever_pushes_filters_to_both_paths(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))
    probe = cfg.model_copy(deep=True)
    probe.retrieval.filters = {"source_type": "html"}

    retriever = build_retriever(probe, embed_fn=fake)
    results = asyncio.run(retriever.retrieve("alpha 连接", top_k=5))

    # n_a/n_b 词面与向量都命中，但 n_a 是 pdf 被两侧过滤；只剩 n_b
    assert [r["node_id"] for r in results] == ["n_b"]


def test_hybrid_retriever_honors_top_k(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))
    retriever = build_retriever(cfg, embed_fn=fake)
    assert len(asyncio.run(retriever.retrieve("alpha 连接", top_k=2))) == 2


def test_hybrid_requires_both_role_keys(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))
    bad = cfg.model_copy(deep=True)
    bad.retrieval.components = {"vector": "comp_vec_v1"}

    with pytest.raises(ValueError, match="bm25"):
        build_retriever(bad, embed_fn=FakeEmbedder(VECTORS))


def test_hybrid_rejects_mismatched_node_sets(tmp_path, monkeypatch):
    # bm25 组件用不同 chunking（fixed/v1）→ nodes_path 不同 → 拒绝
    fake = _setup(tmp_path, monkeypatch, bm_method="fixed")
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(ValueError, match="节点集"):
        build_retriever(cfg, embed_fn=fake)


def test_hybrid_missing_subindex_raises_with_build_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    _write_component(tmp_path, "comp_vec_v1", "vector")
    _write_component(tmp_path, "comp_bm25_v1", "bm25")
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(FileNotFoundError, match="make index"):
        build_retriever(cfg, embed_fn=FakeEmbedder(VECTORS))
```

说明：`test_hybrid_missing_subindex_raises_with_build_hint` 故意只写配置、不建索引、不写节点（build_retriever 在索引存在性检查处即拒绝，不触碰节点文件）。`fixed/v1` 组件测试中两个组件的节点文件与索引都会各自建好，误配在 `build_retriever` 的节点集一致性检查处被拒。（`build_index` 对 hybrid 的防护测试在 Task 3 追加——先写会破坏本任务「全绿」预期。）

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/unit/test_hybrid_retriever.py -v`
Expected: FAIL — `ImportError: cannot import name 'HybridRetriever'`

- [ ] **Step 3: 实现 retriever.py 改动**

3a. 文件头 import 追加：

```python
from retrieval.rrf import DEFAULT_RRF_K, fuse_hits
```

3b. 在 `BM25Retriever` 类之后新增：

```python
class HybridRetriever:
    """vector + bm25 两路候选 → RRF 融合（引用制：无自有索引，PR#27 设计 §2）。"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        rrf_k: float = DEFAULT_RRF_K,
        candidate_top_k: int = 30,
        filters: dict | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._rrf_k = rrf_k
        self._candidate_top_k = candidate_top_k
        self._filters = filters

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        # 子检索各取候选池；top_k 大于池容量时以 top_k 兜底（防融合池不足）
        sub_k = max(top_k, self._candidate_top_k)
        vec_hits = self._vector_store.query(question, sub_k, filters=self._filters)
        bm_hits = self._bm25_store.query(question, sub_k, filters=self._filters)
        fused = fuse_hits([vec_hits, bm_hits], top_k=top_k, k=self._rrf_k)
        return [_to_source_ref(r) for r in fused]
```

3c. `build_retriever` 在 bm25 分支之后、`mode != "vector"` 判断之前插入 hybrid 分支：

```python
    if cfg.retrieval.mode == "hybrid":
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
        bm25_store = BM25Store.load(bm25_path)
        rrf_k = float((cfg.retrieval.params or {}).get("rrf_k", DEFAULT_RRF_K))
        return HybridRetriever(
            vector_store,
            bm25_store,
            rrf_k=rrf_k,
            candidate_top_k=cfg.retrieval.candidate_top_k,
            filters=cfg.retrieval.filters or None,
        )
```

3d. 更新 unsupported-mode 文案（原"当前支持 vector/bm25 检索…hybrid/hybrid_rerank 待后续周次实现"）：

```python
    if cfg.retrieval.mode != "vector":
        raise NotImplementedError(
            f"当前支持 vector/bm25/hybrid 检索，收到 mode={cfg.retrieval.mode!r}"
            "（hybrid_rerank 待第四周实现）"
        )
```

- [ ] **Step 4: 更新旧测试（tests/unit/test_retrieval.py）**

4a. `_write_config` 的 components 块逻辑替换为：

```python
    components_block = ""
    if retrieval_mode == "hybrid":
        components_block = "\n  components: {vector: baseline_v1, bm25: baseline_v1}"
    elif retrieval_mode == "hybrid_rerank":
        components_block = "\n  rerank_model: bge-reranker-v2-m3"
```

4b. `test_build_retriever_rejects_unsupported_mode` 整体替换为（不再需要自引用配置——hybrid 已实现，改测 hybrid_rerank）：

```python
def test_build_retriever_rejects_unsupported_mode(tmp_path, monkeypatch):
    # hybrid 已实现（PR#27 设计 §2）；此处锁定 hybrid_rerank 仍被明确拒绝
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path, retrieval_mode="hybrid_rerank"))

    with pytest.raises(NotImplementedError, match="hybrid_rerank"):
        build_retriever(cfg, embed_fn=FakeEmbedder({}))
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/unit/test_hybrid_retriever.py tests/unit/test_retrieval.py -v`
Expected: 全部通过（含更新后的 reject 测试）

- [ ] **Step 6: 全量回归**

Run: `python -m pytest tests/unit -q`
Expected: 全绿（无既有测试因分发改动破坏）

- [ ] **Step 7: 提交**

```bash
git add retrieval/retriever.py tests/unit/test_hybrid_retriever.py tests/unit/test_retrieval.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): HybridRetriever + build_retriever 引用制分发（PR#27 设计 §2.2/§2.3）"
```

---

### Task 3: build_index 对 hybrid 的防护

**Files:**
- Modify: `retrieval/index.py`（`build_index` 顶部加 hybrid 防护）
- Test: `tests/unit/test_hybrid_retriever.py`（追加一个测试）

**Interfaces:**
- Consumes: Task 2 的 hybrid 配置测试夹具。
- Produces: `retrieval.index.build_index(cfg)` 对 `mode=hybrid` 抛 `ValueError`（消息含「引用制」）；D 的 `scripts/build_index.py` 已在调用前短路（打印子索引提示），本防护只拦程序化误用。

- [ ] **Step 1: 追加失败测试**

在 `tests/unit/test_hybrid_retriever.py` 末尾追加：

```python
def test_build_index_rejects_hybrid_reference_mode(tmp_path, monkeypatch):
    fake = _setup(tmp_path, monkeypatch)
    cfg = experiment_config.load(_write_hybrid(tmp_path, "comp_vec_v1", "comp_bm25_v1"))

    with pytest.raises(ValueError, match="引用制"):
        build_index(cfg, embed_fn=fake)
```

Run: `python -m pytest tests/unit/test_hybrid_retriever.py::test_build_index_rejects_hybrid_reference_mode -v`
Expected: FAIL（当前会走 vector 通路尝试建索引，不抛 ValueError）

- [ ] **Step 2: 实现**

`retrieval/index.py` 的 `build_index` 函数体第一行（`nodes_file = ...` 之前）插入：

```python
    if cfg.retrieval.mode == "hybrid":
        # 引用制无自有索引（PR#27 设计 §2.2）：子索引由各自配置管；
        # scripts/build_index.py 已提前短路，此处拦程序化误用
        raise ValueError(
            "hybrid 为引用制、无自有索引：请分别构建 components 引用的子配置"
            "（make index CFG=configs/experiments/<子实验>.yaml）"
        )
```

- [ ] **Step 3: 运行确认通过**

Run: `python -m pytest tests/unit/test_hybrid_retriever.py -v`
Expected: 全通过

- [ ] **Step 4: 提交**

```bash
git add retrieval/index.py tests/unit/test_hybrid_retriever.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(retrieval): build_index 拦截 hybrid 引用制误用"
```

---

### Task 4: struct_hybrid 配置 + 跳过提示冒烟

**Files:**
- Create: `configs/experiments/struct_hybrid.yaml`
- Modify: `configs/experiments/README.md`（`candidate_top_k` 一行，D 域，PR 注明）

**Interfaces:**
- Consumes: D 的 `components` 字段与 README（已就绪）；Task 2 的分发实现。
- Produces: 可被 `run_experiment`/`build_retriever` 消费的 `struct_hybrid` 实验配置；Task 5 使用。

- [ ] **Step 1: 创建配置**

创建 `configs/experiments/struct_hybrid.yaml`：

```yaml
# =====================================================================
# RAG4ZRDDS 实验配置 · 第三周 Hybrid RRF 初版（struct_hybrid）
# 引用制（PR#27 设计 §2）：无自有索引，components 引用 struct_v1(vector)
# 与 struct_bm25(bm25) 两个既有索引，RRF 运行时融合——零重建。
#   * build_index 对 hybrid 自动跳过（子索引由各自配置构建）
#   * rrf_k 放 retrieval.params（B 自由区）：score = Σ 1/(rrf_k + rank)
#   * 本实验为第四周正式对比热身；指标待 E 真值标注定稿后补
#     （宁缺毋滥：标注 P0 整改前 expected_sources 置 null）
# =====================================================================
schema_version: 1

experiment:
  name: struct_hybrid
  description: 第三周 Hybrid RRF 初版：struct_v1(向量) + struct_bm25(词袋) 引用融合
  stage: ablation

sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"

ingest:
  cleaned_output: data/cleaned/pages.jsonl
  quality_check: true

chunking:                          # 与 struct_v1/struct_bm25 完全一致（同一节点集）
  method: struct
  version: v1
  params:
    max_chunk_chars: 2500
    overlap_chars: 200
    large_section_thresh: 2500

embedding:                         # 与 struct_v1 一致（向量路消费；hybrid 命名沿用）
  provider: local
  model: bge-m3
  batch_size: 32
  device: cpu

index:
  backend: chroma
  metric: cosine

retrieval:
  mode: hybrid
  top_k: 5
  candidate_top_k: 30              # 两路子检索各取条数（融合粗取池）
  filters: {}
  params:
    rrf_k: 60                      # RRF 常数（经典值 60）
  components:                      # 引用制：实验名 → configs/experiments/<名>.yaml
    vector: struct_v1
    bm25: struct_bm25

generation:
  enabled: false                   # 热身只验检索路径，不跑生成（省 LLM 配额）
  prompt_version: v0
  llm_env_prefix: LLM_

evaluation:
  dataset: evaluation/datasets/questions.jsonl
  expected_sources: null           # 宁缺毋滥（D 协议）：标注整改前不产出循环论证指标
  retrieval_metrics: [hit_rate@5, mrr@5]
  response_metrics: []
  sample_size: null

report:
  dir: evaluation/reports
  compare_baseline: struct_v1      # 单来源基线对照（热身期指标为空，仅记录检索明细）
```

- [ ] **Step 2: 更新 README 一行（D 域）**

`configs/experiments/README.md` 中 `candidate_top_k` 行改为：

```
| `candidate_top_k` | 粗取候选数 | `hybrid`=两路子检索各取条数 / `hybrid_rerank`=精排前粗取条数（必须 ≥ top_k，典型 30 → 5） |
```

- [ ] **Step 3: 配置校验**

Run: `python scripts/experiment_config.py configs/experiments/struct_hybrid.yaml`
Expected: `[配置有效]`，检索 `mode=hybrid`，无报错（components 引用的两个 yaml 均存在）

- [ ] **Step 4: 跳过提示冒烟**

Run: `python scripts/build_index.py --config configs/experiments/struct_hybrid.yaml`
Expected: 打印「mode=hybrid 无自有索引（引用制…）」并列出两个子索引路径（`struct_bge-m3_0a7830b7`、`struct_bge-m3_677d777f`），退出码 0，**不产出任何索引目录**

- [ ] **Step 5: 提交**

```bash
git add configs/experiments/struct_hybrid.yaml configs/experiments/README.md
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(configs): struct_hybrid 实验配置（Hybrid RRF 引用制）+ README candidate_top_k 语义（D 域一行）"
```

---

### Task 5: struct_hybrid 真实索引跑通（检索热身）

**Files:**
- Create: `evaluation/reports/struct_hybrid.json`（run_experiment 产出后提交）

**Interfaces:**
- Consumes: Task 4 的配置；本地已建的 `struct_v1`/`struct_bm25` 索引；真实 bge-m3。
- Produces: hybrid 全链路的端到端证据（120 题检索明细报告）；无指标（expected_sources null，`evaluated: 0` 属预期）。

- [ ] **Step 1: 单题探针（先小后大）**

Run:
```bash
python -X utf8 -c "
import asyncio, sys
sys.path.insert(0, '.')
from retrieval._bootstrap import experiment_config as ec
from retrieval.retriever import build_retriever
cfg = ec.load('configs/experiments/struct_hybrid.yaml')
r = build_retriever(cfg)
for h in asyncio.run(r.retrieve('如何创建 DataWriter？', top_k=5)):
    print(h['node_id'][:48], '|', h['source_id'], '|', h['score'])
"
```
Expected: 打印 5 条结果，score 为 RRF 分（0.01~0.033 区间，双路共识者靠前）；首次运行含模型加载 1~3 分钟。

- [ ] **Step 2: 全量实验（120 题检索）**

Run: `python scripts/run_experiment.py --config configs/experiments/struct_hybrid.yaml`
Expected: 打印子索引复用信息（`_ensure_hybrid_subindexes`）；产出 `evaluation/reports/struct_hybrid.json`；`dataset.evaluated == 0`、`metrics` 全 null（expected_sources null 属预期）；`per_question` 120 条、每条 `retrieved` 5 条且 note 为「无期望来源标注（不计入指标分母）」。耗时约 10~20 分钟（含模型加载）。

- [ ] **Step 3: 检查报告内容**

Run:
```bash
python -X utf8 -c "
import json
r = json.load(open('evaluation/reports/struct_hybrid.json', encoding='utf-8'))
print('mode:', r['retrieval']['mode'])
print('evaluated:', r['dataset']['evaluated'], '/', r['dataset']['total'])
pq = r['per_question'][0]
print('per_question:', len(r['per_question']), '首题 retrieved:', len(pq['retrieved']))
print('score 样例:', [x['score'] for x in pq['retrieved']])
"
```
Expected: `mode: hybrid`；`evaluated: 0 / 120`；`per_question: 120`；score 在 RRF 量纲区间。

- [ ] **Step 4: 提交**

```bash
git add evaluation/reports/struct_hybrid.json
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(evaluation): struct_hybrid 120 题检索跑通报告（热身，无指标——expected_sources 宁缺毋滥）"
```

---

### Task 6: 多来源三件套配置 + 索引构建

**Files:**
- Create: `configs/experiments/struct_multisrc_bm25.yaml`
- Create: `configs/experiments/struct_multisrc_hybrid.yaml`

**Interfaces:**
- Consumes: 上游已有的 `struct_multisrc_v1.yaml`（PDF 2.0 + HTML 2.4 多来源基线，mode=vector，hash8=d57f695e，本地**未建**索引）。
- Produces: `struct_multisrc_bm25`（bm25 索引秒级建成）与 `struct_multisrc_hybrid`（引用前两者）配置；Task 7/8 的验证对象。多来源向量索引构建（~30-60 分钟）在 Task 7 期间后台进行。

- [ ] **Step 1: 创建 struct_multisrc_bm25.yaml**

```yaml
# =====================================================================
# RAG4ZRDDS 实验配置 · 第三周多来源对照（struct_multisrc_bm25）
# 与 struct_multisrc_v1 同节点集（PDF 2.0 + HTML 2.4 合并 1606 块），
# 检索方式换为 BM25 词袋——“同分块、异检索”对照。
# =====================================================================
schema_version: 1

experiment:
  name: struct_multisrc_bm25
  description: 第三周多来源对照：struct 分块 × (用户手册 PDF 2.0 + Doxygen HTML 2.4) × BM25 词袋检索
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

chunking:
  method: struct
  version: v1
  params:
    max_chunk_chars: 2500
    overlap_chars: 200
    large_section_thresh: 2500

embedding:                         # bm25 不消费；命名/校验需要保留
  provider: local
  model: bge-m3
  batch_size: 32
  device: cpu

index:
  backend: chroma                  # bm25 实际落 bm25.json，backend/metric 仅参与命名
  metric: cosine

retrieval:
  mode: bm25
  top_k: 5
  candidate_top_k: 30
  filters: {}
  source_priority: []
  params:
    k1: 1.5
    b: 0.75

generation:
  enabled: false
  prompt_version: v0
  llm_env_prefix: LLM_

evaluation:
  dataset: evaluation/datasets/questions.jsonl
  expected_sources: null           # 宁缺毋滥（同 struct_multisrc_v1 协议）
  retrieval_metrics: [hit_rate@5, mrr@5]
  response_metrics: []
  sample_size: null

report:
  dir: evaluation/reports
  compare_baseline: struct_multisrc_v1
```

- [ ] **Step 2: 创建 struct_multisrc_hybrid.yaml**

```yaml
# =====================================================================
# RAG4ZRDDS 实验配置 · 第三周多来源 Hybrid RRF（struct_multisrc_hybrid）
# 引用制：components 引用 struct_multisrc_v1(vector) 与
# struct_multisrc_bm25(bm25)，RRF 运行时融合——跨来源检索的融合基线。
# =====================================================================
schema_version: 1

experiment:
  name: struct_multisrc_hybrid
  description: 第三周多来源 Hybrid：struct_multisrc_v1(向量) + struct_multisrc_bm25(词袋) 引用融合
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
  mode: hybrid
  top_k: 5
  candidate_top_k: 30
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
  expected_sources: null
  retrieval_metrics: [hit_rate@5, mrr@5]
  response_metrics: []
  sample_size: null

report:
  dir: evaluation/reports
  compare_baseline: struct_multisrc_v1
```

- [ ] **Step 3: 两个配置校验**

Run:
```bash
python scripts/experiment_config.py configs/experiments/struct_multisrc_bm25.yaml
python scripts/experiment_config.py configs/experiments/struct_multisrc_hybrid.yaml
```
Expected: 两个都 `[配置有效]`；hybrid 的 Node 集为 `struct_v1__b95d1061.jsonl [存在]`

- [ ] **Step 4: 构建多来源 bm25 索引（秒级）**

Run: `python scripts/build_index.py --config configs/experiments/struct_multisrc_bm25.yaml`
Expected: 完成，`indexes/struct_bge-m3_<hash>/bm25.json` + manifest（nodes=1606）

- [ ] **Step 5: 后台启动多来源向量索引构建（~30-60 分钟）**

Run（后台执行，不要阻塞后续任务）:
```bash
python scripts/build_index.py --config configs/experiments/struct_multisrc_v1.yaml
```
Expected: 打印 10~15 分钟级耗时警告与 30s 心跳；完成后 `indexes/struct_bge-m3_d57f695e/` 出现 manifest + chroma 段文件。**Task 7 编码期间并行等待，Task 8 前必须确认完成。**

- [ ] **Step 6: 提交配置**

```bash
git add configs/experiments/struct_multisrc_bm25.yaml configs/experiments/struct_multisrc_hybrid.yaml
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(configs): 多来源 bm25/hybrid 实验配置（引用 struct_multisrc_v1 双路）"
```

---

### Task 7: 过滤验证（合成 parity 测试 + verify_filters 脚本）

**Files:**
- Create: `tests/unit/test_multisource_filters.py`
- Create: `scripts/verify_filters.py`（D 域目录，PR 注明）
- Create: `tests/unit/test_rrf.py` 已在 Task 1；本任务无其他依赖

**Interfaces:**
- Consumes: Task 6 的 `struct_multisrc_bm25` 索引（真实 bm25 合规测试）；Task 2 的 HybridRetriever；`retrieval.nodes.load_nodes`（元数据真值）。
- Produces: 三模式过滤语义对齐的合成测试；`scripts/verify_filters.py --config <yaml>`（真实索引合规校验脚本，退出码 0/1）。

- [ ] **Step 1: 合成 parity 测试（失败先行）**

创建 `tests/unit/test_multisource_filters.py`：

```python
"""多来源 metadata 过滤验证：合成数据三模式语义对齐 + 真实索引合规。

合成部分不依赖模型（FakeEmbedder + 内存 chroma）；
真实部分对本地已建的多来源索引做「结果节点 ⊆ 元数据真值」合规校验
（bm25 通路无模型依赖；vector/hybrid 通路的真实验证在
scripts/verify_filters.py 中以真实模型执行）。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest

from retrieval._bootstrap import experiment_config
from retrieval.bm25 import BM25Store
from retrieval.nodes import NodeRecord, load_nodes
from retrieval.retriever import HybridRetriever
from retrieval.vector_store import VectorStore

MIXED_NODES = [
    NodeRecord("p1", "gamma 连接失败排查", {"source_type": "pdf", "version": "2.0",
                                          "source_id": "user_manual"}),
    NodeRecord("p2", "delta 安装步骤", {"source_type": "pdf", "version": "2.0",
                                       "source_id": "user_manual"}),
    NodeRecord("h1", "gamma create_datawriter 参数", {"source_type": "html", "version": "2.4",
                                                     "source_id": "zrdds_dev_guide"}),
    NodeRecord("h2", "delta 版本兼容说明", {"source_type": "html", "version": "2.4",
                                          "source_id": "zrdds_dev_guide"}),
]
VECS = {
    "gamma 连接失败排查": [1.0, 0.0, 0.0, 0.0],
    "delta 安装步骤": [0.0, 1.0, 0.0, 0.0],
    "gamma create_datawriter 参数": [0.9, 0.1, 0.0, 0.0],
    "delta 版本兼容说明": [0.1, 0.9, 0.0, 0.0],
    "gamma 查询": [1.0, 0.0, 0.0, 0.0],
    "delta 查询": [0.0, 1.0, 0.0, 0.0],
}


def _fake(texts):
    return [VECS.get(t, [0.0, 0.0, 0.0, 1.0]) for t in texts]


def _stores():
    vec = VectorStore(embed_fn=_fake, collection_name=f"filt_{uuid.uuid4().hex}")
    vec.add_nodes(MIXED_NODES)
    bm = BM25Store()
    bm.add_nodes(MIXED_NODES)
    return vec, bm


def _allowed(filt: dict) -> set[str]:
    return {n.node_id for n in MIXED_NODES
            if all(n.metadata.get(k) == v for k, v in filt.items())}


FILTER_CASES = [
    ({"source_type": "pdf"}, "gamma 查询"),
    ({"source_type": "html"}, "gamma 查询"),
    ({"version": "2.4"}, "delta 查询"),
    ({"source_type": "html", "version": "2.4"}, "delta 查询"),
]


@pytest.mark.parametrize("filt,question", FILTER_CASES)
def test_filter_semantics_identical_across_three_modes(filt, question):
    vec, bm = _stores()
    hybrid = HybridRetriever(vec, bm)
    allowed = _allowed(filt)

    vec_ids = {r["node_id"] for r in vec.query(question, 10, filters=filt)}
    bm_ids = {r["node_id"] for r in bm.query(question, 10, filters=filt)}
    hy_ids = {r["node_id"] for r in asyncio.run(hybrid.retrieve(question, top_k=10))}

    for name, ids in (("vector", vec_ids), ("bm25", bm_ids), ("hybrid", hy_ids)):
        assert ids <= allowed, f"{name} 返回越界节点: {ids - allowed}"
    # 至少要能命中允许集内的词面相关节点（防空结果掩盖过滤失效）
    assert bm_ids and vec_ids, f"{filt} 下两路均空，过滤可能过度"


def test_filter_matching_nothing_returns_empty_in_all_modes():
    vec, bm = _stores()
    filt = {"source_type": "html", "version": "2.0"}  # 无此组合
    assert vec.query("gamma 查询", 10, filters=filt) == []
    assert bm.query("gamma 查询", 10, filters=filt) == []
    hybrid = HybridRetriever(vec, bm)
    assert asyncio.run(hybrid.retrieve("gamma 查询", top_k=10)) == []


def test_real_multisrc_bm25_filter_compliance():
    # 需本地已建多来源 bm25 索引（Task 6 构建）；否则跳过。
    # 直接对 BM25 产物查（无模型依赖）：结果 metadata 必须满足过滤约束，
    # 且索引确实含两种来源（合成索引无法暴露的分来源口径问题在此兜底）。
    cfg = experiment_config.load(
        Path(__file__).resolve().parents[2] / "configs" / "experiments" / "struct_multisrc_bm25.yaml")
    p = experiment_config.index_dir(cfg)
    if not p.exists():
        pytest.skip("多来源 bm25 索引未构建（先 make index CFG=struct_multisrc_bm25.yaml）")

    store = BM25Store.load(p)
    source_types = {n.metadata.get("source_type") for n in store._nodes}
    assert source_types == {"pdf", "html"}, "索引未真正混合两种来源"

    probes = ["产品如何安装？", "create_datawriter() 的参数是什么？", "QoS 策略配置"]
    for filt, expect in (({"source_type": "pdf"}, "pdf"),
                         ({"source_type": "html"}, "html"),
                         ({"version": "2.4"}, "2.4")):
        hits = 0
        for q in probes:
            for r in store.query(q, 5, filters=filt):
                hits += 1
                if "source_type" in filt:
                    assert r["metadata"].get("source_type") == expect
                if "version" in filt:
                    assert r["metadata"].get("version") == expect
        assert hits > 0, f"{filt} 全部探针零命中——过滤口径或元数据可能不对齐"
```

- [ ] **Step 2: 运行合成/真实测试**

Run: `python -m pytest tests/unit/test_multisource_filters.py -v`
Expected: 合成用例通过；`test_real_multisrc_bm25_filter_compliance` 在 bm25 索引已建（Task 6）时通过（若索引缺失则 skip，构建后重跑）

- [ ] **Step 3: 编写 verify_filters.py**

创建 `scripts/verify_filters.py`：

```python
#!/usr/bin/env python3
"""scripts/verify_filters.py — 多来源索引 metadata 过滤全量校验（B 域，PR#27 设计 §3.2-2）

对指定实验配置，用内置过滤集 × 探针问题执行检索，校验每条结果的 node_id
属于「按 nodes jsonl 元数据真值过滤后的允许集」——对照真值而非依赖 store
自查。全空命中会单独提示（最常见的失败信号：过滤口径/元数据不对齐）。

用法:
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_bm25.yaml    # 无需模型
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_v1.yaml      # 需 bge-m3
  python scripts/verify_filters.py --config configs/experiments/struct_multisrc_hybrid.yaml  # 需 bge-m3

退出码：0=全部通过；1=存在违规。
依赖: retrieval/*（B）· 目标索引已构建
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from retrieval._bootstrap import experiment_config as ec  # noqa: E402
from retrieval.nodes import load_nodes  # noqa: E402

PROBES = [
    "产品如何安装？",
    "create_datawriter() 的参数是什么？",
    "用户手册里的设备连接功能在 Java SDK 中如何实现？",
    "v2.4 的 API 是否仍使用旧参数？",
    "如何配置 QoS 策略？",
]
FILTER_SETS = [
    {"source_type": "pdf"},
    {"source_type": "html"},
    {"version": "2.4"},
    {"source_type": "html", "version": "2.4"},
]


def _nodes_of(cfg):
    """检索器消费的节点集（hybrid 取 vector 组件——两路同节点集已由构建期校验）。"""
    if cfg.retrieval.mode == "hybrid":
        ref = ec.load(ec.experiment_yaml_path(cfg.retrieval.components["vector"]))
    else:
        ref = cfg
    return load_nodes(ec.nodes_path(ref))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="verify_filters", description=__doc__)
    ap.add_argument("--config", required=True, help="实验配置 yaml")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args(argv)

    from retrieval.retriever import build_retriever

    cfg = ec.load(args.config)
    nodes = _nodes_of(cfg)
    embed_fn = None
    if cfg.retrieval.mode == "vector":
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(cfg)
    elif cfg.retrieval.mode == "hybrid":
        from retrieval.embeddings import build_embedding

        embed_fn = build_embedding(ec.load(
            ec.experiment_yaml_path(cfg.retrieval.components["vector"])))

    print(f"[verify] {args.config} mode={cfg.retrieval.mode} 节点数={len(nodes)}")
    violations = 0
    for filt in FILTER_SETS:
        allowed = {n.node_id for n in nodes
                   if all(n.metadata.get(k) == v for k, v in filt.items())}
        probe_cfg = cfg.model_copy(deep=True)
        probe_cfg.retrieval.filters = filt
        retriever = build_retriever(probe_cfg, embed_fn=embed_fn)
        print(f"[verify] filters={filt} 真值允许 {len(allowed)} 节点")
        hits_total = 0
        for q in PROBES:
            refs = asyncio.run(retriever.retrieve(q, top_k=args.top_k))
            hits_total += len(refs)
            bad = [r["node_id"] for r in refs if r["node_id"] not in allowed]
            violations += len(bad)
            tag = "OK" if not bad else "违规"
            note = f"  越界: {bad[:3]}" if bad else ""
            print(f"  [{tag}] {q}  命中 {len(refs)} 条{note}")
        if hits_total == 0:
            print("  [警告] 该过滤集全部探针零命中——口径或元数据可能不对齐")
    if violations:
        print(f"[verify] 失败：{violations} 条结果越界")
        return 1
    print("[verify] 通过：全部结果满足过滤约束")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑 bm25 真实校验（无需模型）**

Run: `python scripts/verify_filters.py --config configs/experiments/struct_multisrc_bm25.yaml`
Expected: 4 个过滤集全部 `OK`；`{source_type: pdf}` 与 `{source_type: html}` 命中数 > 0；退出码 0

- [ ] **Step 5: 等 Task 6 的向量索引构建完成后跑 vector + hybrid 校验（需模型）**

Run:
```bash
python scripts/verify_filters.py --config configs/experiments/struct_multisrc_v1.yaml
python scripts/verify_filters.py --config configs/experiments/struct_multisrc_hybrid.yaml
```
Expected: 两个都「通过」；hybrid 的输出与 vector/bm25 在相同过滤集下结果集一致（RRF 融合不改变过滤边界）
注：若 chroma 对同路径多客户端句柄报错，改为每次过滤集构造新进程运行（`--filters` 循环外置为 shell for 循环），并将现象记录进 PR。

- [ ] **Step 6: 全量回归 + 提交**

Run: `python -m pytest tests/unit -q`
Expected: 全绿

```bash
git add tests/unit/test_multisource_filters.py scripts/verify_filters.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "test(retrieval): 过滤语义三模式对齐 + verify_filters 真值合规脚本（PR#27 设计 §3.2/§3.3）"
```

---

### Task 8: 跨来源冒烟（§7.5 A/B/C/D 四场景）

**Files:**
- Create: `scripts/smoke_cross_source.py`（D 域目录，PR 注明）

**Interfaces:**
- Consumes: Task 6 的 `struct_multisrc_hybrid` 配置与索引；真实 bge-m3。
- Produces: 四场景 top-5 来源/版本分布的人工对照输出（**不落盘、不进正式报告**——正式评测等 E 题集 + C 口径）。

- [ ] **Step 1: 编写脚本**

创建 `scripts/smoke_cross_source.py`：

```python
#!/usr/bin/env python3
"""scripts/smoke_cross_source.py — §7.5 A/B/C/D 四场景跨来源冒烟（B 域，PR#27 设计 §4.3）

对指定实验配置跑指南 §7.5 的 4 个样例问题，打印 top-k 的来源/版本/章节分布，
供人工对照「理想结果」表。结果只作开发参考、不进正式报告（正式评测等 E 题集
重新标注 + C 判对口径会签）。

用法:
  python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_bm25.yaml
  python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_hybrid.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from retrieval._bootstrap import experiment_config as ec  # noqa: E402
from retrieval.nodes import load_nodes  # noqa: E402

SCENARIOS = [
    ("A 单一来源即可回答", "产品如何安装？", "理想：user_manual（手册）"),
    ("B HTML 更适合回答", "create_datawriter() 的参数是什么？", "理想：zrdds_dev_guide（开发指南）"),
    ("C 多来源联合", "用户手册里的设备连接功能在 Java SDK 中如何实现？", "理想：两来源同时出现"),
    ("D 冲突/版本问题", "v2.4 的 API 是否仍使用旧参数？", "理想：能区分版本/来源"),
]


def _nodes_of(cfg):
    if cfg.retrieval.mode == "hybrid":
        ref = ec.load(ec.experiment_yaml_path(cfg.retrieval.components["vector"]))
    else:
        ref = cfg
    return load_nodes(ec.nodes_path(ref))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="smoke_cross_source", description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args(argv)

    from retrieval.retriever import build_retriever

    cfg = ec.load(args.config)
    meta = {n.node_id: n.metadata for n in _nodes_of(cfg)}
    retriever = build_retriever(cfg)
    print(f"[smoke] {args.config} mode={cfg.retrieval.mode}（结果仅开发参考，不进正式报告）")
    for title, question, ideal in SCENARIOS:
        refs = asyncio.run(retriever.retrieve(question, top_k=args.top_k))
        print(f"\n== {title} | {question}")
        print(f"   {ideal}")
        for i, r in enumerate(refs, 1):
            m = meta.get(r["node_id"], {})
            print(f"   {i}. [{m.get('source_type', '?')}/{m.get('version', '?')}] "
                  f"{r['source_id']} · {r['section'][:36]} · score={r['score']}")
    print("\n[smoke] 对照 §7.5 理想结果人工判读：来源分布是否符合预期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 先跑 bm25（无需模型，快速对照）**

Run: `python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_bm25.yaml`
Expected: 四问各有 top-5 输出；B/C/D 问题能明显看到 `html/2.4` 与 `pdf/2.0` 并存或按词面选择

- [ ] **Step 3: 跑 hybrid（需模型，确认融合不吞来源）**

Run: `python scripts/smoke_cross_source.py --config configs/experiments/struct_multisrc_hybrid.yaml`
Expected: 四问 top-5 中来源分布合理；C 场景（多来源联合）出现两来源共存；D 场景能按 score 区分

- [ ] **Step 4: 人工判读并记录**

对照 §7.5「理想结果」逐场景记录观察到的事实（简短文字，进 PR 描述即可，不建报告文件）。若发现明显异常（如 B 场景全为 pdf），记录现象与初步分析供例会讨论。

- [ ] **Step 5: 提交脚本**

```bash
git add scripts/smoke_cross_source.py
git -c user.name="Huuuu11" -c user.email="191314368+Huuuu11@users.noreply.github.com" commit -m "feat(tools): §7.5 四场景跨来源冒烟脚本（开发参考，不进正式报告）"
```

---

### Task 9: 收尾——全量测试 + PR

**Files:**
- 无新文件（汇总推送）

**Interfaces:**
- Consumes: Tasks 1-8 全部产出。
- Produces: `feature/hybrid-rrf` 分支推送 + PR（含会签注记）。

- [ ] **Step 1: 全量测试**

Run: `python -m pytest tests/unit -q`
Expected: 全绿（新增 test_rrf 9 + test_hybrid_retriever 7 + test_multisource_filters 6 = 22 条左右；总数应 ≥ 230）

- [ ] **Step 2: 工作树检查**

Run: `git status --short && git log --oneline origin/develop..HEAD`
Expected: 仅剩预期文件；提交序列清晰（7 个提交左右）

- [ ] **Step 3: 推送 fork**

```bash
git push fork feature/hybrid-rrf
```
Expected: 推送成功（网络偶发失败时重试）

- [ ] **Step 4: 创建 PR（GitHub MCP / gh）**

PR 标题：`feat(retrieval): 第三周 Hybrid RRF + 多来源过滤验证（PR#27 设计落地）`
PR 正文要点：
- 内容：RRF fuse_hits + HybridRetriever 引用制分发 + struct_hybrid/struct_multisrc_bm25/struct_multisrc_hybrid 配置 + verify_filters/smoke_cross_source 脚本 + 测试
- 验证：pytest 全绿；结构（struct_hybrid 120 题检索跑通）；多来源过滤校验通过（附 verify_filters 输出摘要）
- 会签注记：① `configs/experiments/README.md` candidate_top_k 一行（D）② `scripts/` 新增两个校验脚本落位（D）③ expected_sources: null 沿用「宁缺毋滥」协议
- 指标说明：本 PR 不产出 hit_rate/mrr（等 E 重标注 + C 口径），hybrid 正式对比在第四周
- 冒烟发现（§7.5 四场景人工判读摘要）

- [ ] **Step 5: 通知团队**

在 PR 里 @ D 过目会签注记；提示 A/E/C 的依赖项状态（A 产物已就绪被消费；E 题集是正式评测的唯一剩余阻塞）。

---

## Self-Review 记录（计划自审）

- **Spec 覆盖**：§2.2→T4，§2.3→T1/T2，§2.4→T1（score 语义写入 rrf.py docstring），§2.5→T1/T2/T5，§3.2-2→T7，§3.3→T7，§4.2/4.3→T8，§4.4→T6，§5 顺序→T1-T9；§6 会签①②③④ D 已实现，剩余 README 行/脚本落位在 T4/T7/T8 并进 PR 注记；§7 风险（score 量纲/k 未调参）已在 docstring 与限制中体现。
- **偏离声明**：设计 §2.5「跑 120 题评测，指标与单路对比」——因标注 P0（团队新协议「宁缺毋滥」）改为*仅跑通、无指标*，数值对比移至第四周（T5 已注明）。
- **占位符扫描**：无 TBD/TODO；所有步骤含可执行命令或完整代码。
- **类型一致性**：`fuse_hits(hit_lists, top_k, k)` 在 T1 定义、T2 引用一致；`HybridRetriever.__init__(vector_store, bm25_store, rrf_k, candidate_top_k, filters)` 在 T2 定义与测试、T7 测试引用一致；`experiment_yaml_path`/`index_dir`/`nodes_path` 均为 D 已上线接口。
