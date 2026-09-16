# 第四周交付记录（成员 D）

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

## 4. 未完成任务与阻塞

| 事项 | 归属 | 现状与影响 |
|---|---|---|
| 六题题干重做| E（或 C 定拒答口径） | 重写务必 UTF-8 全程（勿经 ASCII/ANSI 转码环节） |
| PR#36 P1 宽区间 keyword 复核 | E | 69 题全书级区间页码条件名存实亡；Q056 仍 10.34 错标 |
| ~~`hybrid_rerank` 实现 + §3.3 设计一致性拍板~~ | ~~B~~ | **已随 PR#38 交付并拍板**（§3.5）；~~剩余 D 两项~~ **已落地（2026-09-15）**：schema `hybrid_rerank.components` 必填（含 `uses_reference_index()` 简化为按 mode 判定、注释更新）+ README components 行更新，+1 校验测试，pytest 368/368 |
| ~~`answer_eval.py` runner（X2）~~ | ~~C~~ | **已随 PR#42 交付并审查合格（§3.6，X2 闭环）**：runner + judges 四指标 + 20 题拒答专项；剩余 = 全量终跑实测数字（`make experiment CFG=final_v1.yaml`，待 E 标注清零 + LLM 就绪，一条命令补齐） |
| `source_url` 正式进 wire（方案 A） | B/C/E 会签 | 回查通道已落地且被前端消费；SSE 仍 7 字段 |
| multisource 数据集接线 | D | 待标注定版：**命名已认可 B 的方案**（`questions_multisource.jsonl` / `expected_sources_multisource.jsonl`，B 在 evaluation.md §4 登记，用户 2026-09-15 拍板）+ multisrc 配置 dataset/expected_sources 指向 + Makefile audit 覆盖 |
| **feature/web 基线漂移（§3.7）** | E | 远端 feature/web（`7c309f0`）基于 PR#36 时代，缺 PR#37~#42 全部（约 2.4 万行）；后续 PR 不先同步 develop 必触发大面积回退。**例会通报 + E 开工前 `git merge origin/develop`** |
| ~~B1：BM25 零分过滤改了 B 的测试断言~~ | ~~B~~ | **视为默认接受、不再单独追认**（B 历经 PR#26/#30/#38/#40 均无异议；改动方向正确——零词面重叠不构成证据。用户 2026-09-15 拍板） |
| ~~精排阻塞事件循环（§3.5.1）~~ | ~~B~~ | **已随 PR#40 修复并本机复核闭环**（热题 159/161 ticks；建议②经拍板撤销），详见 §3.5.1.1 |
| **前端实测四项问题（F1~F4）** | E 为主（F1/F3/F4 涉契约会签） | 2026-09-15 用户实测反馈，D 逐条对照前端源码与 api.md 核实**全部属实**；同日用户拍板后 **F1/F3/F4 的 D 侧后端已落地**（api.md v0.14，§4.1）——剩 E 前端接线与 F2 markdown 渲染 |
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
| 有最终 Demo | ◕ | demo-runbook v0.2 + 四场景实测；缺口只剩 reranker |
