# 第四周交付记录（成员 D）

> **v1.8（2026-09-17 凌晨）**：新增 §3.10 —— 用户实测反馈三项处理 + 一个增强：**①中止当前回答**（前端"停止生成"＋服务端取消语义）②**相关度分数跨通路口径澄清**（bm25/hybrid 不可比，前端按模式换标签；runbook 新增 §8 各实验运行策略）③**三处缺陷**（PDF 页码恒空＝产物字段名读错 / HTML 无页码概念 / "打开 HTML 原文"指向占位域名打不开）④节点详情**按来源格式**渲染。api.md **v0.16**、runbook **v0.7**；pytest **420/420**、前端 vitest **13/13**。

> **v1.7（2026-09-16 深夜）**：新增 §3.9 —— **D 代修 E 域前端 + 一处必须的整合修复**（用户授权，为次日演示）：F4 选择器空列表、vite 代理缺 `/nodes`、markdown 无样式、重复相关度条、节点详情 JSON 堆、**展示路径依赖 rAF 导致回答区可能永不挂载**（本机实证并修复）、`/nodes` 跨实验回查。全链路 live 实测通过；api.md 升 **v0.15**；pytest 408/408、前端 vitest 5/5、`vite build` 通过。
> **v1.6（2026-09-16 晚）**：新增 §3.8（PR#45 = E 前端与 P0/P1 复核）——**E 误删 C 第三周交付的事故**（Revert 事故，D 已按 `adf69f0` 恢复）+ E 任务完成度逐项核实（F1/F2/F3 ✅、F4 ❌ 运行时不可用、P0 编码 ✅ 但三题新实体零命中、P1 未完成）；§1 总览补 #44/#45；§4/§5 同步。pytest **402/402**。
> **v1.5（2026-09-16）**：新增 §3.6（PR#42 = C 第四周回答侧评测，**X2 闭环**，合格）与 §3.7（PR#43 = E 名不副实的空交付 + feature/web 基线漂移警告）；§1 总览补 #41/#42/#43；§4 销项 X2、E 行补分支警告；§5 验收对照更新。pytest **402/402**。
> **v1.3（2026-09-15）**：§4.1 F1/F3/F4 的 D 侧后端落地回写（用户四问拍板：/healthz 扩 kb、新增 /nodes、/query experiment；E 域前端全部留 E）——api.md 升 **v0.14**，+15 测试，pytest 383/383。
> **v1.2（2026-09-15）**：新增 §4.1（前端实测四项问题，D 逐条代码核实全部属实）；§4 总表加一行指向。
> **v1.1（2026-09-15）**：新增 §3.5（PR#38 = B 第四周检索交付审查）；§1 总览、§4 未完成、§5 验收对照同步更新。
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
| #37 | D | 第四周收尾（PR#36 合入 + review v1.0 + README/demo-runbook 改 API 为主） | 已 squash 合入 develop（`0050e6f`） |
| #38 | B | 第四周检索：Hybrid+Reranker 通路 + Version-aware 加权 + 四组对比 | 合格（§3.5） |
| #39 | D | 第四周收尾二（PR#38 审查 + hybrid_rerank components 必填 + 精排阻塞入册） | 已 squash 合入 develop（`d8134e5`） |
| #40 | B | 审查跟进：审计状态更正 + 精排打分移出事件循环 | 合格，已闭环（§3.5.1.1） |
| #41 | D | F1/F3/F4 后端三件（/healthz kb、/nodes/{node_id}、/query experiment）+ api.md v0.14 | 已 squash 合入 develop（`d6774b1`，diff 验证零丢失） |
| #42 | C | 第四周回答侧评测：answer_eval runner + 20 题拒答专项 + C2~C5 落实 + 可靠性报告 | **合格，X2 闭环（§3.6）** |
| #43 | E | 「前端修复与 P1 复核数据交付」 | **名不副实的空交付；feature/web 基线漂移警告（§3.7）** |
| #44 | D | PR#42/#43 审查落笔（review v1.5） | 已 squash 合入 develop（`adf69f0`） |
| #45 | E | 前端 F1~F4 接线 + P0 题干修复 + P1 复核清单 | **P0 编码 ✅、F1/F2/F3 ✅、F4 ❌ 运行时不可用、P1 未完成；⚠ 误删 C 交付（§3.8）** |
| 本分支待发 | D | 代修 E 域前端可见缺陷（含 rAF 不渲染）+ F3×F4 整合修复 + api.md v0.15 | **408/408 + 前端构建/测试 + 全链路 live 与浏览器实测通过（§3.9）** |



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

### 3.5 PR#38（B 第四周检索）= 合格

merge-base = `b606e9f`（#35）rebase 后交付，零冲突；B 正文声明 rebase 时丢弃两项已被上游取代的改动——**核实属实**（scripts 两处 gate 已用 `uses_reference_index()`、README params 行已由 D 写好，B 均未重复）。本机 merge 后 **pytest 367/367**（B 报 362+2 skip，差异 = 本机真实产物齐全、2 个守卫测试实跑）。

**交付内容**：

1. **Hybrid+Reranker 通路**：`retrieval/rerank.py` 精排工厂（懒加载 CrossEncoder、models/ 本地优先复用 D 的 `resolve_model`、别名映射）+ `HybridRerankRetriever`（RRF 30 → 精排 → Top5）。走原始 hit 通路的原因（版本加权需要 metadata、`_to_source_ref` 投影后丢失）在 docstring 写明；`rerank_fn` 可注入可测。`max_length=512` 性能修复（不设时按模型上限 8192 处理，120 题 4.9h → 512 截断 2.1h，BAAI 官方用法）有实测依据。
2. **Version-aware（§8.3）**：`retrieval/boosts.py::apply_version_boost` = 池内 min-max 归一 + 版本加成。量纲免疫论证正确（乘法在负分翻转、加法在 RRF 量纲淹没，均排除）；未配置时零回归；node_id 决定性 tie-break。三模式 retrieve 统一挂接，仅 boost 生效时扩候选池。ver24/ver20 双向对照配置齐备。
3. **四组对比 + 方法学**：`docs/evaluation.md`（B 域新文档）——指标纪律好：真值标注未定版期间按宁缺毋滥走**证据链模式**（`expected_sources: null`，不产 hit/mrr 数字），结构性证据（来源分布、top-1 漂移 59/120、token 覆盖率）均明示"非真值指标"。回归快照 11 实验 **10 pass 1 warn 且 `with_metrics=false`——B 遵守了指标闸门**。

**D 域触碰（均追认）**：api.md 升 **v0.13**——B 冒烟定死精排分量纲（sigmoid 0~1，120 题实测 0.084~0.991，输入 512 token 截断），PR#34 会签事项 2 闭环，字段无增删；三份既有报告重跑刷新（`struct_multisrc_v1/bm25/hybrid`）——同索引同题集，仅两处 top-5 近平局换序（0.7098/0.6657，**集合不变，与回归明细重合 1.0 自洽**）+ 时间戳/耗时。

