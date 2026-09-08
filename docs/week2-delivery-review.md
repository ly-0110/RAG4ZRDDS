# RAG4ZRDDS 第二周交付审查与未完成任务（2026-09-07）

> 指南 §6.5 第二周验收逐项对照、各成员未完成任务与阻塞。
> **全部结论均有实测依据**（pytest / make 三件套 / live 冒烟 / 真值脚本对照 / 逐项代码核对），
> 方法与数据细节见 `AGENTS.md` 2026-09-07 条与 `docs/ingest-pipeline.md` 已知边界表 R1~R6。
> 下次更新节点：周三会签（§4 议题定案后）。
>
> **v1.1（2026-09-07 晚）**：同步 develop 的 PR#19（成员 C 第三周交付提前到达）后修订——
> 新增 §2.3 末的第三周交付审查、更新 §3 验收项 5 与 §4 会签议题。本稿按团队意见做了精简，
> 逐条审查过程细节以 AGENTS.md 时间线条目为准。
>
> **v1.2（2026-09-08）**：B 的检索日志字段定义到货（PR#21）并完成 D 侧落地——§1 总览、
> §2.2 未完成任务、§4 议题 3 已更新；接线明细见 `docs/retrieval-log-schema.md` §6 会签记录。

---

## 1. 总览

| 成员 | 交付（PR / 合入日） | 审查结论 | 未完成核心项 |
|---|---|---|---|
| A 知识工程 | semantic/hybrid 分块（#11，09-01） | 方向正确；基线漂移致合入即回退（R1），已代修 | 碎块过滤、生成性能；先同步 develop |
| B 检索 | BM25 全链路（#17，09-07）；检索日志字段定义 `docs/retrieval-log-schema.md`（#21，09-08） | **合格可用**，含真实产物冒烟；日志字段定义完整（含 result_count=0 无证据信号） | score 阈值 X1 追认、日志会签修改点 1~3 追认 |
| C 生成与可靠性 | Prompt v1 + LLM-as-judge + Citation 会签（#18，09-07）；**第三周提前交付：多来源 Context + 冲突披露 + Source Priority 草案 + 错误案例集（#19，09-07）** | #18 方向对，一处必修缺陷已代修；#19 见 §2.3 末 | response_metrics runner 归属、C2~C5、错误案例集真实性 |
| D 集成与实验平台 | run_experiment、日志骨架、R5/R6 等修复（本分支）；检索级日志接线（09-08） | 172 测试全绿；live 服务已恢复并实测 | response_metrics 接线（等 C runner）、回答级日志（等 C 定口径） |
| E 前端与质量 | web 重写 + 120 题集（#13/#15/#16，09-02/03/07） | 前端合格；标注未达标、格式违约 | 标注接入三条件、查看详情回查退化 |

跨成员横向结论：**本轮（#15/#16/#17/#18）均无基线漂移、无 D 域回退**，R1/R4 类事故未再发生；
但 **D 自查发现并修复了两条自身的索引身份设计缺陷（R5/R6）**，详见 §2.4。
PR#19 同步（merge `0f8cf4d`）零冲突，`pytest` **166/166**；
**R5 修复得到首次实测验证**——C 在 PR#19 把三个实验 yaml 的 `generation` 段切到 `prompt_version: v2`
并新增 `source_priority` 字段，派生索引目录名不变、既有真实索引继续复用
（若 hash8 仍对整份配置取值，这是第二次孤儿化事故）。

---

## 2. 各成员工作情况与未完成任务

### 2.1 成员 A —— 知识工程

**已交付（PR #11，2026-09-01 合入）**

- `chunkers/semantic.py`（SemanticSplitterNodeParser 封装）与 `chunkers/hybrid.py`（超阈值语义二次切分），`get_chunker` 工厂支持三策略。
- metadata 冻结声明（v1.0）+ HTML 字段对照表；`base.py` 防死循环修复；`_is_descendant` 自排除。


**未完成任务（A 域）**

