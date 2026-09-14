# 回归矩阵 2026-09-14T09:39:39+0800

- 范围: 指定 2 个实验
- 通道: 明细（top-K 重合率阈值 0.8）；指标 静默（标注未定版）
- 结论: **PASS**（2 pass）

| 实验 | 判定 | top-K 重合 | rank-1 一致 | 指标 delta | 耗时 s | 说明 |
|---|---|---|---|---|---|---|
| struct_v1 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 17.8 | — |
| struct_bm25 | pass | 1.0 | 1.0 | hit_rate@5=+0.0000 mrr@5=+0.0000 | 0.6 | — |

> 由 `scripts/run_regression.py` 生成（指南 §10）。incomparable=输入已变，差异不作回归判定；regression/failed 使退出码非 0。