**本机端到端实测（D）**：`make audit` = **pass**（阻断 0，循环 4/120）；`struct_multisrc_hybrid_ver24` 全量 120 题 17.9s 跑通，**boost 生效实证**（score 落在 [0,1.1] 归一化空间，非 RRF ~0.03 量纲）；引用制零新索引，六套既有索引全部复用。

**问题与注意**：

| 级别 | 事项 | 处置 |
|---|---|---|
| P2 | `docs/evaluation.md` §1 写"`make audit` verdict=blocked（48 题 token 错位、6 题零命中）"——为 09-14 过期快照；六题题干回退处置后（#37）现为 **pass**（阻断 0、循环 4/120） | B 顺手更正一行；不影响其证据链模式正确性 |
| 待 D | B 拍板方案①（hybrid_rerank 一律引用制，§6.1 已回写）后留给 D 的两项：schema `components` 可选→必填 + `configs/experiments/README.md` components 行更新（现行"未填则按自有索引+精排建索引"表述作废） | 见 §4；D 域 |

#### 3.5.1 精排同步阻塞事件循环——本机实测与解决方法（2026-09-15）

**现象与根因**：`HybridRerankRetriever.retrieve()` 是 async 方法，但精排打分（CrossEncoder 对 30 个「问题×候选块」对逐一推理）是同步 CPU 代码，直接占据事件循环线程——这是 B 第一周注记"同步推理置于 async 内"老问题的放大版（向量路单题 ~1s 从未显形，精排 15~63s 使其可见）。

**本机实测**（9700X CPU，ticker 法：事件循环内挂 0.1s 间隔心跳，与检索并发）：

| 项 | 实测值 |
|---|---|
| 双路 store 装载 | 0.6s |
| 首题总延迟（含 2.2GB CrossEncoder 冷加载） | **27.8s** |
| 热题总延迟 | **15.1s**（向量路 0.1s + bm25 路 0.00s + RRF 融合 ~0 + **精排打分 15.0s**，占 99%+） |
| 事件循环阻塞 | 查询 15s 期间心跳 **0 次跳动**（不阻塞理论值 ~150）→ 全程冻结 |
| B 机对照 | ~63s/题（120 题 2.1h，docs/evaluation.md §2.1） |

**影响边界**：仅 live 服务通路——冻结期间 `/healthz`、并发 `/query`、其他会话的 SSE 流、`/feedback` 全部排队；单用户演示体感为"提问后干等 15~28s"。**对离线实验流水线（run_experiment）无影响**（批量跑无事件循环概念）。检索质量 sanity 正常：两道探针题 top-1 分别命中手册 8.3.1 创建DataWriter / 6.3.1 创建DomainParticipant，双来源共存合理。

**解决方法（B 域，按优先级）**：

1. **打分移出事件循环（推荐，改动最小）**：`retrieve()` 内 `scores = await asyncio.to_thread(self._rerank_fn, question, texts)`——事件循环保持响应，冻结消失；torch CPU 推理释放 GIL，线程可行。并发语义注意：to_thread 后多个请求可同时进精排争抢 CPU 核（CPU-bound 无排队控制），单用户演示无碍，多人并发场景 B 需评估是否加信号量串行化。
2. **启动期预热精排模型（配合 1）**：同 D 的 `_warmup_retriever` 先例——pipeline live 分支组装后跑一次打分，把 2.2GB 冷加载从首题移到启动期（预热失败拒绝启动并给可读错误）。
3. **降本选项（实验口径需 B 评估）**：`candidate_top_k` 30→10 打分时间约线性降至 1/3；或换 bge-reranker-base 等更小模型（模型选型变更属实验记录，需重跑对比）。
4. **演示规避（不动代码）**：live 演示不挂 hybrid_rerank 配置（vector/hybrid 通路检索为秒级）；如必须演示精排，单题单发并明确标注等待时长（demo-runbook v0.3 §4 已同步该口径）。

**B 请 D 留意的另两项**：①`struct_multisrc_v1` 回归 warn——纯时长项（B 机 21.5s vs 基准 10.2s >2×），检索明细重合 1.0，属跨机器速差非回归；②reranker 权重两份并存（HF 缓存 + B 机 `models/`）——**本机核实仅 HF 缓存一份 2.2GB**（`models/` 不入 Git，B 的两份都在其机器），清理与否由 B 自定。精排组单次 2.1h，全量回归含精排组建议 `--only` 选跑（合理，照办）。

#### 3.5.1.1 状态更新（2026-09-15 晚，PR#40 后 · 已闭环）

**B 已按建议①修复**（`60ee5b2`）：`retrieval/retriever.py` 单点改为 `scores = await asyncio.to_thread(self._rerank_fn, question, texts)`，并按 TDD 补"同步打分期间心跳持续跳动"回归用例（0.3s 假打分 + 0.01s 心跳，修复前 0 跳红 / 修复后 ≥5 跳绿）。

**D 本机 ticker 复核**（真实产物 `struct_multisrc_hybrid_rerank`，非单测）：

| 场景 | 耗时 | 心跳 ticks | 理论值 | 判定 |
|---|---|---|---|---|
| 热查询（纯精排打分 30 候选） | 16.1s | **159** | ~161 | 事件循环几乎不冻（修复前同口径 = 0 tick/15s） |
| 冷查询（首题含 bge-m3 + CrossEncoder 冷加载） | 26.0s | 167 | ~260 | 约 9s 冷加载仍占循环 |

**建议②（启动期预热精排模型）撤销，不再要求 B 实现**（用户 2026-09-15 拍板）——理由：①已消除主体阻塞；且本轮 F4 落地后，服务端切到 `hybrid_rerank` 时的管线组装（含预热）跑在 `PipelineRegistry` 的 worker 线程里，冷加载不落在事件循环上；②只在"hybrid_rerank 作为启动默认配置"时才有边际意义。**剩余的冷加载/首切等待（~26s）已由 demo-runbook v0.4 的"通路切换需预热"口径覆盖**。

**仍留 B 自评**：并发信号量（to_thread 后多请求可同时进精排争抢 CPU 核；单用户演示无碍）——记 P3，不阻塞交付。

### 3.6 PR#42（C 第四周回答侧评测）= 合格，X2 闭环

head = `feature/generation-week4`（`3822feb`），squash 合入 `a436412`；diff 17 文件 +1165/−61，D 域 server/ 文件零触碰、无回退——**基线纪律达标**。

**交付内容**：

