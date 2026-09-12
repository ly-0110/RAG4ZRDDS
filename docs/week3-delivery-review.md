# 第三周交付审查记录（成员 D）

> **v0.3（2026-09-12）**：新增 §9——A 第三周交付（PR#28）审查与 D 侧接线端到端实测；§10——B 第三周检索设计（PR#27）审查；**§11——第三周全员工作任务跟踪**（指南 §7 对照，全员）；§12——Week 3 验收对照与结论。同步修复 A 的 PR#28 带入的两处文档回退（ingest-pipeline.md v1.3 撞号、week2 review B 行回退，见 §9.3）。
> **v0.2（2026-09-11）**：新增 §7——B 第二周收尾（PR#26）审查与四实验指标真实性验证（三方三角验证），及处置方法。
> **v0.1（2026-09-08）**：首版，覆盖 E 的 PR#22（`b871bf8`，"修复问题集格式与本地回归验证"，merge `53e8099`）。
> 审查人：成员 D。审查方法沿用《week2-delivery-review》四步：基线核对 → pytest 全套 → 契约/格式核对 → 内容真值抽查。
> 同步状态：`feature/server-platform` 已 merge origin/develop（`fa39418`，含 PR#27 `7cf2687` + PR#28 `04c3327`）零冲突，pytest **238/238** 绿。

---

## 1. 总览

| 交付物 | 结论 |
|---|---|
| `questions.jsonl`（120 题 JSONL） | ✅ 格式达标（PR#15 违约修复）；题集大改写待 C 口径会签 |
| `expected_sources.jsonl`（120 条标注分文件） | ❌ **P0：标注依据为检索 top-1 （导致循环论证），不可用作评测真值** |
| `annotation_audit.jsonl` | ❌ "审计"= 与索引核对，非对 PDF 核对 |
| `scripts/improve_questions*.py`、`fix_questions_format.py` | ❌ **P0：假验证脚本**（页码校验上限 1000、"吻合率"是模拟值） |
| `scripts/build_index.py` / `retrieval/embeddings.py` / `.env.example` 改动 | ❌ **P1：跨域未会签环境私货**（本次已由 D 清理，见 §4） |
| `web/RAG4ZRDDS/src/components/CitationsCard.vue`（+127 行） | ✅ E 域内，视觉升级，7 字段契约未破坏 |
| `web/RAG4ZRDDS/docs/` 过程文档 10 篇 | ✅ 记录详尽；第三周前端方向 = CitationsCard 视觉增强，仍自研轻量页路线，**无 OpenAI 兼容/MCP 需求** |


## 2. P0-1 标注循环论证（阻断验收项 1/2/3）

**实证方法**：对 `expected_sources.jsonl` 全部 120 条与 `evaluation/reports/struct_v1.json`（PR#22 入库版）的检索明细逐条比对。

- **120/120 条标注页码 = 检索 top-1 页码**，`annotation_audit.jsonl` 的 `retrieval_page_print` 与标注页逐条相同。
- 即：标注是从检索结果**反推**的，`hit_rate@5=1.0 / mrr@5=1.0` 是构造产物，不是评测结果——**检索缺陷被固化成"标准答案"再给检索打满分，导致评测丧失发现缺陷的能力，评测无任何意义。**。



### 给 E 的整改路径

1. 逐题打开 PDF 对到**页眉印刷数字**，标注"答案实际所在页"；区分"策略定义页 / 操作页"口径（该口径分歧请与 C 会签定稿）。
2. 禁止用检索/实验报告反推标注；`improve_questions*.py` 的"吻合率（模拟）"不可再作验证依据。
3. 自查工具：D 的真值核对脚本（对产物按 keyword 反查页码 + 已知审计锚点）；提交前先自查再提 PR。


## 3. P0-2 假验证脚本

- `scripts/improve_questions.py`："真值抽查吻合率（**模拟**）" = 标注数 ÷ 题数——不是任何意义上的真值核对。
- 页码合理性校验上限为 **1000**：脚本硬编码的 309/316 等页码（**超出手册印刷页最大 289、物理页最大 295**）全部判"合理"。
- 仍引用旧格式 `questions.json`（PR#15 违约格式），与本次交付的 `questions.jsonl` 脱节。
- 处置：**作废重做或删除**（E 域，待 E 答复）；在真值标注完成前，任何"验证通过"结论不采信。

