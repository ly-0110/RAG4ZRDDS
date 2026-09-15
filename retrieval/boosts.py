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