1. **X2 闭环**：`evaluation/runners/answer_eval.py`——逐题检索→生成→拒答判定→四指标判分→聚合。`judge_fn`/`chat_stream` 可注入（离线单测不联网，与既有测试模式一致）；`aggregate()` 均值只统计 `parse_ok=True`、失败单列 `parse_failed`；报告经 `build_report` 落盘前 `to_source_refs` 剥离正文——"正文不入报告"立场保持。run_experiment 在 `response_metrics` 非空时接入，报告新增可选 `response` 段（不 bump schema）。
2. **C2/C3/C4/C5 全部落实**（我 2026-09-08 反馈）：C2 = `JudgeResult.parse_ok` 显式标记，解析失败不再静默记 0；C3 = `_judge` 固定 `temperature=0.0`，`stream_chat`/`complete_chat` 加可选 temperature；C4 = RELEVANCE_SYSTEM 明确"正确拒答应评 5 分，不得因未给正面答案扣分"；C5 = `generation/abstention.py::ABSTENTION_MARKERS` 单一事实源 + `is_abstention()`，judges/runner/拒答专项共用，**刻意不收事实性否定**（"不支持 X"可能是检索到的真值）。
3. **20 题拒答专项（§8.4）**：`abstention_questions.jsonl` AB-001~020，五类（杜撰 API 4 / 杜撰错误码 3 / 杜撰功能 7 / 跨版本断言 3 / 越界 3），**每题 note 锚定审计已确立的"语料不存在"事实**（connect()、E1003、版本对比、第 300 页越界）；`abstention.py` 校验模块（AB- 前缀/恰 20 题/category 白名单/id 唯一/note 非空）；`make abstention` 20/20 拒答则退出码 0，可挂 CI。
4. **新 judge ×2**：`correctness`（无 gold answer，评"证据一致的正确性"，口径在 system prompt 写明）与 `citation_accuracy`（[n] 越界/张冠李戴/漏标扣分）；空检索兜底判 0 不调 LLM。
5. **终跑配置 `final_v1.yaml`**（stage=product）：与 `struct_multisrc_v1` **同 hash8（`d57f695e`）复用同一索引目录**——R5 身份段机制的实证（改 generation/evaluation 段不触发重建）；`expected_sources: null` 遵守标注闸门；`source_priority: [zrdds_dev_guide, user_manual]` 定稿。
6. **`docs/reliability-report.md`**：检索侧如实标 void/blocked（引用本 review §3.4 P0/P1，阻塞链理解正确）、回答侧与拒答专项标"已实现·留命令"——**不虚报数值，宁缺毋滥纪律执行到位（B PR#26 教训未重演）**。
7. **跨域改动（D 域，追认）**：`run_experiment.py`——response_metrics 非空时 LLM env 前置校验（早失败）；`Makefile` +3 目标（answer-eval/abstention/manual-review）。

**D 本机验证（2026-09-16）**：

| 项 | 结果 |
|---|---|
| `pytest tests/` | **402/402 全绿**（C 报告 §8 的"15 例失败"经核实为其本机环境：缺 mcp 包、未建子索引、跨盘符 tmp——非代码问题，本机不复现） |
| `scripts/experiment_config.py final_v1.yaml` | 配置有效，hash8=`d57f695e`，Node 集/索引目录均指向既有产物（`indexes/` 六目录盘点复核，零重建） |
| `make manual-review` | 冒烟通过：固定种子抽 30 题、六问清单格式正确；顺带如实暴露 Q028 乱码题干（E 的 P0，见 §4） |
| `make regression --only struct_v1` | **incomparable**——根因 = 问题集/标注集指纹变化（PR#36 改写 questions/expected_sources 后未重提基准锚点），**与 C 无关**（指纹闸门按设计工作）；检索明细 top-K 重合 0.97 / rank-1 一致 0.9833，与"少数题干改写"量级自洽。E 标注定版后重跑 + `--promote` 重锚即归位 |

**未完成（报告已如实标注）**：全量终跑留命令——回答侧四指标尚无实测数字；20/20 拒答无实测；人工抽检清单已生成、未签署。均待 E 标注清零 + LLM 就绪后 `make experiment CFG=configs/experiments/final_v1.yaml` 一条命令补齐。

**小笔误（P3）**：报告 §4 拒答标记串引用与代码不完全一致（写的"无法给出有依据"，实际 `ABSTENTION_MARKERS` 为"无法给出"/"无法可靠判断"）——不影响行为，顺手更正即可。

### 3.7 PR#43（E）= 名不副实的空交付 + feature/web 基线漂移警告

head = `feature/web`（`7c309f0`），squash 合入 `e6b1243`。

**实际内容 = 3 文件 +2 行**：

| 文件 | 内容 | 问题 |
|---|---|---|
| `evaluation/datasets/review_wide_interval.csv` | **仅表头一行，零数据行**（question_id,page_start,page_end,current_keyword,suggested_keyword,is_validated） | "P1 复核数据"实为空表——复核尚未开始 |
| `scripts/datasets/review_wide_interval.csv` | 同一文件逐字节复制 | **位置错误**：数据集权威位置是 `evaluation/datasets/`，`scripts/` 下不应有 datasets 目录 |
| `commit_message.txt` | 0 字节 | 垃圾文件，意外入库，应删除 |

另：CSV 带 UTF-8 BOM。

**标题声称 vs 事实**：PR 标题"完成前端修复与 P1 复核数据交付"——`web/` 目录**自 PR#36 后零变化**（全分支核对：7c309f0 相对其基线 `957d281` 的 diff 同样只有这 3 个琐碎文件），"前端修复"不存在于任何分支；F2 markdown 渲染、F1/F3/F4 前端接线均未开始。提交信息与实际内容脱节。

**万幸**：提交内容足够少，即使基于旧基线合并也未造成回退（若为大改动即触发 R1/R4 级事故）。

**⚠ feature/web 基线漂移警告（须例会通报 E）**：远端 `feature/web` 当前 head `7c309f0` 基于 `957d281`（PR#36 时代），**缺 PR#37~#42 全部内容（约 2.4 万行）**——含 D 的 F1/F3/F4 后端三件（server/api/nodes.py 等）、B 的 hybrid_rerank 全套、C 的回答侧评测。E 后续若从该分支直接发 PR，将大面积回退 develop。**E 必须先 `git merge origin/develop` 并逐文件核对，或从最新 develop 切新分支**（PR#11/13/22/28/32 同类教训第五次预警）。

**P0/P1 门禁未动**：六题乱码（Q021/Q023/Q028/Q059/Q060/Q119）与宽区间复核（69 题全书级）依旧未解决——检索正式指标继续冻结，`--with-metrics` 继续禁开。

### 3.8 PR#45（E 前端 F1~F4 与 P0/P1）= 部分完成，且误删 C 的交付

head = `feature/web`（`900fe08`），合入 `c401c78`。本轮 E 的提交内容**有实质工作量**（前端接线、题干修复、复核清单导出），但夹带了一次**跨域数据事故**，且三项任务只完成一半。

#### 3.8.1 ⚠ 事故：E 的 Revert 抹掉了 C 的第四周交付（D 已恢复）

**事实链**（`git log` 可复核）：E 的分支基于 `d6774b1`（**PR#41 时代，早于 PR#42**）→ `6946093`/`4313fb2` 提交自己的 P1 清单与前端 → `37aeca9` merge develop（此时 C 的 PR#42 内容进入分支）→ **`9703784` `git revert` 掉了这个 merge**（把 merge 带来的 develop 内容整体撤回，**含 C 的全部交付**）→ `900fe08` 再 merge 自己的工作树 → squash 合入 develop。