## 4. P1 跨域环境私货（b871bf8 混入，**本次已清理**）

E 在 QA 提交中未经会签修改了三个跨域文件，给 embedding 环境塞入镜像默认值与个人机器路径：

| 文件（域） | E 的改动 | 问题 |
|---|---|---|
| `scripts/build_index.py`（D） | `main()` 默认设 `HF_ENDPOINT=https://nexus.aliyun.com/` | **该域名不是 HF 镜像**（Maven 仓库域）；与本机实测相悖（见 §5）；该文件 docstring 自述"勿设 HF_ENDPOINT"自打脸 |
| `retrieval/embeddings.py`（B） | 默认设 `HF_ENDPOINT` 清华镜像；新增 `BGE_M3_MODEL_PATH` env；`Path.home()/Desktop/bge-m3` 硬编码兜底 | 清华镜像同本机实测相悖；Desktop 路径是 E 个人机器布局，对他人是死路径 |
| `.env.example`（D） | 新增 `BGE_M3_MODEL_PATH` + E 个人路径示例（`C:\Users\55386\...`） | 环境私货入模板 |

**处置（2026-09-08，用户授权 D 代修）**：三文件已恢复到 PR#22 改动前的会签状态——`embeddings.py`、`build_index.py` 与基线 `472ff70` 逐字节一致；`.env.example` 仅保留 D 自己的 LOG_DIR 注释。pytest 178/178 + `build_index --list` 冒烟通过。随下次 D 的 PR 入库。**若 E 本机确需本地模型目录，请在自己的 `.env`（不入 Git）解决，勿改仓库文件。**

## 5. 正确的镜像/网络配置方式（本机实测，团队参考）
注意：建议完全不要在业务代码里设置环境变量--每个人的情况不同，都需要进行自己的设置，那么就不能在会同步到git的文件中设置。
本机（Windows + huggingface_hub 1.29）实测结论，**任何成员不得在仓库代码/脚本中默认设置 `HF_ENDPOINT`**：

1. **默认直连**：`huggingface.co` 直连可用（本机下载 bge-m3 权重即直连完成）。清华源似乎已失效，走清华镜像拉文件**必失败**（`FileMetadataError`）——设 `HF_ENDPOINT` 反而弄巧成拙。
2. **模型已缓存时**（权重在 `~/.cache/huggingface/`），务必设：
   ```bash
   HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
   ```
   否则 SentenceTransformer 初始化会对每个 config 文件做 5 次重试 HEAD，挂数分钟（`make experiment` 假死实录）。建议写进运行环境而非代码。
3. **本地已有模型目录**：放入仓库 `models/{model}`（如 `models/bge-m3`），解析顺序自动优先（`embeddings.py::_resolve_model`）；`models/` 不入 Git。
4. **确需镜像的场景**（如 CI 无直连）：在**运行环境变量**中设置，不改代码；且所选域名必须是真实 HF 镜像（`hf-mirror.com`），`nexus.aliyun.com` 是 Maven 仓库域、`mirrors.tuna.tsinghua.edu.cn/huggingface.co` 根本不可用。
5. GitHub 资产下载慢/超时：release 资产前缀 `https://gh-proxy.com/` 断点续传（仅人工操作，不入脚本）。

## 6. P2 与遗留

- `questions.jsonl` 大改写（135 行 diff，题面/类型/难度变动）：问题集口径归 C 管，**需 C 会签确认**后再视为正式题集。
- X1/X2/X3 追认、B 补充约定 3 条 + B1 追认、C2~C5 反馈等既有会签事项不变（见 AGENTS.md 待办区）。

## 7. B 第二周收尾（PR#26，`4a83de1`）审查 + 指标真实性验证（2026-09-11）

