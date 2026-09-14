# 第四周交付记录（成员 D）

> **v0.1（2026-09-14）**：首版。周计划见项目记忆 `project-week4-plan.md`（指南 §8 D 三项 / §10 回归机制 / §19 Week 4 验收）。本版记录 **D 交付一：回归自动化落地**（§1）、开工前置与分支状态（§2）、跨成员依赖与阻塞（§3）、需用户拍板的决策点（§4）、Week 4 验收对照现状（§5）。
> 记录人：成员 D。验证口径沿用四步：基线核对 → pytest 全套 → 契约核对 → 真值/端到端实测。

---

## 1. D 交付一：回归自动化（指南 §8 D 任务 1 · §10 机制生效）

### 1.1 交付物

| 文件 | 内容 |
|---|---|
| `scripts/run_regression.py`（新，~330 行） | 一键回归矩阵：实验发现 → 跑实验 → 与历史/基准报告比对 → 四态判定 + 退出码 |
| `scripts/run_experiment.py` | 报告 schema 升 **`rag4zrdds.report/v1.1`**：新增 `artifacts` 三份输入产物指纹；新增 `_artifact_fingerprints(cfg)` |
| `scripts/build_index.py` | 指纹算法抽出通用 `sha12_file(path)`，`_nodes_file_sha12` 委托之（**单一事实源**，R6 教训：算法副本必造成恒不匹配） |
| `Makefile` | 新增 `regression`（`REG_ARGS` 透传）与 **`test`**（此前 make 里根本没有单测入口） |
| `.gitignore` | 忽略回归的本机产物 `evaluation/reports/runs/`、`regression_2*.json`；`regression_latest.*` 与 `baseline/` 入库 |
| `tests/unit/test_run_regression.py`（新，36 例） | 闸门/明细/指标/变更映射/发现/紧凑锚点/main 失败聚合 |

### 1.2 机制设计要点

1. **可比性闸门（本次最关键的一条）**：报告此前只带 `config_hash8`。R1（PR#11）与 R4（PR#13）两次事故同根——**配置未变、磁盘产物被旧基线 PR 换掉**，只看 hash8 会让这类差异伪装成"可比"，从而把输入变更误记成性能回归（或反之掩盖真回归）。v1.1 报告额外记录 `nodes_file_sha12` / `questions_sha12` / `expected_sources_sha12`；比对前任一不符 → 判 `incomparable` 并列出原因，**不出 regression 结论**。旧版 v1 报告无 artifacts 同样判不可比（首次运行会看到，重跑即自愈）。
2. **双通道（宁缺毋滥不变量）**：
   - 明细通道（默认）：与标注无关，比 top-K 命中集合重合率、rank-1 一致率、空结果题数、耗时。重合率口径 = `|A∩B| / max(|A|,|B|)`（**不是 Jaccard**：top_k=5 换 1 条 Jaccard 只剩 0.667 会误报，重合系数为 0.8 恰好落在默认阈值上）。
   - 指标通道（`--with-metrics` 显式开）：真值标注定版后启用，指标下跌超 `--metric-tol`（默认 0.02）判 regression。默认关闭并在摘要标注"静默（标注未定版）"——现库 120 条标注仍是检索反推的循环版（week3 review §2.5），指标已算但不参与判定。
3. **变更 → 范围映射（§10 的 7 类变更）**：`--changed-only` 读 `git diff`（相对 `--base`，默认 `origin/develop` + 工作区）。`data_pipeline/`、`retrieval/`、`data/processed/`、`requirements.txt`、`scripts/`（D 的 ingest/build_index/配置校验/实验运行）任一改动 → **全量**；只改 `configs/experiments/X.yaml` → 只回归 X；只改生成侧 → 提示不纳入矩阵；判定器自身（`scripts/run_regression.py`）豁免，否则改进判定器会自触发全量。规则倾向偏全（漏跑比多跑危险）。
4. **历史不丢**：`run_experiment` 是覆盖式写报告，回归器在跑之前把旧报告归档到 `reports/runs/{name}__{生成时间}.json`；`--promote` 写 `reports/baseline/{name}.json` **紧凑锚点**（只留判定所需头部字段 + 每题 `node_id` 列表，340KB → 99KB，且锚点不带题干与标注原文）。
5. **退出码可挂 CI**：`regression`/`failed` → 1（总体 FAIL）；`incomparable`/`warn`/`missing`/`no_baseline` → 0（总体 REVIEW）；全清 → 0（PASS）。

### 1.3 实测证据（本机，2026-09-14）

- `python -m pytest tests/` → **302/302 绿**（266 → +36）。
- **正向闭环**：`--only struct_bm25` 首轮 `incomparable`（历史报告为 v1 无指纹）→ 重跑 → `pass（vs 上次 pass / vs 基准 pass）`，结论 PASS、退出码 0。
- **真实实验复现性**：`--only struct_v1,struct_bm25` 连跑两轮，第二轮两实验均 `top-K 重合 1.0 / rank-1 一致 1.0 / hit_rate@5 delta +0.0000`，耗时 17.5s（真实 bge-m3 向量检索）与 0.6s（bm25）——同索引同产物的确定性复现得到实证。
- **负向验证（不破坏基线的前提下）**：把阈值抬到 `--min-overlap 1.0001` → 判 `regression`、总体 FAIL、**退出码 1**；`--with-metrics` 在零差值重跑下仍 `pass`（闸门不误伤）。
- **紧凑锚点**：`--promote` 后 `baseline/struct_v1.json` 100KB / `struct_bm25.json` 99KB，比对照常成立（有单测锁定）。
- 落盘：`evaluation/reports/regression_latest.{json,md}`（矩阵摘要）+ `runs/` 归档（本机）。