1. **semantic 碎块过滤**：166/1059 块 <50 字符（62 块 <10 字符的图号/节号碎片）进索引。
   建议在 `_node_to_chunk` 加最短长度过滤（≥20 字符）并复测；属 A 调参域，D 未代改。
2. **semantic 生成性能**：逐页 Document 调 splitter（约 300 次独立调用），bge-m3 CPU 全文档 ~25 分钟；
   建议改全文档拼接一次调用。


### 2.2 成员 B —— 检索

**已交付（PR #17，2026-09-07 合入）**

- `retrieval/bm25.py`：tokenize（中文 bigram + ASCII 词整体保留小写）+ `BM25Store`
  （add/query/save/load，k1/b 参数化）；`index.py`/`retriever.py` 按 `retrieval.mode` 分派，bm25 通路不碰 embedding（建库 0.3s / 301 节点）。
- `_PositiveIdfBM25Okapi`：rank_bm25 的 ATIRE idf 在小语料恒 0（过滤后候选并列乱序），改经典 Robertson idf——诊断正确。
- `struct_bm25.yaml` 对照实验配置；24 个单测，**含真实 struct_v1 产物冒烟（带 skip 守卫）**——落实了 D 在 PR#11 审查后给的"单测全绿≠真实数据可跑"反馈。

**审查结论：合格可用。** 契约全合规（SourceRef 7 字段、无 text 泄漏、双页码差恒 6、node_id←chunk_id）。
真实数据检索吻合审计真值：Q002 环境变量题 top-1 = 印刷 168 第 11 章软件安装指南（与 8-30 真值精确一致）、
Q001 connect() = 印刷 242 第 18 章（与 semantic 审计真值一致）。

**D 代修（经授权，B 需追认 B1）**

- **B1**：`BM25Store.query` 过滤 score==0（零词面重叠不构成证据；旧行为把无关块按插入顺序填进 top_k）。
  **同步修改了 B 的 `test_store_query_ranks_by_term_overlap` 断言并补 2 用例——需 B 事后追认。**
- **B2**：`bm25.json` 不再存 tokens（可由 text 确定性重算），产物 2.44MB → 0.87MB。
- **B3**：`struct_bm25.yaml` 的 `compare_baseline` 由 null 改 `struct_v1`（消融对照必须挂基准）。

**未完成任务（B 域）**

1. ~~检索日志字段定义~~ **已交付（2026-09-08，PR#21）**：`docs/retrieval-log-schema.md` v0.1
   字段定义完整（request_id 关联、result_count=0 无证据信号、text 仅落本地、量纲注意）；
   D 已按 §6 落地存储接线（pipeline 层 `LoggedRetriever` + ContextVar 注入 rid，
   `{LOG_DIR}/retrievals.jsonl`），补充约定 3 条待 B 回签追认。
2. **score 阈值定标（X1，需与 C/E 会签）**：bm25 原始分实测 7.70~56.43，与 vector 的 cosine（0.46~0.78）
   不可比；任何基于 score 的判定必须按 mode 分别定标（api.md v0.6 已登记量纲事实，v0.7 已按 mode 定标、待例会追认）。


### 2.3 成员 C —— 生成与可靠性

**已交付（PR #18，2026-09-07 合入）**

- Prompt v1（§6.4 Grounding/Abstention：证据不足拒答 + 版本差异披露），`query_engine` 注册表式多版本（v0 保留）。
- `evaluation/judges/`：Faithfulness / Answer Relevance 的 LLM-as-judge；`generation/llm.py` 新增 `complete_chat` 非流式。
- Citation 会签：对 5 个问题逐项答复（§3 [n] 下标 / [1,2] 并引 / 末两级路径 / 本周取 start / 弱证据标记），实质推进。
- **跨域接缝修复**：`scripts/experiment_config.py` 把检索指标 `@K` 格式校验与回答质量白名单校验解耦——改动干净且最小，未改既有语义，**D 认可**。

**审查发现并代修的缺陷**