**范围**：① chroma 1.5.9 绝对路径段 flush 竞态修复（`vector_store.py`/`index.py`/`build_index.py`）② `retrieval-log-schema.md` 会签回签（v0.2）③ 四实验"120 题真实指标"报告入库（struct_v1 0.6167/0.4054、struct_bm25 0.3250/0.2206、hybrid_v1 0.3000/0.1521、semantic_v1 0.0583/0.0311）。
**同步**：merge `901a5f4` 零冲突；pytest **207/207**；绝对路径时代四个既有索引经本地复跑全部正常加载（兼容性确认）。

### 7.1 代码审查结论

- ✅ 修复方向合理：persist 路径经 `os.path.relpath` 相对化 + 编码先行 + 预计算向量传入 + `close()` 轮询段目录 `data_level0.bin` 落盘（超时抛错——宁失败不出"构建成功但不可加载"索引）；6 个新测试锁定契约。
- ⚠ `os.path.relpath` 在索引目录与 cwd 跨盘符时抛 ValueError（Windows 边界，B 域后续加守卫）。
- ⚠ `build_index.py`（D 域）注释声称"import 排列会让 chroma flush 静默失效、机制不明"——**无因果依据的魔法思维**；改动本身（`retrieval._bootstrap` 模块单例引导）无害且合理。
- ✅ B 回签追认检索日志 D 补充约定 3 条（v0.2，修改点 1~3 无异议）；C 的「result_count=0 → 拒答」仍待 C。

### 7.2 指标真实性验证（三方三角验证）

背景：E 的标注问题（§2）未整改，B 却在 PR#26 中宣称"四实验 120 题真实指标"。验证方法与结果：

| # | 验证项 | 结果 |
|---|---|---|
| 1 | 四报告内部一致性（per_question 明细复算 hit/mrr vs 聚合值） | ✅ 逐位吻合，时间戳/耗时真实 |
| 2 | 本机同索引复跑四实验 vs B 报告 | ✅ struct/bm25/semantic **100% 逐题吻合**；hybrid 97.8%（融合并列边界非确定性，hit@5 差 0.8pp）→ **B 确实真实运行，非编造** |
| 3 | B 真实检索 vs E 标注（top-1） | ❌ 仅 **35/120** 吻合 |
| 4 | E 旧报告（标注来源，`93ace54` 版）vs E 标注 | 120/120 ——循环论证坐实（§2 结论在报告被 B 覆盖前再次确认） |
| 5 | E 旧报告 vs 规范索引真实检索 | ❌ top-1 仅 29% 相同、top-5 平均重合 0.30、**分数中位 0.80 vs 规范 0.67 系统性偏移**；但同为真实运行（~40s、与真实结果 top-5 有交集 0.79，排除 --fake-embed 与纯造假） |

**根因判定**：E 旧报告生成于 PR#22 时代——当时 `retrieval/embeddings.py` 带 `Path.home()/Desktop/bge-m3` 硬编码兜底（§4 已清理），E 在本机用**非规范 embedding 模型副本**跑了实验。权重不同 → 向量不同 → 排序不同 → E 的"标注"与规范索引的真实检索大面积错位。分数系统性偏高（0.80 vs 0.67）指向权重差异而非索引损坏（缺数据只会使分数偏低，且损坏在 chroma 1.5.9 上表现为加载即崩）。

**结论**：B 的数字是**真实测量**，但**指标无效**——
1. 标注是循环论证产物（§2）；
2. 且标注出自非规范模型副本，与被评测的规范索引不在同一向量空间；
3. 四方案排序（struct > bm25 > hybrid > semantic）**结构性偏向 struct_v1 系**——标注源自其同源检索，dense 系天然与 E 的副本排序更相关；
4. semantic 0.0583 崩盘数字**不可作质量结论**（碎块问题本身另由 D 的 R-notes 独立成立，无需依赖无效指标）；
5. B 引用无效标注出指标且未附任何 caveat，**违反宁缺毋滥先例**。

### 7.3 处置方法