**被抹掉的内容**（`git diff adf69f0..c401c78`）：C 的 `evaluation/runners/{answer_eval,abstention_eval,__init__}.py`、`evaluation/datasets/abstention.py` + `abstention_questions.jsonl`、`generation/abstention.py`、`scripts/sample_manual_review.py`、`tests/unit/test_{abstention,answer_eval,test_judges}.py`、`docs/reliability-report.md`（132 行）、**`configs/experiments/final_v1.yaml`**（终跑配置），以及 `judges/judge.py`、`generation/llm.py`、`scripts/run_experiment.py`、`Makefile` 三目标被**逐个回退到 PR#42 之前**。**这正是 §3.7 预警的 R1/R4 型事故，第一次真正落到 develop 上。**

**为什么没被冲突拦住**：合并基线里 C 的文件在我的分支未被改动，develop 侧的删除因此被 git 静默应用——**零冲突不等于零丢失**，这也是我在 PR#34 会签时坚持"只比 `config_hash8` 不足以判可比"的同一类问题（这里连产物指纹都比不出）。

**D 的恢复动作**（提交 `c263234`，18 文件 +1165/−61，与 PR#42 原始增量逐位一致）：按 `adf69f0`（上一良好状态）`checkout` 回 6 个纯回退文件（`Makefile`/`judges/judge.py`/`llm.py`/`run_experiment.py`/`test_judges.py`/`datasets/README.md`）+ 11 个被删文件，保留 E 的实质改动（题干修复、P1 清单、前端）；顺手删除空文件 `scripts/fix_wide_interval.py`（PR#43 那个 0 字节 `commit_message.txt` 改名而来）。恢复后 **pytest 402/402**。

**给 E 的流程反馈**：①`git revert` 一个 merge 是危险操作，会把对方全部内容反向应用——要撤回自己的合并请用 `git reset --hard <自己的上一个提交>` 或 `git revert <自己的提交>`，**绝不要 revert merge 提交**；②开工前先 `git merge origin/develop`，本次若从最新 develop 切分支就不会有这一串；③提交前核对 `git diff --stat origin/develop` 只应出现自己域的文件。

#### 3.8.2 任务完成度逐项核实

| 任务（来自 §3.7/§4 的 D 反馈） | 结论 | 证据 |
|---|---|---|
| **F1 知识库状态** | ✅ 完成 | `App.vue` onMounted 取 `/healthz`，`kbStats` 绑定文档集合/知识节点/索引健康度/向量引擎四卡；离线态文案改为"服务离线"（原"占位数据"） |
| **F2 markdown 渲染** | ✅ 完成 | `marked` + `DOMPurify.sanitize`（`renderedAnswer` computed，异常降级纯文本）；依赖 `marked ^11.0.0`/`dompurify ^3.0.0` 已入 package.json 且 lockfile 登记（11.2.0/3.4.15）；**D 本机 `npm install` + `vite build` 通过**（33 模块） |
| **F3 节点详情** | ✅ 完成 | `CitationsCard.vue` 改用 `fetch('/nodes/' + source.node_id)`（api.md v0.14），不再拉整包 `/sources/{rid}` |
| **F4 检索模式选择** | ❌ **运行时不可用** | App 侧请求体正确（选了才带 `experiment`，`experiments` 取自 `/healthz`），但组件内 `const availableExperiments = ref([])` **遮蔽了同名 prop**（第 87 行），模板 `v-for` 绑到那个空 ref。**D 双重实证**：Vue 官方编译器 `bindingMetadata.availableExperiments = "setup-ref"`；运行时挂载测试传入两个实验，下拉实际只有 `["选择检索模式..."]`。修法＝删除该行局部 ref（保留 prop 并在模板用 `props.availableExperiments`） |
| **P0 六题题干重做** | ✅ 编码修复完成 / ◕ 衍生新问题 | `questions.jsonl` 全库 **0 处** ASCII `?` 乱码，Q021/023/028/059/060/119（+Q120）已是通顺中文；**但 `make audit` 仍判 blocked**（`QUESTION_TOKEN_ABSENT 3` = Q021/Q023/Q028）——三题新题干用了 camelCase 字段名（`subscriptionMatched`/`livelinessChanged`/`publicationMatched`），**双产物中零出现**（语料为 snake_case `subscription_matched` 等各 6 处）→ 换了另一类零命中实体。Q059/Q060/Q119 已转正 |
| **P1 宽区间复核** | ❌ 未完成 | `review_wide_interval.csv` 31 行 = **待办导出**：`suggested_keyword`/`note` **0/30 非空**，30 题中 26 题仍是全书级区间 `[7,288]`；`expected_sources.jsonl` **零改动**（标注未收窄）→ P1 遗留原样保留 |

#### 3.8.3 其他问题

| 级别 | 事项 | 处置建议 |
|---|---|---|
| P2 | `requirements.txt` 把 `numpy/pandas/tqdm/scikit-learn` 由 `==` 锁定改为 `>=` | 与"B 锁定版 + 干净环境可复现"约定冲突；建议回退到 `==`，或经 B/团队会签（D 未代改，属项目级依赖策略） |
| P2 | `evaluation/dataload_review_wide_interval.py` 硬编码个人路径 `c:\Users\ycfnc\Documents\Downloads\ZRDDS 用户手册.pdf` | 同 PR#22 的镜像私货一类问题；建议改参数化/相对路径 |
| P2 | 新增 `commits/todo_v1.2.0.md`（提交信息草稿，280 行）与仓库结构（指南 §4）无关；`web/RAG4ZRDDS/MOCK_MODE_TESTING.md`(801 行)、`docs/Mock_Mode_Testing.md`(291 行) 属过程文档 | 建议移出或合并到一份；`docs/` 与 `evaluation/` 的权威位置需保持 |
| P3 | `package.json` 脚本由 `vite` 改为 `npx vite`；`package-lock.json` 大范围重写 | `npx` 在无本地依赖时会尝试联网拉包，建议回退；lockfile 抖动建议只提交增量 |
| P3 | `server/core/pipeline.py` 加 `source_url: None`（MockRetriever，D 域，E 未声明） | 内容无害（mock 与 live 字段对齐），**D 追认**；纪律备注：跨域改动应在 PR 描述声明 |
| P3 | E 提交信息写"pytest 384/384 passed" | 那是 PR#42 合并前的用例数（现 402）；E 未跑其分支上的完整套件——**若其分支跑过 C 的测试就不会漏掉"误删 C 交付"** |

**一句话结论**：**任务完成度约 60%**——前端四项里 F1/F2/F3 真做了且质量不错、F4 是"接线接了一半"（App 侧对了、组件内部断了）；P0 的编码问题根治但换成零命中实体，闸门仍 blocked；P1 只产出待办清单。**外加一次必须通报的跨域误删事故（C 的交付全灭，D 已恢复）。**

