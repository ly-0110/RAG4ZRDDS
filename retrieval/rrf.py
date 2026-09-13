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