1. **四报告 `metrics` 字段视同 void**：检索明细（per_question）保留可查，但指标数值不采信、不引用、不得用于跨方案结论或对比基线。
2. **真值标注到位后由 D 统一重跑刷新四份报告**（原"重跑 struct_v1.json"计划扩为四份；B 版报告届时被覆盖）。
3. **例会通报 B**：①引用任何标注出指标前必须先确认标注有效性（宁缺毋滥/附 caveat）；②"import 排列影响 chroma flush、机制不明"注释无因果依据，应删除或给出真实机制。
4. **例会通报 E**：标注整改新增第三条理由——除循环论证、未逐题对 PDF 核对外，标注还出自**非规范模型副本**的检索结果；模型副本问题自 §4 清理后已消除，但其产物（旧报告与标注）仍在库中。
5. **B1**（BM25 零分过滤追认）PR#26 未涉及，仍待 B。

## 8. 结论

- **PR#22（E）**：格式整改合格、前端改动合格；标注与验证脚本不合格，评测闭环在真值标注完成前不可用。验收项现状：2 达成 / 2 部分 / 3 未达成（不变，E 标注阻塞继续）。
- **PR#26（B，2026-09-11）**：代码修复合格（含既有索引兼容性确认）、会签回签完成；四实验指标经三方三角验证为**真实测量但无效**（§7.2），metrics 视同 void，不得用作结论或基线（§7.3）。
- **PR#28（A，2026-09-12）**：**合格，已由 D 接线**——html_loader 契约达标、产物逐字节可复现、semantic 两项遗留真实闭环；带入两处文档回退已由 D 修复（§9.3）。被 A 阻塞的 D 侧多来源端到端联调已完成（§9.5）。
- **PR#27（B，2026-09-12）**：设计文档合格，hybrid 引用既有索引零重建的决策合理；`components` schema 字段等三项 D 侧配套待 B 启动实现时落地（§10）。
- **第三周全员任务跟踪**：见 §11（指南 §7 对照）；Week 3 验收口径现状见 §12。

## 9. 成员 A 第三周交付（PR#28，`04c3327`）审查 + D 侧接线（2026-09-12）

**范围**：① `data_pipeline/html_loader.py`（997 行）+ `docs/html-loader.md` 契约文档 ② `data/processed/html_v1.jsonl`（1305 chunk）③ `chunkers/semantic.py` 两项遗留闭环（+13 回归测试）④ 对 `docs/ingest-pipeline.md` / `docs/week2-delivery-review.md` / `semantic_v1.yaml` 的跨文档更新。

### 9.1 四步审查结果

| 步骤 | 结果 |
|---|---|
| ① merge-base 基线核对 | ✅ A 分支头 `a995f7e` 包含 develop 侧全部已合修复（含 R3/R5/R6 与页码真值）——**PR#11 事故后 A 首次零基线漂移**（代码域） |
| ② pytest 全套 | ✅ **238/238**（207 → +31：html_loader 24 例 + semantic 回归扩充） |
| ③ 契约/格式核对 | ✅ 见 §9.2；metadata.py v1.0 冻结 Schema **未改动**即覆盖 html 分支 |
| ④ 内容真值抽查 | ✅ 见 §9.2 逐字节复现；另发现两处**文档域**回退（§9.3，已由 D 修复） |

### 9.2 html_loader 契约与产物核对

| 核对项 | 结果 |
|---|---|
| 来源治理 | source_id=`zrdds_dev_guide`（C 的 source_labels 已注册）、version=`"2.4"`（与 B PR#27 要求的等值过滤口径一致）、source_type=html |
| 规模 | 288 正文页解析（282 产出节点），1007 节点 → **1305 chunk**，6 个无节点文档——与 A 契约文档数字逐位一致 |
| 唯一性 | chunk_id 1305 条全局唯一；与 PDF 侧 `struct_v1_` 前缀零碰撞 |
| 页等价物 | 双页码四字段一律 `null`（metadata v1.0 html 分支允许）、`source_url` 1305/1305 非空 |
| content_type | 枚举受 Schema 校验（api 952 / tutorial 159 / guide 123 / error 49 / faq 22）；`error_code` 实测 0 条——与 8-30 审计"E1003 不存在"交叉吻合 |
| **可复现性** | **D 接线后实时产出与 A 入库的 `html_v1.jsonl` 逐字节一致**——产物非手写、参数与文档声明一致 |