### 3.9 D 代修：E 域前端明面缺陷 + 一处整合修复（2026-09-16 深夜，用户授权）

**触发**：次日演示需系统"看起来真的能用"。用户在 §3.8 审查后授权 D 直接修 E 域前端的可见缺陷。修完经**全链路 live 实测**（后端 408/408、前端构建 + 5 例组件测试、浏览器端到端）。

#### 3.9.1 修了什么

| # | 缺陷 | 性质 | 修法 |
|---|---|---|---|
| 1 | **F4 检索模式下拉恒为空** | 阻塞（§3.8 已实证） | `ChatInput.vue` 删掉遮蔽 prop 的局部 `const availableExperiments = ref([])`，模板改用 `props.availableExperiments`；**补 4 例回归测试**（含防护力验证：还原旧代码 2 例变红） |
| 2 | **vite 代理缺 `/nodes`** | 阻塞（F3 在 dev 下必然失败） | `vite.config.js` 补 `/nodes` → 后端；此前请求被 SPA fallback 当页面路由吞掉 |
| 3 | **markdown 答案无样式** | 观感（演示第一眼） | `App.vue` 给渲染容器加 `.answer-markdown` + `:deep()` 样式（标题/列表/代码/表格/引用）——**scoped 样式够不到 `v-html` 注入内容**，此前 markdown 结构虽有、样式全丢 |
| 4 | **相关度条重复且无样式** | 观感 | `CitationsCard.vue` 删掉遗留的 `.relevance-track`（与新的 `.relevance-container` 重复）；E 改了模板类名但 CSS 仍挂在旧类名上（`.relevance-row`/`.relevance-track`），已对齐并补进度条样式 |
| 5 | **节点详情是一堆 JSON** | 观感 + 可用性 | 改为结构化渲染：来源/v 徽标、印刷页·物理页、章节路径、正文（等宽、可滚动）、HTML 原文外链；mock 模式给可读提示而非 JSON |
| 6 | **外链改成了 `window.open`** | 可用性 | 恢复真实 `<a href target=_blank rel=noopener>`（E 原来加 `role=link`+`tabindex` 却无键盘处理，且弹窗可能被拦截） |
| 7 | **展示路径依赖 rAF，回答区可能永不挂载** | **严重（演示致命）** | 见 §3.9.2 |
| 8 | `package.json` 脚本改回 `vite`（E 改成 `npx vite`，无本地依赖时会联网拉包）；`start-dev.ps1` 重写为合法 PowerShell（原文件是批处理语法，`.ps1` 跑必报错） | 可用性 | 见对应文件 |

#### 3.9.2 必须记下的一处发现：Vue 过渡 + rAF 节流 = 回答区永不渲染

**现象**：浏览器里点"开始检索"，左侧流程四步全绿（检索与生成确实跑完），**主区始终停在空状态**，无任何 JS 报错。

**根因**：`App.vue` 的 `<Transition name="section-fade" mode="out-in">` 包着「空状态 ↔ 回答区」。`mode="out-in"` 要求**离场过渡完成后才挂载**新元素，而 Vue 结束离场靠 `requestAnimationFrame` 回调；本机实测该标签页 **`document.hidden === false` 但 rAF 一秒触发 0 次**（页面未被合成，如标签页被遮挡/在后台/部分 webview），于是离场永远停在 `leave-from leave-active`、回答区永不挂载。同理 `-enter-from` 是 `opacity: 0`，即便挂载也会不可见。

**修法**：把展示路径上的过渡包装全部换成普通元素（`App.vue` 三处 + `CitationsCard.vue` 两处：来源列表 `TransitionGroup`、详情面板、答案/骨架、错误提示、空状态切换）；**CSS 规则保留**，环境确认可靠后可恢复。修后在同一 rAF=0 环境下复测：回答区挂载且 `opacity: 1`、5 条来源卡可见、节点详情面板可见。

**为什么值得记**：①演示机器上任何"标签页被遮挡/切到后台再切回"都可能复现同类不渲染；②这类缺陷**不报错、测试也抓不到**（单测不跑过渡），只能靠真实浏览器看；③`-enter-from` 隐藏内容 = 所有"淡入"过渡在 rAF 停摆时都会静默吞掉内容，值得全队知道。

#### 3.9.3 整合修复：`/nodes` 跨实验回查（F3 × F4）

**问题**（本机实测复现）：F4 切到 `struct_multisrc_v1` 提问，拿到的 HTML node_id 去查 `/nodes/{node_id}` → **404**——节点详情表只在启动时按**默认实验**装载。两个同批交付的功能各自可用、**合起来不可用**。

**修法**：新增 `server/core/pipeline.py::NodeDetailIndex`——默认实验表随启动就绪，其余实验**首次回查时按需解析**其 Node 产物并缓存（纯 JSONL 解析，实测 1606 节点首次 0.04s、缓存命中 0.002s；表数上限 3 逐出最久未用；失败只记不重试），端点经 `asyncio.to_thread` 调用以免卡事件循环。响应新增 `experiment` 字段（api.md **v0.15**）。+6 例回归测试。

#### 3.9.4 本机全链路实测（2026-09-16 深夜）

| 环节 | 结果 |
|---|---|
| 后端 `pytest tests/` | **408/408**（402 + 6 例新回归） |
| 前端 `vite build` / `vitest run` | 构建通过（33 模块）/ **5/5**（HelloWorld + ChatInput 4 例） |
| live 服务启动 | 预热 7.7s 在端口绑定前完成；`/healthz` 报 `mode:live`、`kb` 真实（struct_v1 / 301 节点 / `struct_bge-m3_0a7830b7`）、白名单 13 个实验 |
| 真实查询（默认实验） | `DurabilityQosPolicy kind` → sources 1 + token 487 + done，**top-1 = 印刷 127/物理 133（真值）**；`connect()` 不存在题 → 正确拒答（9.0s） |
| 真实查询（F4 切换） | `struct_multisrc_v1` → 多来源共存（HTML `zrdds_dev_guide` + PDF `user_manual`），28.7s（含该实验首次装载）；`struct_bm25` → 15.8s，score 20.04（bm25 原始分量纲，与 api.md 量纲说明一致） |
| F3 端点（切模式后） | HTML 节点回查 200：`experiment=final_v1`（同 Node 集先命中）、v2.4、章节路径、真实 C API 原文、`source_url` 正确 |
| 浏览器端到端（IAB） | F1 四卡真实数据；F4 下拉 13 个实验可选、选 `struct_multisrc_v1` 后检索确为多来源；F2 答案 1131 字、markdown 元素齐全（P/STRONG/CODE/H3/UL/LI/**TABLE**/TR/TD）且 `opacity: 1`；F3 详情面板可见、显示节点原文与参数表、外链正确、无 JSON 堆；反馈面板出现 |
| 未完成验证 | **截图取不到**（IAB 面板未被合成，`screenshot` 报 guest capture failed）——视觉判断以 DOM/计算样式断言替代；`make setup` 的干净 venv 安装仍未跑（沿用 §2 缺口） |

