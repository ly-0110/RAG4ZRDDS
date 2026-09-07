# RAG4ZRDDS 第二周交付审查与未完成任务（2026-09-07）

> 维护人：成员 D。范围：PR#11(A)、#13/#15/#16(E)、#17(B)、#18(C) 的交付审查结论、
> 指南 §6.5 第二周验收逐项对照、各成员未完成任务与阻塞。
> **全部结论均有实测依据**（pytest / make 三件套 / live 冒烟 / 真值脚本对照 / 逐项代码核对），
> 方法与数据细节见 `AGENTS.md` 2026-09-07 条与 `docs/ingest-pipeline.md` 已知边界表 R1~R6。
> 下次更新节点：周三会签（§4 议题定案后）。

---

## 1. 总览

| 成员 | 交付（PR / 合入日） | 审查结论 | 未完成核心项 |
|---|---|---|---|
| A 知识工程 | semantic/hybrid 分块（#11，09-01） | 方向正确；基线漂移致合入即回退（R1），已代修 | 碎块过滤、生成性能；先同步 develop |
| B 检索 | BM25 全链路（#17，09-07） | **合格可用**，含真实产物冒烟 | 检索日志字段（逾期两周）、score 阈值会签 |
| C 生成与可靠性 | Prompt v1 + LLM-as-judge + Citation 会签（#18，09-07） | 方向对；一处必修缺陷已代修 | response_metrics runner 归属、C2~C5 |
| D 集成与实验平台 | run_experiment、日志骨架、R5/R6 等修复（本分支） | 156 测试全绿；live 服务已恢复并实测 | response_metrics 接线、检索/回答级日志 |
| E 前端与质量 | web 重写 + 120 题集（#13/#15/#16，09-02/03/07） | 前端合格；标注未达标、格式违约 | 标注接入三条件、查看详情回查退化 |

跨成员横向结论：**本轮（#15/#16/#17/#18）均无基线漂移、无 D 域回退**，R1/R4 类事故未再发生；
但 **D 自查发现并修复了两条自身的索引身份设计缺陷（R5/R6）**，详见 §2.4。

---

## 2. 各成员工作情况与未完成任务

### 2.1 成员 A —— 知识工程

**已交付（PR #11，2026-09-01 合入）**

- `chunkers/semantic.py`（SemanticSplitterNodeParser 封装）与 `chunkers/hybrid.py`（超阈值语义二次切分），`get_chunker` 工厂支持三策略。
- metadata 冻结声明（v1.0）+ HTML 字段对照表；`base.py` 防死循环修复；`_is_descendant` 自排除。

**审查发现的问题（均由 D 代修，A 侧需知悉根因）**

- **R1 事故**：分支基于未同步 D 域修复的旧基线开发，合入即回退——页码真值（+7/0 基）、D1~D5、
  `source_id` 必填、超长段兜底全部丢失，三方案产物页码全错（printed 13–301）、struct 退化 105 条。
  D 代修四文件恢复 + metadata 超集 + semantic 块起始页口径 + hybrid 字段泄漏清除 + 补 3 测试。
- **R3**：复制 `structure._split_by_subsections` 到 hybrid 时丢 `_has_intermediary` 过滤，
  5 级节点重复产出 → 真实产物 223 个 chunk_id 碰撞（建索引必炸）。D 代修 b595f09 + 嵌套树回归。
- **入库的 semantic/hybrid 产物疑似 mock 嵌入生成**（288/220 条 vs 真实 1059/906 条），已用真实 bge-m3 重跑替换。

**未完成任务（A 域）**

1. **semantic 碎块过滤**：166/1059 块 <50 字符（62 块 <10 字符的图号/节号碎片）进索引。
   建议在 `_node_to_chunk` 加最短长度过滤（≥20 字符）并复测；属 A 调参域，D 未代改。