- **C1（P1，已实测复现）**：`judge._parse` 的 `except` 只接 `JSONDecodeError/TypeError/ValueError`，
  模型返回合法 JSON 但顶层非对象（`[1,2,3]`/`"str"`/`null`）时 `data.get` 抛未捕获 `AttributeError`
  → 一条畸形响应中断整批评测。已修为 `isinstance(data, dict)` 判定 + 走既有正则兜底，补 6 条回归测试。

**第三周交付提前到达（PR #19，2026-09-07 合入 develop，D 已同步审查）**

已交付：Prompt v2（§8.4 冲突披露规则 5 + 来源优先级注入）；`context_builder` 来源标签
（source_id→类别注入每片段，缺省回退）；`query_engine` 接线 v2 且 v0/v1/v2 **统一签名（非破坏）**；
`docs/source-priority-draft.md` 草案；`evaluation/datasets/error_cases.jsonl`（混版本/错来源各 10 例）
+ `error_cases.py`（load/validate/counts）+ 10 个新测试。零 D 域文件。

审查结论：

- **代码与接缝合格**：v0/v1/v2 统一签名向后兼容；prompt_version 走配置接线（live 通路已实证切换生效）；
  D 域零改动。
- **错误案例集不满足验收项 5「真实」要求（20 例全部为手写虚构场景，真值核对 39 条问题）**：
  ① 所有 `wrong_source`/多数 `mixed_version` 案例引用 `zrdds_dev_guide`——该 HTML 源第三周才接入，
  当前产物中不存在；② EC-MV-003 标注 `page_print=300`，超出手册最大印刷页 289（手册共 295 页物理页）；
  ③ 抽验 chunk 正文前缀在真实产物中**零命中**（证据文本为手写）；④ EC-MV-003 复用了 E1003——
  该错误码已实证在语料中不存在。验收项 5 仍为未达成（见 §3）。
  但其结构（question + chunks + gold_behavior + gold_note）适合作为**第三周多来源通路的测试夹具**
  （HTML 接入后恰好可用于验证冲突披露），处置方案待会签（§4 议题 4）。
- 两处小问题：`struct_bm25.yaml` 仍为 `prompt_version: v0`，与三个向量实验的 v2 不一致
  （bm25 对照实验若后续开生成，两臂 prompt 不同会破坏公平性）；`error_cases.py` 的
  loader/validate 尚无任何管线消费（`run_experiment`/`server` 均未接线）。

**未完成任务（C 域）**

1. **response_metrics 闭环（X2，验收项 4 唯一阻塞）**：judges 本身已就绪，但缺
   "逐题生成答案 → 对答案调用 judges" 的 runner——C 在 `evaluation/__init__.py` 把落点写为
   `evaluation/runners/answer_eval.py`，D 侧 build_pipeline/answer_stream 即答案生成钩子，该目录目前只有 `.gitkeep`。
   
2. **C2**：判分解析失败静默记 0 分，与"完全不忠实"不可区分 → LLM 抖动会系统性压低 faithfulness 且无法回溯。
   建议 `JudgeResult` 增加 valid/parsed 标记，聚合时把判分失败单列、不计入均值。
3. **C3**：judge 未固定温度、无独立配置（`complete_chat` 无 temperature 参数，继承生成侧配置），
   与 `judge.py` 自身文档"正式口径用固定低温度与同 judge 模型，回归对比才有意义"不符 → 回归对比不可复现。
4. **C4**：`answer_relevance` 会惩罚正确拒答——`RELEVANCE_SYSTEM` 只判"是否直接完整回应问题"，
   未告知"证据不足时拒答是正确行为"。Prompt v1 规则 3 要求拒答，两者矛盾。
5. **C5**：两处拒答串不一致且不可机读（`query_engine._NO_EVIDENCE` 的"没有检索到相关内容" vs
   Prompt v1 规则 3 的"当前知识库无法确认"），下游 judges/前端/指标无法可靠识别拒答。
