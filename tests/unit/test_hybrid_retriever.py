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