2. **semantic 生成性能**：逐页 Document 调 splitter（约 300 次独立调用），bge-m3 CPU 全文档 ~25 分钟；
   建议改全文档拼接一次调用。
3. **流程纪律**：开发前必须先同步 develop——这是 R1 的根因，两次事故同款。

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

1. **检索日志字段定义（逾期两周）**：指南 §6 明确任务"给出检索日志字段定义，与 D 会签存储格式"，
   `server/core/request_log.py` 检索级仍挂占位。第三周首日催办。
2. **score 阈值定标（X1，需与 C/E 会签）**：bm25 原始分实测 7.70~56.43，与 vector 的 cosine（0.46~0.78）
   不可比；任何基于 score 的判定必须按 mode 分别定标（api.md v0.6 已登记量纲事实）。
3. 第三周 Hybrid 初版（向量 + BM25 RRF）落地时，沿用本轮养成的习惯：对真实产物走一遍冒烟。

### 2.3 成员 C —— 生成与可靠性

**已交付（PR #18，2026-09-07 合入）**

- Prompt v1（§6.4 Grounding/Abstention：证据不足拒答 + 版本差异披露），`query_engine` 注册表式多版本（v0 保留）。
- `evaluation/judges/`：Faithfulness / Answer Relevance 的 LLM-as-judge；`generation/llm.py` 新增 `complete_chat` 非流式。
- Citation 会签：对 5 个问题逐项答复（§3 [n] 下标 / [1,2] 并引 / 末两级路径 / 本周取 start / 弱证据标记），实质推进。
- **跨域接缝修复**：`scripts/experiment_config.py` 把检索指标 `@K` 格式校验与回答质量白名单校验解耦——改动干净且最小，未改既有语义，**D 认可**。

**审查发现并代修的缺陷（经授权）**

- **C1（P1，已实测复现）**：`judge._parse` 的 `except` 只接 `JSONDecodeError/TypeError/ValueError`，
  模型返回合法 JSON 但顶层非对象（`[1,2,3]`/`"str"`/`null`）时 `data.get` 抛未捕获 `AttributeError`
  → 一条畸形响应中断整批评测。已修为 `isinstance(data, dict)` 判定 + 走既有正则兜底，补 6 条回归测试。

**未完成任务（C 域）**

1. **response_metrics 闭环（X2，验收项 4 唯一阻塞）**：judges 本身已就绪，但缺
   "逐题生成答案 → 对答案调用 judges" 的 runner——C 在 `evaluation/__init__.py` 把落点写为
   `evaluation/runners/answer_eval.py`，该目录目前只有 `.gitkeep`；D 的 `run_experiment` 只跑检索不生成答案。
   **归属待周三会签**（C 出 runner，或 D 直接在 run_experiment 接 judges）。
2. **C2**：判分解析失败静默记 0 分，与"完全不忠实"不可区分 → LLM 抖动会系统性压低 faithfulness 且无法回溯。
   建议 `JudgeResult` 增加 valid/parsed 标记，聚合时把判分失败单列、不计入均值。
3. **C3**：judge 未固定温度、无独立配置（`complete_chat` 无 temperature 参数，继承生成侧配置），
   与 `judge.py` 自身文档"正式口径用固定低温度与同 judge 模型，回归对比才有意义"不符 → 回归对比不可复现。
4. **C4**：`answer_relevance` 会惩罚正确拒答——`RELEVANCE_SYSTEM` 只判"是否直接完整回应问题"，
   未告知"证据不足时拒答是正确行为"。Prompt v1 规则 3 要求拒答，两者矛盾。
5. **C5**：两处拒答串不一致且不可机读（`query_engine._NO_EVIDENCE` 的"没有检索到相关内容" vs
   Prompt v1 规则 3 的"当前知识库无法确认"），下游 judges/前端/指标无法可靠识别拒答。