### 9.3 发现的两处文档回退（已由 D 当日修复）

| 文件 | A 带入的回退 | 修复 |
|---|---|---|
| `docs/ingest-pipeline.md` | 变更记录 v1.3 撞号：A 以自己的 v1.3（09-07，semantic 闭环）**替换**了 D 的 v1.3（09-08，多来源注册式接入）条目；依赖清单 `html_loader` 仍标"⏳ 未交付" | D 的 v1.3 条目恢复；A 条目升 v1.4（含 D 接线实测）；依赖清单改 ✅；接缝签名章节更新为实际 API |
| `docs/week2-delivery-review.md` | §1 表 B 行回退到 PR#21 之前（"检索日志字段（逾期两周）"，实际 PR#21 已交付且 D 已接线、B 已回签）；出现两个 v1.2 版本头 | B 行按事实恢复；A 的闭环内容并入并升 v1.3（09-12）；留注释说明合并裁决缘由 |

**根因**：A 于 09-07 晚在**旧工作树**写好文档改动，09-12 合并 develop 时冲突裁决取了自家版本。与 PR#11 同根但**轻量**——代码零回退，仅文档。**给 A 的流程反馈**：修改他人维护的文档（ingest-pipeline / week2 review 属 D 域）必须以 develop 最新版为基线，冲突时逐行核对 develop 侧内容。

### 9.4 semantic 两项遗留闭环核对

- ✅ **碎块过滤**：`_node_to_chunk` 加 `min_chunk_chars`（默认 20，可配可关），对剥离锚点后正文判长；`semantic_v1.yaml` 注释正确提示"写进 params 会改变索引身份 hash8"（A 已理解 R5 语义）。
- ✅ **生成性能**：全文档拼**单个 Document** + 页锚点句流定位，embedding batch 从 ~287 次独立调用降为 1 次；patch 单测锁定。
- ✅ 同批修复两处新缺陷：页锚点控制字符泄漏进正文/索引、跨页 node 错页（句流标签 + 游标定位起始句，块起始页与 struct 单页口径一致）。
- ⚠ **真实复测待做（A 域）**：A 本机缺 bge-m3 权重，新切分下的真实块数/墙钟未测——本机环境就绪后按 `python -m data_pipeline.chunkers.semantic ...` 复测登记（A 契约文档 §2.1.4 已自记此边界）。

### 9.5 D 侧接线与端到端实测（**被 A 阻塞项销项**）

1. **接缝适配（D 域）**：A 实际交付 `build_html_chunks(doc_dir, *, base_url, source_id, version, max_chunk_chars, min_chunk_chars)`（`docs/html-loader.md` §5 指定接口），与 D 预留的 `load_html_nodes` 签名不同名——`scripts/ingest.py::_process_html_source` 已按实际 API 适配（params 袋透传 2500/20），模块 docstring 同步。
2. **多来源基线配置** `configs/experiments/struct_multisrc_v1.yaml` 入库：user_manual(pdf, 2.0) + zrdds_dev_guide(html, 2.4, url)；`source_priority` 留空待 C 草案会签；`compare_baseline: struct_v1`。
3. **ingest 实测**：PDF 301 + HTML 1305 = **1606 条统一 Node 集**（`data/processed/struct_v1__b95d1061.jsonl`），跨来源契约校验全过（source_id ∈ 注册表 / version 一致 / 分组页码差值 / 跨来源 ID 唯一）；先校验后落盘机制正常。
4. **inspect_nodes 分来源统计**：html 缺 source_url 0 / pdf 缺双页码 0 / 空文本 0 / 重复 ID 0；重复文本 34 条与 >2500 字符 5 块均为 A 已核实的源冗余与原子保护块（html-loader.md §6）。
5. **索引**：多来源 vector 索引 `struct_bge-m3_d57f695e` 构建中（1606 节点，CPU 预计 ~1h——`docs/index-rebuild-drill.md` 的 HTML 接入 30min 红线预警首次真实命中）；bm25 通路可即时构建。实验报告待索引完成后运行。

