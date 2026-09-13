"""多来源 metadata 过滤验证：合成数据三模式语义对齐 + 真实索引合规。

合成部分不依赖模型（FakeEmbedder + 内存 chroma）；
真实部分对本地已建的多来源索引做「结果节点 ⊆ 元数据真值」合规校验
（bm25 通路无模型依赖；vector/hybrid 通路的真实验证在
scripts/verify_filters.py 中以真实模型执行）。
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from retrieval._bootstrap import experiment_config
from retrieval.bm25 import BM25Store
from retrieval.nodes import NodeRecord
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
    hybrid = HybridRetriever(vec, bm, filters=filt)
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
    hybrid = HybridRetriever(vec, bm, filters=filt)
    assert asyncio.run(hybrid.retrieve("gamma 查询", top_k=10)) == []


def test_real_multisrc_bm25_filter_compliance():
    # 需本地已建多来源 bm25 索引；否则跳过。
    # 直接对 BM25 产物查（无模型依赖）：结果 metadata 必须满足过滤约束，
    # 且索引确实含两种来源（合成索引无法暴露的分来源口径问题在此兜底）。
    cfg = experiment_config.load(
        Path(__file__).resolve().parents[2]
        / "configs" / "experiments" / "struct_multisrc_bm25.yaml")
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