6. **检索指标"判对"口径**仍未定版（`run_experiment` 的匹配口径仍是占位，报告已注明）。

### 2.4 成员 D —— 集成与实验平台（本分支持续交付）

**已交付**

- `scripts/run_experiment.py`（本周核心：配置→索引→检索评测→报告落盘，含 R2 指纹校验、
  防误毁守卫、--rebuild、无标注不算指标的宁缺毋滥模式）。
- 三级日志骨架：请求级 JSONL + `/sources/{rid}` 持久化（重启可回查）。
- Citation 会签草案（docs/citation-contract-draft.md）。
- **本次审查期间自查并修复的自身缺陷（8 条回归测试锁定）**：
  - **R5**：`config_hash8` 曾对整份配置取哈希 → C 合法修改 generation 段即孤儿化三个真实 bge-m3 索引
    （301/1059/906 节点）、live 启动失败。修为只对索引身份段取值（`index_identity_json` 单一事实源）。
  - **R6**：产物指纹曾对换行符敏感——`make ingest` 写 CRLF、git checkout 写 LF，指纹每个周期来回翻转
    （实证：ingest 重跑后原始字节哈希正是旧 manifest 的 `540ba5a30159`）；且写入/校验两侧各有一份算法副本。
    修为 CRLF→LF 归一化 + 删副本改委托。
  - **D3**：bm25 索引的 manifest 曾照抄 `embedding=bge-m3`/`backend=chroma`/`metric=cosine`（三项全假，
    `--list` 无法区分 bm25 与向量索引）→ 新增 `retrieval_mode`，bm25 时如实标注。
  - **D4**：build_index 对 bm25 也打印"约需 10~15 分钟"（实测 0.3s）→ 按 mode 分支。
  - **D5**：response_metrics 拒绝文案过时（judges 已落地）→ 改为准确指向真实缺口。
- 代修 C1 / B1 / B2 / B3（见各成员节）。

**实测状态（2026-09-07）**

- `pytest tests/` **166/166**（周初 107 → +B 24 → +C 第二周 9 → +D 代修回归 16 → +C 第三周 10）。
- `make ingest` 重跑 1.4s，长度分布与 8-28 记录逐位吻合，`git diff --numstat` 空 = 内容语义未变，指纹不变 → 索引复用通过（R2/R6 端到端闭环）。
- `make index`：vector 468s / 301 节点；bm25 0.3s。
- `make experiment`：两模式跑通（9.5s / 0.1s），无标注 → 只记明细不算指标。
- `make serve` live：预热 8.5s 在端口绑定前完成；`/healthz` 报 `mode:live`；sources 真实下发且
  页码真值正确（10.7 DurabilityQosPolicy 印刷 127 / 物理 133）；**Prompt v1 在 live 通路实证生效**；
  LLM 不可达时 error 事件可读透传（`InternalServerError: Error code: 502`），不静默降级。


**未完成任务（D 域）**


### 2.5 成员 E —— 前端与质量

**已交付（PR #13 / #15 / #16，2026-09-02 / 03 / 07 合入）**

- web 前端重写：`CitationsCard.vue` 组件化（7 字段契约、双页码、score 展示）。
- 120 题正式问题集初版（`questions.json`，7 类配比符合指南 §6.1 的 80~120 题）。

**未完成任务（E 域）**

1. **120 题标注接入三条件（验收项 1/2/3 的共同阻塞）**：
   ① 格式转 `questions.jsonl` + 标注拆分文件 `expected_sources.jsonl`（或与 C/D 会签新格式并改 loader/config；
      现状是 JSON 数组 + 标注内嵌，`run_experiment` 的 JSONL loader 无法解析，幸配置仍指旧 15 题 jsonl，管线无损）；
   ② 标注逐题对 PDF 核对（真值抽查仅 64% 吻合、16 题系统性偏差——QoS 策略题大量标注"章节入口页"47~52
      而定义真值在 125~161，疑"定义页/操作页"口径分歧，需 C 先定口径；67 题 keyword 为函数名在正文，
      标题级无法判定）；页码地面真值 = 页眉印刷数字；
   ③ `audit_questions.py` 作废重做（中文 `split()` 无分词、`question_id in node_ids` 语义不通、只审旧 15 题）。