### 1.4 边界与未覆盖

- `--changed-only` 的路径映射由单测覆盖，**未在真实多人 PR 流上跑过**；下周若有 B 的 reranker PR 合入即为首个实战样本。
- semantic / hybrid / 多来源四个实验本轮未纳入实跑：semantic 索引待 A 处置超长块（§3），hybrid 类实验依赖子索引存在（已具备，跑一次约 3~5 分钟）。
- 指标闸门默认关闭，Week 4 验收项"有自动/半自动 Evaluation"目前只覆盖检索侧，回答侧阻塞在 C（§3）。

---

## 2. 分支与开工前置状态

- 本地 `feature/server-platform` = `5d925c2`（与 origin 同步），**PR#31 仍待 squash 合入 develop**（远端 develop 落后本地 37 提交）。
- 本周新增改动（未提交）：`.gitignore`、`Makefile`、`scripts/{build_index,run_experiment,run_regression}.py`、`tests/unit/test_run_regression.py`、`evaluation/reports/{struct_v1,struct_bm25}.json`（升 v1.1）、`evaluation/reports/{baseline/,regression_latest.*}`（新增）。
- 索引状态：六套全部可用且指纹匹配，本轮回归**未触发任何重建**（复用链路正常）。

## 3. 跨成员依赖与阻塞（截至本版实测）

| 事项 | 归属 | 实测现状 | 对 D/Week4 的影响 |
|---|---|---|---|
| 真值标注（逐题对 PDF 核对） | E | `expected_sources.jsonl` 120 条仍在，但与规范索引报告 top-1 仅 **44/120** 吻合（本次实测），仍是循环 + 非规范模型副本产物 | 指标闸门只能默认关闭；6 份 void 报告无法刷新；Week4 验收项 1/2/3 继续阻塞 |
| Reranker（§8.2） | B | `retrieval/retriever.py:154` 仍 `NotImplementedError("hybrid_rerank 待第四周实现")` | "Reranker 有实验数据"验收项拿不到；D 侧配套（build_index 跳过 / 子索引检查 / 权重离线缓存）待其落地 |
| `answer_eval.py` runner（X2） | C | `evaluation/runners/` 仍只有 `.gitkeep` | 回答侧指标无法进矩阵；D 的 `run_experiment` 保持 `response_metrics` 非空即拒绝的现有语义 |
| semantic 超长块 | A | `data_pipeline/chunkers/semantic.py:63` 的 `self.max_chars` 仍无消费点 | semantic 索引/报告/错误案例三者仍挂起，矩阵里该实验暂不实跑 |
| Prompt 版本一致性（议题 8） | C/D | `struct_bm25.yaml` 仍 `prompt_version: v0` | 配置在 D 域，改前需与 C 对齐 |

## 4. 需用户拍板（提问确认，未答复前不动相关代码）

1. **容器化路线**：本机 `docker` 命令不存在（2026-09-14 实测）。三选一：装 Docker Desktop 后真验证 / 交付未验证的 Dockerfile+compose 并显式标注 / 放弃容器只保证 `make` 三行命令。
2. **PR#31 合入时机**：是否现在就以 squash 合入 develop（我可经 GitHub MCP 执行，随后走"备份 → reset 对齐 → 你手动 force-with-lease"收尾），还是把本周回归改动并进去重后再合。
3. **本地 LLM 实跑**：`ollama`（11434）与 `models/llm_gateway.py`（11500）当前均未监听。Demo 前置的生成侧实际出词验证，要我先启动这两个服务，还是你手动起（涉及长时进程与显存/端口占用）。
4. **OpenAI 兼容门面**：`server/openai_compat/` 空目录（2026-09-08 决策不做）。第四周若汇报不需要"生态兼容"证据，建议删除空目录。

## 5. Week 4 验收对照（指南 §19）· 本版现状

| 通过标准 | 现状 | 依据 |
|---|---|---|
| Hybrid Retrieval 可运行 | ✅ | PR#30 已本机实证；本轮已纳入回归矩阵（`struct_hybrid`/`struct_multisrc_hybrid` 配置齐备） |
| Reranker 有实验数据 | ❌ 未开始 | B 域 `hybrid_rerank` 仍抛 NotImplementedError（§3） |
| Unknown/Abstention 可工作 | ◌ | Prompt v2 拒答规则 live 生效；20 题专项待 C 定版 + E 题集 |
| 有 Citation | ✅ | 7 字段/双页码/来源分型；X3 后 error 路径可回查 |
| 有自动/半自动 Evaluation | ◌ **本版推进** | 检索侧自动化闭环（§1，含可比性闸门与退出码）；回答侧待 C 的 runner |
| 有最终 Demo | ◌ | 生成侧实际出词仍未验证（§4 决策 3） |