**给 E 的交接**：D 代改的 5 个前端文件（`App.vue`/`ChatInput.vue`/`CitationsCard.vue`/`vite.config.js`/`package.json`/`start-dev.ps1`）均已加注释说明改因为何；`ChatInput.spec.js` 是新增的回归测试（防 F4 缺陷复发）。若 E 要恢复过渡动画，请在**未被遮挡的标签页**里验证后再启用。

### 3.10 用户实测反馈处理：中止回答 / 分数口径 / 三处缺陷（2026-09-17 凌晨）

用户次日演示前实测提出三项 + 一个想法，D 逐条处理并实测。**结论：三项全部修复，第四项（按来源格式展示详情）已实现**。

#### 3.10.1 ① 中止当前回答（新功能）

| 层 | 做法 |
|---|---|
| 前端 | `ChatInput` 在生成中出现「停止生成」按钮 → `emit('stop')`；`App.stopGeneration()` 调 `AbortController.abort()`。**已产出的 token 保留**（不因中止清空），`response-state` 由"已完成"改为"**已终止**"，并显示一行说明"引用与请求标识已保留，可继续提问或提交反馈" |
| 服务端 | `/query` 的 SSE 生成器捕获 `asyncio.CancelledError`：把**已产出的部分答案**以 `…（已终止）` 标注写入回查记录（`/sources/{rid}` 仍可读到引用 + 部分答案），然后 `raise` 让取消继续传播 |
| 上游 LLM | 生成器被取消 → `async for` 中断 → `generation/llm.py::stream_chat` 的 `finally` 关闭 `AsyncOpenAI` 客户端 → 上游流断开，不会继续白烧推理 |

**实测**：客户端在第 3 个 token 后断开 → 回查记录 `answer = "根据提供的检索…（已终止）"`、引用 5 条完好；**紧接着的下一问正常完成**（首 token 2.8s / 1249 tokens / 32.6s），无残留阻塞。浏览器实测：生成中点「停止生成」→ 按钮消失、部分答案 594 字保留、状态显示"已终止"、提示条出现。

#### 3.10.2 ② 相关度分数的口径问题（回答"BM25 下为什么显得很低"）

**结论：不是统计口径写错，是四条通路的分数根本不同量纲，而前端此前用同一把尺子渲染。** 旧逻辑 `score>1 → score/100 → clamp 0~1` 把 BM25 的 20 分显示成 "20%"、RRF 的 0.03 显示成 "3%"，看起来都像"很不相关"，可它们各自都是当次 top-1。

| 模式 | 分数含义 | 范围 | 跨查询可比 | 展示（v0.16 起） |
|---|---|---|---|---|
| `vector` | cosine 相似度 | 0~1（实测 0.46~0.78） | ✅ | 「向量相关度 xx%」+ 强/中/弱 |
| `hybrid_rerank` | 交叉编码器 sigmoid | 0~1（实测 0.084~0.991） | ✅ | 「精排相关度 xx%」 |
| `bm25` | Robertson BM25 原始分 | 无上界（实测 7~56） | ❌ | 「BM25 词面分 原始值」+ **池内相对**进度条 + 「第 N 位」+ 不可比说明 |
| `hybrid` | RRF 融合分 | ~0.016~0.033 | ❌（仅排序意义） | 「RRF 融合分 原始值」+ 池内相对 + 位次 + 说明 |

**所以"向量相关度"这个指标在 bm25/hybrid 下没有绝对比较意义**，只有**池内相对强弱与排序**意义（BM25 无上界、长文档天然偏高、换查询即换词表原点；RRF 是 rank 的函数、分值与相关性不成比例）。前端已按 `/healthz` 新增的 **`experiment_modes`** 自动切换标签与口径；均值的写法也分开（可比模式给百分比，不可比模式给"原始分均值（池内相对）"）。

**注意区分两件事**：以上是**显示口径**；"哪条通路检索更准"是**质量问题**，而正式 hit_rate/mrr 仍因 E 的标注未定版而冻结（§3.8.2），故汇报里不给通路间质量排名数字。

**runbook 新增 §8**（用户要求）：13 个配置按迭代顺序（基线单源 → 多源 → 分块对照 → 检索模式消融 → 多来源消融 → 精排/版本加权）列了分组、本机索引成本、演示用法与"为什么是这个顺序"，并含上面这张分数口径表与通路切换节奏。

#### 3.10.3 ③ 三处缺陷：页码、HTML 页数、打开原文

| 缺陷 | 根因（实测定位） | 修法 |
|---|---|---|
| **PDF 详情页码不正确** | `load_nodes_artifacts`（D 写 F3 时引入）读的是 SourceRef 命名 `page_print`/`page_physical`，而 **Node 产物 metadata 的契约字段是 `printed_page_start|end`、`physical_page_start|end`** → 详情里的页码恒为 `—`（此前我在浏览器里看到 `印刷页 — · 物理页 —` 误判为"HTML 本来就该空"，实际是同一个 bug 掩盖了 PDF 的情形） | 按产物契约取值 + 新增 `*_end`（节点可跨页，前端显示区间 `印刷页 80–81`）；HTML 的页字段是字面量字符串 `"None"`，统一归一为 `null` |
| **HTML 页数指标无意义** | HTML 来自 Doxygen 站点，没有页面概念；产物里页字段就是 `"None"` | 前端**按 `source_type` 分格式渲染**：PDF → 印刷页/物理页 + 正文；HTML → 不显示页码，改显示 `source_file`/`title` + 章节路径 + 原文外链 |
| **"打开 HTML 原文"完全不可用** | 产物里的 `source_url` = 配置中的**占位域名** `https://docs.zrtechnology.com/cdoc/html/…`（配置注释写明"A 试跑占位值，正式值待例会确认"）→ 点了必然打不开（DNS 都解析不了）。本地其实有 604 个真实 HTML 快照（`data/raw/developer-guides/cdoc_html/`） | 新增 **`GET /documents/{source_id}/{filename}`**：从实验配置 `sources[].path` 声明的本地目录按白名单提供原文（只读、单层文件名、防穿越）；服务端装载时把占位外部地址**改写为本地地址**（`/nodes`、`/sources/{rid}`、MCP 一并生效）；文件不存在则保留原值（不把"打不开"换成 404） |

**踩坑记录（值得写进审查流程）**：URL 改写第一版只挂在启动管线上，而 `NodeDetailIndex` 的**按需装载走的是另一条路径** → 切实验后 "打开原文" 又退回占位域名；已收敛为**单一装载入口** `load_nodes_for_config()`，两条路径共用。第二版又踩：`cfg.sources` 的元素是 **`SourceCfg` 对象而不是 dict**，`isinstance(src, dict)` 过滤把它们全跳过 → 本地化静默失效（0 条改写）；已兼容两种形态并加回归测试。第三版踩：端点最初只认**当前管线**的 `source_roots`，而默认实验（纯 PDF）没有登记任何目录 → 多来源实验产生的链接一律 404；改为**启动期从全部实验配置合并**的白名单。