6. **检索指标"判对"口径**仍未定版（`run_experiment` 的匹配口径仍是占位，报告已注明）。
7. 问题集 `version` 字段语义（120 题中 107 题用 'documented'，非"功能级版本约束"）待 C 定。

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

- `pytest tests/` **156/156**（周初 107 → +B 24 → +C 9 → +D 代修回归 16）。
- `make ingest` 重跑 1.4s，长度分布与 8-28 记录逐位吻合，`git diff --numstat` 空 = 内容语义未变，指纹不变 → 索引复用通过（R2/R6 端到端闭环）。
- `make index`：vector 468s / 301 节点；bm25 0.3s。
- `make experiment`：两模式跑通（9.5s / 0.1s），无标注 → 只记明细不算指标。
- `make serve` live：预热 8.5s 在端口绑定前完成；`/healthz` 报 `mode:live`；sources 真实下发且
  页码真值正确（10.7 DurabilityQosPolicy 印刷 127 / 物理 133）；**Prompt v1 在 live 通路实证生效**；
  LLM 不可达时 error 事件可读透传（`InternalServerError: Error code: 502`），不静默降级。
- **未验证**：生成侧实际出词（Ollama 与 `models/llm_gateway.py` 当时均未运行）。

**未完成任务（D 域）**

1. response_metrics 接入 run_experiment（等 X2 归属定案）。
2. 检索级/回答级日志字段接线（blocked on B 的字段定义与 C 的回答级字段）。
3. **X3 error 路径引用持久化**：已实证——客户端收到 5 条真实 sources，`/sources/{rid}` 返 404，
   该 rid 不在 `logs/sources.jsonl` 的 68 条内（根因 `query.py` 的 `cache.put` 只在成功路径）。
   修法小（sources 事件发出后即 `cache.put`），但涉及"失败请求是否可回查"的契约，待与 C/E 会签后改。
4. semantic/hybrid 索引重建（派生目录名已变，各约 40 分钟，跑那两个实验前必须先建）。
5. 4 个孤儿索引目录约 48MB（`7e0264df`/`7cea7efc`/`31cd85de`/`0f362cb3`）——Chroma 集合名烘死在
   目录名里无法改名复用，是否删除待定。

### 2.5 成员 E —— 前端与质量

**已交付（PR #13 / #15 / #16，2026-09-02 / 03 / 07 合入）**

- web 前端重写：`CitationsCard.vue` 组件化（7 字段契约、双页码、score 展示）。
- 120 题正式问题集初版（`questions.json`，7 类配比符合指南 §6.1 的 80~120 题）。
- 域纪律进步：PR#15/#16 零 D 域文件、基线最新（PR#13 曾覆盖 D 域 10 文件致 R4 事故，D 已代修恢复）。

**CitationsCard「查看详情」现状（2026-09-07 代码静态核对，未浏览器实测）**

- 9-03 实测的"点击无反应"（fetch 后只 console.log、模板不消费）**已在 PR#16 重写中修复**——模板现以
  `v-if="showDetails[s.node_id]"` 渲染独立详情面板。
- **但实现从"回查 `/sources/{rid}`"退化为直接复用 sources 事件里的数据**：按钮仅在 `requestId`
  存在时显示、却从不发请求；详情面板的 `content` 段恒空（SourceRef 7 字段无 text，服务端投影剥离）。
  PR#15 交付项"`/sources/{rid}` 回查集成"实际消失，"查看详情"相对卡片本身无增量信息。

**未完成任务（E 域）**

1. **120 题标注接入三条件（验收项 1/2/3 的共同阻塞）**：
   ① 格式转 `questions.jsonl` + 标注拆分文件 `expected_sources.jsonl`（或与 C/D 会签新格式并改 loader/config；
      现状是 JSON 数组 + 标注内嵌，`run_experiment` 的 JSONL loader 无法解析，幸配置仍指旧 15 题 jsonl，管线无损）；
   ② 标注逐题对 PDF 核对（真值抽查仅 64% 吻合、16 题系统性偏差——QoS 策略题大量标注"章节入口页"47~52
      而定义真值在 125~161，疑"定义页/操作页"口径分歧，需 C 先定口径；67 题 keyword 为函数名在正文，
      标题级无法判定）；页码地面真值 = 页眉印刷数字；
   ③ `audit_questions.py` 作废重做（中文 `split()` 无分词、`question_id in node_ids` 语义不通、只审旧 15 题）。