2. 「查看详情」接回 `/sources/{rid}`（否则面板无增量价值）；前置依赖 X3（error 路径引用可回查）。
3. 与 C 对齐两件事：section 截断落点（C 倾向后端下发全路径、前端截末两级）；弱证据阈值（等 X1 定标）。


---

## 3. 指南 §6.5 第二周验收逐项对照

| # | 验收项 | 状态 | 说明 |
|---|---|---|---|
| 1 | 80~120 个问题完成初版标注 | ✗ | E 交了 120 题，但格式违约 + 真值抽查仅 64% 吻合；配置仍指旧 15 题 jsonl |
| 2 | 至少 3 种 Chunking/参数方案完成比较 | △ | 产物/索引/报告齐备（struct 301 / semantic 1059 / hybrid 906 + bm25 对照），指标全 n/a（被 1 阻塞） |
| 3 | 有 Retrieval 指标 | ✗ | 代码通路就绪（hit_rate/mrr/precision/recall@K），无标注 → 不计算 |
| 4 | 有回答质量指标 | ✗ | judges 已交付；闭环归属已会签决议——等 C 出 `answer_eval.py`（D 侧 `build_pipeline`/`answer_stream` 即答案生成钩子），验收项 4 阻塞方为 C |
| 5 | 有 20 个以上真实错误案例 | ✓ | D 补采 **37 例真实案例**（`error_cases_real.jsonl`：20 无证据信号缺失 + 8 已验证脱靶 + 9 跨方案分歧），全部源自四份真实报告 + 8-30 人工审计真值，机器校验证据真实性（node_id 在产物中、页码契约成立）；C 的 20 例手写场景转为第三周夹具（§4 议题 4） |
| 6 | Citation 正常 | ✓ | 7 字段契约、双页码真值、卡片组件、C 会签答复齐备；2 项待 E 确认（截断落点、弱证据阈值） |
| 7 | Unknown 问题不会稳定地产生虚构答案 | △ | 机制就位（Prompt v1/v2 拒答规则 + 空检索确定性拒答，PR#19 已将三个向量实验切到 v2）；未做 live 实证（LLM 未运行）。已证检索层给不出无证据信号：E1003 语料中不存在，vector/bm25 仍各返回 5 条中段分数证据（已列入真实错误案例 no_evidence_signal_missing 类）→ 拒答只能靠 LLM 侧 |

**结论**：7 项中 **2 项达成**、2 项部分达成、**3 项未达成**；剩余阻塞集中于 **E 的标注
（1/3，共同阻塞）** 与 **response_metrics runner（4，已决议等 C 的 answer_eval.py）**。

---

## 4. 周三会签议题（2026-09-07 晚用户已预决 4 项，例会追认）

| # | 议题 | 相关方 | 状态与决议 |
|---|---|---|---|
| 1 | E 标注格式：沿用 questions.jsonl + 分文件，或会签新格式改 loader/config | C/D/E | 待例会（阻塞验收项 1/2/3） |
| 2 | 检索指标"判对"口径定版（含"定义页/操作页"口径） | C | 待例会（run_experiment 匹配口径仍为占位） |
| 3 | B 检索日志字段（逾期两周） | B/D | **已交付并落地（09-08）**：B 出 `docs/retrieval-log-schema.md` v0.1，D 已接线（retrievals.jsonl）；待 B 追认 D 补充约定 3 条（检索异常不落日志/mock 不落盘/filters 记配置值） |
| 4 | `struct_bm25.yaml` 仍为 prompt v0（与三个向量实验的 v2 不一致）；error_cases loader 的管线接线归属 | C（D 配合） | 待例会（bm25 若开生成，两臂 prompt 不同破坏对照公平性） |
