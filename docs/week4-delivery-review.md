# 第四周交付记录（成员 D）

> **v1.0（2026-09-15，结构重构）**：按"一个 PR 一个大点"重排——此前按交付时间线滚动追加的 §1~§8 收敛为「总览 + D 交付一张表 + 各 PR 审查」；删除过程性内容（逐版本变更史、分支累积记录、已执行完毕的拍板过程，见 git 历史与本文件旧版）。只保留对当前协作仍有效的结论。
> 记录人：成员 D。验证口径：基线核对 → pytest 全套 → 契约核对 → 真值/端到端实测。

---

## 1. 总览

| PR | 成员 | 内容 | 结论 |
|---|---|---|---|
| #31 | D | week3 review v0.5 + api.md v0.9 | 已 squash 合入 develop |
| #32 | A | semantic 超长块修复 | 合格（§3.1） |
| #33 | B | relpath 跨盘符守卫 + 注释纠偏 | 合格（§3.2） |
| #34 | B | 第四周检索设计文档 | D 会签完毕（§3.3） |
| #35 | D | 第四周全套交付（8 项，§2） | 已 squash 合入 develop（`b606e9f`） |
| #36 | E | 多来源证据前端与问题集质量闭环 | 改善显著，1 个新 P0（§3.4） |



## 2. D 交付（PR#35）

指南 §8 的 D 三项 + 五项跨成员接缝，全部本机实测：

| # | 交付 | 落点 | 关键证据 |
|---|---|---|---|
| 1 | 回归自动化（§8 任务 1 / §10） | `scripts/run_regression.py` + 报告 schema v1.1（artifacts 三指纹：Node/问题/标注集）+ `make regression/test` | 8 实验矩阵提基准后 8/8 pass；负向验证（抬阈值）判 regression 且退出码 1；36 单测 |
| 2 | 打包与 README（§8 任务 2） | Makefile venv 解释器贯通（修"`setup` 建 venv、其余目标用裸 python"的脱节）+ README 全文重写 + `.env.example` 补注 | `make -n` 有/无 venv 双分支实测；README 15 链接程序化核对 0 缺失 |
| 3 | Demo 环境（§8 任务 3） | `docs/demo-runbook.md` + Ollama→`llm_gateway.py`→live 通路 | **生成侧实际出词首次实测**：四场景（印刷 127/物理 133 真值、E1003 与第 300 页两例正确拒答、跨来源 C/C++ 差异披露、hybrid RRF 0.0276~0.0318）；四级日志按 rid 关联 |
| 4 | Feedback 落库（E 任务接缝） | `POST /feedback` + `{LOG_DIR}/feedback.jsonl` + api.md v0.10 | 7 单测；live 三条（未知 rid 404 零落盘、跨重启仍可归因） |
| 5 | Reranker 配套（B 接缝） | `uses_reference_index()` 单一事实源收敛三处判定；schema 放宽 `hybrid_rerank`、拒绝 vector/bm25 误填 | 5 单测；`struct_hybrid` 端到端复用子索引 |
| 6 | W1 过渡处置（方案 B） | 回查通道（`/sources`、MCP `get_sources`）附带 `source_url`（api.md v0.11）；SSE 仍 7 字段 | 多来源 5 引用 4 条真实 URL；+6 测试；`make smoke-mcp` 抓到并修复 MCP 二次 put 覆盖缺陷 |
| 7 | reranker 权重预取 | `BAAI/bge-reranker-v2-m3` 2.2GB 本地 HF 缓存 | B 落地可离线加载，演示当天不赌网络 |
| 8 | 标注真值核对工具 | `scripts/audit_annotations.py` + `make audit`（判据只来自 A 的产物与章节树，**不调检索器**） | 首轮 verdict=blocked（48 题 token 邻近、6 题零命中、循环 44/120）→ 直接促成 E 回炉（§3.4）；是 `--with-metrics` 的前置门禁 |

**验证缺口（如实）**：`make setup` 的 venv 全新安装未本机跑（需重下 2GB+）；容器形态未交付（本机无 docker，按 make 链路交付）。

## 3. 各 PR 审查

### 3.1 PR#32（A）= 修复合格，但第三次带入文档回退

- **修复有效**：`_enforce_max_chars()` 让 `max_chunk_chars` 真正被消费——D 独立复核：修复前 18 块超限（max 7175）→ 新产物 **622 块 / max 2497 / 0 超限**。semantic 索引重建 719.1s → 报告重跑 → 真实错误案例 37→70 → 基准重锚，回归闸门全程判定正确。
- **第三次带入旧基线文档回退**（week2 review §1 状态被擦回 09-07、ingest-pipeline 表行重复）→ 合并中按事实恢复。反馈 A：开工前必须 `git merge develop`（PR#11 代码回退、PR#28 文档回退、本次同类）。
- **衍生缺陷根因在 D**：`collect_real_error_cases.py` 的 `TRUTHS[qid]` 硬索引在题集 15→120 后即坏（自 PR#22 起），已修为"无人工真值即跳过 + 显式打印覆盖度"。

### 3.2 PR#33（B）= 合格

- relpath 跨盘符守卫（+测试）+ 我 09-13 指出的"import 排列影响 chroma flush"无因果依据注释纠偏。
- 交付习惯好：正文如实登记 `+1 failed` 并 stash 自证与己无关——该失败根因即 §3.1 的 TRUTHS 硬索引（D 域）。

### 3.3 PR#34（B 第四周检索设计）= D 会签完毕