2. 「查看详情」接回 `/sources/{rid}`（否则面板无增量价值）；前置依赖 X3（error 路径引用可回查）。
3. 指南 §6 任务"对三方案做人工盲评抽检 20 题，补充主观体感证据"——未见产物。
4. 与 C 对齐两件事：section 截断落点（C 倾向后端下发全路径、前端截末两级）；弱证据阈值（等 X1 定标）。
5. 流程：前端功能提交前必须在浏览器实测（9-03"点击没反应"教训）。

---

## 3. 指南 §6.5 第二周验收逐项对照

| # | 验收项 | 状态 | 说明 |
|---|---|---|---|
| 1 | 80~120 个问题完成初版标注 | ✗ | E 交了 120 题，但格式违约 + 真值抽查仅 64% 吻合；配置仍指旧 15 题 jsonl |
| 2 | 至少 3 种 Chunking/参数方案完成比较 | △ | 产物/索引/报告齐备（struct 301 / semantic 1059 / hybrid 906 + bm25 对照），指标全 n/a（被 1 阻塞） |
| 3 | 有 Retrieval 指标 | ✗ | 代码通路就绪（hit_rate/mrr/precision/recall@K），无标注 → 不计算 |
| 4 | 有回答质量指标 | ✗ | judges 已交付，闭环未接（X2：缺答案生成 + runner） |
| 5 | 有 20 个以上真实错误案例 | ✗ | **全仓库零产物，且无人认领**（C 第三周任务写的是"扩容"，暗示本周应有基础集） |
| 6 | Citation 正常 | ✓ | 7 字段契约、双页码真值、卡片组件、C 会签答复齐备；2 项待 E 确认（截断落点、弱证据阈值） |
| 7 | Unknown 问题不会稳定地产生虚构答案 | △ | 机制就位（Prompt v1 规则 3 + 空检索确定性拒答）；未做 live 实证（LLM 未运行）。已证检索层给不出无证据信号：E1003 语料中不存在，vector/bm25 仍各返回 5 条中段分数证据 → 拒答只能靠 LLM 侧 |

**结论**：7 项中 1 项达成、2 项部分达成、4 项未达成；阻塞集中在 **E 的标注（1/2/3）** 与
**response_metrics runner 归属（4）**，另有 **错误案例集无人认领（5）**。

---

## 4. 周三会签待决议题

| # | 议题 | 相关方 | 备注 |
|---|---|---|---|
| 1 | X1：score 量纲与弱证据阈值按 mode 定标 | C/E/B | 量纲事实已入 api.md v0.6；单一阈值 0.5 在 bm25 下静默失效 |
| 2 | X2：response_metrics runner 归属（C 出 `answer_eval.py` 或 D 接入 run_experiment） | C/D | 验收项 4 唯一阻塞 |
| 3 | X3：error 路径引用是否可回查（`cache.put` 时机） | C/E/D | 已实证 404；E 的查看详情回查依赖此项 |
| 4 | 错误案例集（≥20 个真实错误案例）归属 | 全员 | 验收项 5，零产物且无人认领 |
| 5 | E 标注格式：沿用 questions.jsonl + 分文件，或会签新格式改 loader/config | C/D/E | 阻塞验收项 1/2/3 |
| 6 | 检索指标"判对"口径定版（含"定义页/操作页"口径） | C | run_experiment 匹配口径仍为占位 |
| 7 | B 检索日志字段（逾期两周） | B/D | 第三周首日催办 |
