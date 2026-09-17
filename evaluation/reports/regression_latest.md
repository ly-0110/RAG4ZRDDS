# 回归矩阵 2026-09-17T11:05:18+0800

- 范围: 全量
- 通道: 明细（top-K 重合率阈值 0.8）；指标 静默（标注未定版）
- 结论: **PASS**（12 pass）

| 实验 | 判定 | top-K 重合 | rank-1 一致 | 指标 delta | 耗时 s | 说明 |
|---|---|---|---|---|---|---|
| final_v1 | pass | 1.0 | 1.0 | n/a | 11.4 | — |
| hybrid_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 17.7 | — |
| semantic_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 17.5 | — |
| struct_bm25 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 0.1 | — |
| struct_hybrid | pass | 1.0 | 1.0 | n/a | 18.1 | — |
| struct_multisrc_bm25 | pass | 1.0 | 1.0 | n/a | 0.7 | — |
| struct_multisrc_hybrid | pass | 1.0 | 1.0 | n/a | 27.5 | — |
| struct_multisrc_hybrid_rerank | pass | 1.0 | 1.0 | n/a | 1987.4 | — |
| struct_multisrc_hybrid_ver20 | pass | 1.0 | 1.0 | n/a | 28.0 | — |
| struct_multisrc_hybrid_ver24 | pass | 1.0 | 1.0 | n/a | 26.8 | — |
| struct_multisrc_v1 | pass | 1.0 | 1.0 | n/a | 23.3 | — |
| struct_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 17.7 | — |

> 由 `scripts/run_regression.py` 生成（指南 §10）。incomparable=输入已变，差异不作回归判定；regression/failed 使退出码非 0。