**实测（live）**：PDF 详情 `印刷 80–81 · 物理 86–87`（与卡片 `page_print 80` 一致）；HTML 详情 `source_type=html`、无页码、`title=DDS_Publisher_create_datawriter`、`source_url=/documents/zrdds_dev_guide/group___c_publication.html` → **HTTP 200 / 193KB / 真实 Doxygen 页**；卡片经 `/sources/{rid}` 拿到的链接同样 200。浏览器实测：PDF 卡片详情显示"PDF 手册"格式标记 + 页码范围 + 正文；HTML 详情无页码、显示文件与原文外链。

#### 3.10.4 ④ 想法评估：节点详情按来源格式展示

**可行，且已实现**（就是 §3.10.3 的第二行）。当前形态：`/nodes/{node_id}` 返回 `source_type`/`source_file`/`title`/页码区间/`section_path`/`text`/`source_url`，前端按 `source_type` 分模板渲染——PDF 走"页码 + 章节 + 正文"，HTML 走"文件/标题 + 章节路径 + 正文 + 原文外链"。

**还能再往前一步的三档（按性价比排序，供决策）**：

1. **PDF 显示所在页的缩略图/截图**（最直观）：需要把 PDF 页渲染成图片（`pymupdf` 之类）并新增 `GET /documents/user_manual/page/{n}.png` 一类的端点；`data/raw/*.pdf` 在本地可读，成本≈1 个端点 + 1 个依赖，能把"印刷页 127"变成"看到那一页"。
2. **HTML 内嵌预览**：把 `/documents/...` 放进 `<iframe>` 展示，省掉"跳出去再回来"；风险是 Doxygen 页面自带相对引用的 css/js，需要确认能从本地目录正确加载（同目录平铺，通常可行）。
3. **右侧原文抽屉**（PDF 图 + HTML iframe 统一容器）：交互最好，但属于前端布局改造，工作量最大。

**建议**：演示按现状即可（已经比"一堆 JSON"和"点不开的链接"强很多）；若时间允许，第 1 档投入产出比最高。

#### 3.10.5 用户复看后的两处调整（同日）

1. **runbook §8 改按"实际加入时间线"重排**（原按逻辑分组读起来别扭）：列首加**加入日期**（`git log --diff-filter=A` 可复核），顺序＝配置真正进仓库的时间：
   `08-25 example_v1` → `08-27 struct_v1` → `09-01 semantic/hybrid_v1`（三方案对比）→ `09-07 struct_bm25` → `09-12 struct_multisrc_v1`（HTML 接入）→
   `09-13 struct_hybrid / multisrc_bm25 / multisrc_hybrid` → `09-15 hybrid_rerank / ver20 / ver24` → `09-16 final_v1`。
   并补了"时间线怎么读"：前四行先让单来源跑起来、再回答"分块方案选哪个"；09-12 起知识源扩到多来源后**同一批消融重跑一遍**；09-15 叠精排与版本加权；09-16 固化成产品态配置——这既是团队四周节奏，也是演示讲解顺序（runbook **v0.8**）。
2. **卡片元信息收敛**：①HTML 来源不再渲染"第 — 页 · 物理页 —"这类**空占位**（页字段为 null 时整段隐藏，只留来源 id；PDF 照旧显示"第 80 页 · 物理页 86"）；
   ②**未实现的图谱占位从界面移除**——卡片上的"图谱数据暂无（占位区域）"与汇总区的"图谱关联 · 后端未提供"统计卡一并删掉，相关死代码（`graphLinksTotal`/`graphLinkCount`/`graphLinkLabel`）清理。
   浏览器复验：多来源 5 张 HTML 卡片 meta 只剩 `zrdds_dev_guide`，全文无"图谱"字样；切回 `struct_v1` 后 5 张 PDF 卡片页码正常。

**验证**：pytest **420/420**（新增 12 例：页码字段映射 / 本地化改写 / `/documents` 端点与穿越拒绝 / 来源目录类型 / 模式映射）；前端 vitest **15/15**（新增 CitationsCard 7 例：分数标签按模式、PDF 页码区间、HTML 无页码 + 外链、卡片元信息空占位缺席）；live 与浏览器端到端见上。

## 4. 未完成任务与阻塞

| 事项 | 归属 | 现状与影响 |
|---|---|---|
| ~~六题题干重做~~ | ~~E~~ | **编码已修复（PR#45，全库 0 处 `?` 乱码）**；但 Q021/Q023/Q028 新题干改用 camelCase 字段名（`subscriptionMatched` 等）在双产物中零出现 → `make audit` 仍判 blocked（`QUESTION_TOKEN_ABSENT 3`）。**待 E 改用产物中的实际写法（snake_case）后重跑 `make audit`** |
| PR#36 P1 宽区间 keyword 复核 | E | **仍未完成**（PR#45 只导出待办清单 `review_wide_interval.csv`：30 题、`suggested_keyword`/`note` 全空、26 题仍全书级区间；`expected_sources.jsonl` 零改动） |
| ~~`hybrid_rerank` 实现 + §3.3 设计一致性拍板~~ | ~~B~~ | **已随 PR#38 交付并拍板**（§3.5）；~~剩余 D 两项~~ **已落地（2026-09-15）**：schema `hybrid_rerank.components` 必填（含 `uses_reference_index()` 简化为按 mode 判定、注释更新）+ README components 行更新，+1 校验测试，pytest 368/368 |
| ~~`answer_eval.py` runner（X2）~~ | ~~C~~ | **已随 PR#42 交付并审查合格（§3.6，X2 闭环）**：runner + judges 四指标 + 20 题拒答专项；剩余 = 全量终跑实测数字（`make experiment CFG=final_v1.yaml`，待 E 标注清零 + LLM 就绪，一条命令补齐） |
| `source_url` 正式进 wire（方案 A） | B/C/E 会签 | 回查通道已落地且被前端消费；SSE 仍 7 字段 |
| multisource 数据集接线 | D | 待标注定版：**命名已认可 B 的方案**（`questions_multisource.jsonl` / `expected_sources_multisource.jsonl`，B 在 evaluation.md §4 登记，用户 2026-09-15 拍板）+ multisrc 配置 dataset/expected_sources 指向 + Makefile audit 覆盖 |
| **feature/web 基线漂移（§3.7）** | E | 分支已在 PR#45 补做 merge develop（`900fe08`），但**过程中 revert merge 造成 C 交付被抹掉并进入 develop**（D 已按 `adf69f0` 恢复，§3.8.1）。**例会必须通报：①开工前先 merge develop ②禁止 revert merge 提交 ③提交前核对 `git diff --stat origin/develop`** |
| ~~B1：BM25 零分过滤改了 B 的测试断言~~ | ~~B~~ | **视为默认接受、不再单独追认**（B 历经 PR#26/#30/#38/#40 均无异议；改动方向正确——零词面重叠不构成证据。用户 2026-09-15 拍板） |
| ~~精排阻塞事件循环（§3.5.1）~~ | ~~B~~ | **已随 PR#40 修复并本机复核闭环**（热题 159/161 ticks；建议②经拍板撤销），详见 §3.5.1.1 |
| **前端实测四项问题（F1~F4）** | E 为主（F1/F3/F4 涉契约会签） | 2026-09-15 用户实测反馈，D 逐条对照前端源码与 api.md 核实**全部属实**；同日用户拍板后 F1/F3/F4 的 D 侧后端已落地（api.md v0.14，§4.1）。**PR#45 后 F1/F2/F3 ✅；F4 由 D 代修完成（§3.9，含 4 例回归）——四项经浏览器端到端实测全部可用** |
| E 的 P2 项（PR#45 夹带） | E | requirements 锁定改 `>=`（建议回退或 B 会签）、`dataload_review_wide_interval.py` 硬编码个人 PDF 路径、`commits/` 与两份 MOCK 文档属过程文件（§3.8.3） |
| 例会带回 | — | struct_bm25 prompt v0→v2（议题 8）、F1（filters 是否移出身份段）、feedback 字段会签（E/C）、base_url 正式域名、PR#34 两项通报 C、questions 大改写口径（C） |

