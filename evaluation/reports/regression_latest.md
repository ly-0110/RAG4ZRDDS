# 回归矩阵 2026-09-14T10:29:44+0800

- 范围: 全量
- 通道: 明细（top-K 重合率阈值 0.8）；指标 静默（标注未定版）
- 结论: **PASS**（8 pass）

| 实验 | 判定 | top-K 重合 | rank-1 一致 | 指标 delta | 耗时 s | 说明 |
|---|---|---|---|---|---|---|
| hybrid_v1 | pass | 0.9883 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 17.4 | — |
| semantic_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 10.4 | — |
| struct_bm25 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 0.1 | — |
| struct_hybrid | pass | 1.0 | 1.0 | n/a | 10.7 | — |
| struct_multisrc_bm25 | pass | 1.0 | 1.0 | n/a | 0.5 | — |
| struct_multisrc_hybrid | pass | 1.0 | 1.0 | n/a | 11.0 | — |
| struct_multisrc_v1 | pass | 1.0 | 1.0 | n/a | 10.3 | — |
| struct_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 10.3 | — |

> 由 `scripts/run_regression.py` 生成（指南 §10）。incomparable=输入已变，差异不作回归判定；regression/failed 使退出码非 0。