## 10. 成员 B 第三周设计（PR#27，`7cf2687`）审查（2026-09-12）

`docs/superpowers/specs/2026-09-11-week3-retrieval-design.md`（203 行）——设计先行、实现等 A 就绪（团队决策）。

- ✅ **Hybrid RRF 零重建方案合理**：`components` 引用既有 struct_v1(vector) + struct_bm25 索引（同一节点集），运行时 RRF 融合，避免重复编码；components 引**实验名**而非 hash8 目录名，与 D 的命名单一事实源约定一致。
- ✅ **schema 改动最小化**：`rrf_k` 入 `retrieval.params` 袋（Owner 自由区零校验）、子检索候选数复用既有 `candidate_top_k`，唯一新增字段 `components`。
- ✅ **components 不入 `index_identity_json`**：hybrid 无索引产物，不影响子索引定位——对 R5 语义的理解正确。
- ✅ **score 量纲第三次对齐 X1 决议**：RRF 分（0~2/61）与 cosine / BM25 原始分互不可比，按 mode 分别定标——与 api.md v0.7 的按 mode 定标决议一致。
- ✅ HTML version 口径 `"2.4"`：A 产物已按此落盘（§9.2），B 的前置会签条件已满足。
- **D 侧三项配套**（B 设计 §6 表，待 B 启动实现时由 D 落地，**触发条件已满足**）：①`RetrievalCfg` 新增 `components: dict[str,str]|None`（extra=forbid 严格模型 + hybrid 必填 + 引用实验名存在性校验）②`build_index` hybrid 分支跳过构建的 `--list`/manifest 对齐 ③`run_experiment` 对 hybrid 的索引存在性检查豁免。
- ⚠ **命名对齐一处**：B §4.4 提名多来源三件套 `multi_v1`/`multi_bm25`/`multi_hybrid`；D 已按仓库 `struct_*` 前缀惯例创建 `struct_multisrc_v1`（本日）。B 实现 `multi_hybrid` 时 components 直接引用实际配置名即可，例会一次对齐，不阻塞。

## 11. 第三周全员工作任务跟踪（指南 §7 对照，2026-09-12）

| 成员 | 指南 §7 任务 | 状态 | 交付物 / 阻塞 |
|---|---|---|---|
| **A 知识工程** | ① `html_loader.py` 解析 Doxygen HTML | ✅ PR#28 | 288 正文页、噪声过滤实测、质检全 0（§9.2） |
| | ② HTML Node 按 §7.2 Schema 落盘 `html_v1.jsonl` | ✅ PR#28 | 1305 chunk；Schema v1.0 未改即达标；URL 进 metadata；D 接线逐字节复现 |
| | ③（可选）第二 PDF《故障排查指南》接入 | ❌ 未做 | 可选项；偏移 −68 需先将 `PAGE_OFFSET` 参数化（html-loader.md §7.4 已记） |
| | 遗留：semantic 真实复测 | ⏳ | 碎块/耗时新数字待 bge-m3 环境（A 本机权重缺失）；语义修复本身已合入（§9.4） |
| **B 检索** | ① Metadata Filtering 验证 | ◌ 设计定稿 | PR#27 §3（接口第二周已接线）；执行等多来源索引——**本日已建成**，可启动 |
| | ② Hybrid RRF 初版 | ◌ 设计定稿 | PR#27 §2 零重建方案；触发条件（A 就绪）已满足，待 B 实现；D 三项配套见 §10 |
| | ③ §7.5 四场景跨来源验证 | ◌ 方案定稿 | PR#27 §4 验证矩阵；正式评测等 E 题集 + C 口径；降级路径（4 样例冒烟）可用 |
| **C 生成与可靠性** | ① 多来源 Context 组装 + 冲突披露 | ✅ PR#19 提前交付 | Prompt v2（§7 多来源 + §8.4 规则 5）live 通路已实证生效 |
| | ② Source Priority 规则草案 | ✅ PR#19 | `docs/source-priority-draft.md` 待会签；会签后 D 填入各配置 `source_priority` |
| | ③ 错误案例集扩容（混版本/错来源 ≥10 例） | ◌ 部分 | C 的 20 例经真值核对为手写虚构 → 转第三周夹具；**D 补采 37 例真实案例达标**（`error_cases_real.jsonl`，2026-09-07 决议④） |
| | （X2）response_metrics runner `answer_eval.py` | ❌ 未交付 | 验收项 4 阻塞方 C；D 侧 build_pipeline/answer_stream 钩子就绪 |
| **D 集成与实验平台** | ① ingest 多来源注册式接入 | ✅ 完成 | PR#23 骨架（17 例回归）+ 本日 PR#28 接线实测 1606 条端到端（§9.5） |
| | ② MCP Server 打底（OpenAI 门面条件未触发） | ✅ PR#23 | `server/mcp_server.py` stdio 端到端冒烟通；OpenAI 兼容门面经用户决策**不做**（E 自研轻量页） |
| | ③ 索引升级演练（全量重建 ≤30min、可回切） | ✅ 文档成文 | `docs/index-rebuild-drill.md` v0.1（PR#23）；本日多来源 1606 节点重建首次实测——**30min 红线预警真实命中**（§9.5-5），红线应对四选项待例会 |
| **E 前端与质量** | ① 问题集扩展跨来源题 | ❌ 阻塞 | P0 标注循环论证未整改（§2），跨来源题标注同样受 "逐题对 PDF/正文核对" 条件约束 |
| | ② 来源徽标区分 PDF/HTML、HTML 引用跳转 URL | ◌ 待核对 | CitationsCard 视觉升级已交付（PR#22/25，7 字段含 source_url）；徽标与点击跳转的 UI 细节 D 侧未逐项验证 |
| | ③ 回归：PDF-only 指标不低于 Week 2 基线 | ❌ 阻塞 | 四报告 metrics 视同 void（§7.2）；真值标注到位后 D 统一重跑四份报告，届时可做回归对照 |