- 四项落定：①gate 按现状答复（D 两脚本已由 `uses_reference_index()` 覆盖 hybrid_rerank，B 只需直改 `retrieval/index.py` 的字面比较）②api.md **v0.12**（hybrid_rerank 交叉编码器分以 B 冒烟实测为准；boost 归一化分跨查询不可比；均不设绝对阈值）③README params 行 D 直接写 ④B→C 两项（阈值按 mode/配置定标、source_priority 维持生成侧）认可待例会通报。
- **待 B 拍板「设计一致性」**（设计文档 §6.1 回写）：schema/README 允许 hybrid_rerank 无 components 走自有索引，而 B 计划让检索层一刀切拒绝——二选一。
- 成本修正：Node 集重建以 D 实测为准（multisrc 24.8min，非 B 估的 87min）。

### 3.4 PR#36（E）= 改善显著，1 个新 P0

merge-base = develop 合并前 HEAD，**基线纪律连续第三次达标**；16 文件，跨域触碰 D 的审计脚本——**D 追认**（页码区间校验实现干净、判据仍只来自产物、+3 测试；纪律备注：跨域改动应在 PR 描述声明）。本轮审查在只读 review worktree 完成（权限分类器拦截分支级 git 操作，PR#23 同类先例）。

**标注质量（week3 P0-1 循环论证实质改善）**：

| 指标 | PR#22 版 | PR#36 版 |
|---|---|---|
| `make audit` verdict | blocked | **pass** |
| 循环指纹（标注=检索 top-1 回显） | 44/120 | **4/120** |
| 48 题 token 邻近阻断 | 阻断 | 清零（部分经区间放宽达成，见 P1） |
| 6 题实体零命中 | 阻断 | 题干改写（但引入 P0） |

**指标可算性**：区间标注与 `run_experiment` 兼容（`_page_in_range` 自 PR#14 即有）；`matches_expected` 为 AND 语义（source_id + 页码 + section_keyword），69 题全书级区间**不灌水**——struct_bm25 实跑 **hit@5=0.3667 / mrr@5=0.2575**（非平凡值）。multisource 标注 25 条 Makefile 未覆盖，D 用 CLI 补审 = pass。

**前端合格**：feedback 面板按 api.md v0.10 契约；**W1 正式闭环**（回查富化 `source_url` + CitationsCard 渲染外链，noopener）；vitest/@vue/test-utils 测试设施；Top-K 显示 6→5 修正。

**问题**：

| 级别 | 问题 | 处置 |
|---|---|---|
| **P0** | Q021/Q023/Q028/Q059/Q060/Q119 六题题干经 E 重写（意图为消除零命中实体），但写入环节发生有损转码——非 ASCII 字符全部变字面 `?`、ASCII 完好，文本已废；乱码题干会污染检索与计分 | 改写意图由 E 以正确编码重做，或由 C 将 6 题转入拒答专项口径；期间不开正式 `--with-metrics` |
| **P1** | 宽区间语义复核未完成：114/120 为区间、69 题全书级 [7,288/289]——页码条件名存实亡，keyword 选错机器抓不出；Q056 仍 `10.34 DurabilityServiceQosPolicy` 错标（真值 10.7 @印刷127），被区间 [61,163] 洗白后审计不再报警 | E 逐题收窄区间并**人工**复核 keyword（机器探针因 QoS 汇总表干扰分辨力不足） |
| **P2** | datasets README 的 expected_sources 行仍写"尚无"（过期）；questions.jsonl 大改写未经 C 口径会签（上轮遗留） | E 顺手更正；口径例会带 |

## 4. 未完成任务与阻塞

| 事项 | 归属 | 现状与影响 |
|---|---|---|
| 六题题干重做| E（或 C 定拒答口径） | 重写务必 UTF-8 全程（勿经 ASCII/ANSI 转码环节） |
| PR#36 P1 宽区间 keyword 复核 | E | 69 题全书级区间页码条件名存实亡；Q056 仍 10.34 错标 |
| `hybrid_rerank` 实现 + §3.3 设计一致性拍板 | B | 仍 `NotImplementedError`；D 侧配套与 2.2GB 权重已备好 |
| `answer_eval.py` runner（X2） | C | `evaluation/runners/` 仍空；回答侧指标无法进矩阵 |
| `source_url` 正式进 wire（方案 A） | B/C/E 会签 | 回查通道已落地且被前端消费；SSE 仍 7 字段 |
| multisource 数据集接线 | D | 待标注定版：multisrc 配置 dataset/expected_sources 指向 + Makefile audit 覆盖 |
| 例会带回 | — | struct_bm25 prompt v0→v2（议题 8）、F1（filters 是否移出身份段）、feedback 字段会签（E/C）、base_url 正式域名、PR#34 两项通报 C、questions 大改写口径（C） |

## 5. Week 4 验收对照（指南 §19）

| 通过标准 | 现状 | 依据 |
|---|---|---|
| Hybrid Retrieval 可运行 | ✅ | 实验通路 + live 服务通路实测（RRF 0.0276~0.0318、引用制零重建） |
| Reranker 有实验数据 | ❌ | B 域 `hybrid_rerank` 仍 `NotImplementedError`（D 侧配套就绪） |
| Unknown/Abstention 可工作 | ✅ | E1003 不存在 / 第 300 页越界两例 live 明确拒答且不虚构；20 题专项口径待 C |
| 有 Citation | ◕ | 双页码/来源分型/回查达标；回查通道带 `source_url` 且前端已消费；SSE 扩第 8 字段待会签 |
| 有自动/半自动 Evaluation | ◌ | 检索侧矩阵与闸门闭环、`make audit` 首次 pass；正式指标冻结至 PR#36 P0/P1 清零 |
| 有最终 Demo | ◕ | demo-runbook v0.2 + 四场景实测；缺口只剩 reranker |