### 4.1 前端实测四项问题（2026-09-15，D 代码核实）

| # | 问题 | 核实结论与证据 | 归属与处置 |
|---|---|---|---|
| F1 | 知识库状态无法查看，是摆设 | **属实**。`web/RAG4ZRDDS/src/App.vue` L34~55「文档集合 / 知识节点 / 索引健康度」三卡与 L82~90「向量引擎」卡全部写死「占位数据：未接入××接口」文案；唯一真实数据是顶栏 `/healthz` 状态徽标（服务在线 + mock/live 模式）。根因双向缺位：**API 层本就没有知识库统计端点**（api.md v0.13 仅 `/query`、`/sources/{rid}`、`/healthz`、`/feedback` 四个端点），E 无数据可接 | **D 侧已落地（2026-09-15 拍板）**：`/healthz` 附 `kb` 统计（experiment/retrieval_mode/index_dirname/node_total/sources[{id,version,chunks}]，启动时从 Node 产物实数）+ `experiments` 白名单（api.md **v0.14**）；剩余 E 按契约接线替换占位卡 |
| F2 | 答案不解析 markdown，可读性低 | **属实**。`App.vue` L148 `<pre class="streaming-response">{{ answer }}</pre>` 纯文本插值；`web/RAG4ZRDDS/package.json` 无任何 markdown 渲染依赖。Prompt v2 输出含标题/列表/代码块 → `#`/`-`/反引号全部字面显示 | E 引入 markdown 渲染（marked / markdown-it + DOMPurify 防 XSS，LLM 输出属不可信输入） |
| F3 | 「查看节点详情」显示的不是该节点原文，而是类似 /query 返回体且含 answer | **属实**（机制精确化：拉的是 `GET /sources/{rid}` 回查体，内容族与 /query 相同）。`CitationsCard.vue` L198~235：无论点开哪个节点，都 fetch **同一份** `/sources/{rid}` 整体记录并 `JSON.stringify` 全量展示 = `question + answer + 全部 sources[]`（落库形状见 `server/api/query.py` L67/L76）。且 chunk 正文在契约上就不下发（投影剥离，text 仅生成侧使用）——**「原文」当前 API 层不存在**，前端无从展示 | **D 侧已落地（2026-09-15 拍板）**：新增 **`GET /nodes/{node_id}`**（api.md **v0.14**）——启动时装载 node_id→详情表（同 source_url 表先例），按需返回单节点 text+section_path+双页码+source_url；**正文出网属"正文不下发"立场的定向放宽，待 B/C/E 追认**；SSE wire 仍 7 字段。剩余 E：详情面板改为取该端点（并消除"点谁都显示整包 JSON"） |
| F4 | 前端只能使用单源 vector 检索 | **属实**（默认演示路径下）。`/query` 请求体契约仅 `question`/`top_k`（api.md v0.13），**无 mode/experiment 参数**；检索实验由服务端启动期 `RAG_EXPERIMENT_CONFIG` 定死（默认 struct_v1.yaml = 单源 vector）。前端零检索模式选择器，ChatInput 的「语义检索 / Top-K 5」chip 是静态装饰（`ChatInput.vue` L13~14）。multisrc / bm25 / hybrid / hybrid_rerank 通路从 UI 不可达 | **D 侧已落地（2026-09-15 拍板）**：`/query` 新增可选 **`experiment`**（api.md **v0.14**）——白名单 = `configs/experiments/*.yaml`（`/healthz` 的 `experiments` 同源），`PipelineRegistry` 懒组装 + LRU 缓存（≤3，默认管线钉住，worker 线程组装不冻事件循环，逐出尽力 close）；未知 ID 422 列可用值；mock 忽略。剩余 E：选择器从 `/healthz` 取白名单、请求带 `experiment`；演示口径＝首次切换某实验前先点一题预热 |

**核实方法**：逐条对照 `web/RAG4ZRDDS/src/`（App.vue / CitationsCard.vue / ChatInput.vue / package.json）与 `docs/api.md` v0.13、`server/api/query.py`；未跑浏览器端到端（结论均来自源码与契约静态核实，与用户实测现象互证）。

## 5. Week 4 验收对照（指南 §19）

| 通过标准 | 现状 | 依据 |
|---|---|---|
| Hybrid Retrieval 可运行 | ✅ | 实验通路 + live 服务通路实测（RRF 0.0276~0.0318、引用制零重建） |
| Reranker 有实验数据 | ✅ | PR#38：四组对比报告 + 精排漂移/token 覆盖结构性证据（§3.5）；精排分量纲 v0.13 定死 |
| Unknown/Abstention 可工作 | ✅ | E1003 不存在 / 第 300 页越界两例 live 明确拒答且不虚构；**20 题专项 + 机器可读拒答判定已随 PR#42 交付（§3.6），待 `make abstention` 实测 20/20** |
| 有 Citation | ◕ | 双页码/来源分型/回查达标；回查通道带 `source_url` 且前端已消费；SSE 扩第 8 字段待会签 |
| 有自动/半自动 Evaluation | ◕ | 工具链闭环：检索矩阵与三指纹闸门 8/8 实测、`make audit` pass、回答侧 runner + 拒答专项 + 人工抽检清单交付（§3.6）且 402 单测绿；正式指标数字仍冻结（E P0/P1 未清零）、回答侧全量终跑待 LLM 就绪 |
| 有最终 Demo | ✅ | demo-runbook v0.7（§8 各实验运行策略）+ 四场景实测；前端支持**中止回答**、**本地原文跳转**、详情按来源格式；前端四项（F1 知识库状态/F2 markdown/F3 节点原文/F4 模式切换）**经 §3.9 代修后浏览器端到端实测全部可用**，并消除了"回答区在 rAF 停摆时不渲染"的演示致命风险；reranker 组可按 runbook 可选演示 |