> 图例：✅ 完成 · ◌ 部分完成/进行中 · ⏳ 待条件 · ❌ 未开始或阻塞。

## 12. Week 3 验收口径对照（指南 §19）与结论

**"PDF 手册和 HTML 开发指南能否作为一个知识体系回答问题？"**

| 通过标准 | 现状 |
|---|---|
| 两种来源均可独立解析 | ✅ pdf 六步链路（301）/ html_loader（1305）各自质检全 0 |
| Metadata 统一 | ✅ metadata.py v1.0 冻结 Schema 双来源共用（22 字段，html 分支页码 null + source_url 必填） |
| 可同时检索 | 🔶 统一 Node 集 1606 条已产出并校验；bm25 索引可即时构建；vector 索引构建中（本日）；hybrid 待 B 实现 |
| Citation 能区分来源 | ✅ source_id / source_file / source_url / 双页码按来源分型（HTML 引用跳 URL，PDF 引用报双页码）；X3 修复后 error 路径引用可回查 |

**结论**：多来源知识库的数据面（解析 → 统一 Schema → 统一 Node 集 → 可建索引）已闭环；检索面等本日 vector 索引建成后即"可同时检索"达成，hybrid 初版在 B 手上。评测面（跨来源题 + 真值标注）仍阻塞在 E 的 P0 整改与 C 的口径定稿。

**本次新增待办 / 会签**：① D 三项配套（B 启动 hybrid 时落地，§10）② multi_* 命名对齐（例会一次）③ `base_url` 正式值确认（现为文档站占位 `https://docs.zrtechnology.com/cdoc/html`）④ source_priority 填值（等 C 会签）⑤ A 的 semantic 真实复测 + 索引红线实测数据补入 `index-rebuild-drill.md` §5 演练记录表（本日 1606 节点计时）⑥ 例会通报 A：文档回退修复（§9.3 流程反馈）。

> 变更记录：v0.3（2026-09-12）新增 §9 A PR#28 审查与接线实测、§10 B PR#27 审查、§11 全员第三周任务跟踪、§12 验收对照；v0.2（2026-09-11）新增 §7 PR#26 审查与指标真实性验证、§8 补 PR#26 结论。v0.1（2026-09-08）首版。
