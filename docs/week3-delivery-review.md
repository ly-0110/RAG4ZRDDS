# 第三周交付审查记录（成员 D）

> **v0.4（2026-09-12）**：结构重排（对齐 week2 review 版式）——全员任务跟踪表提前至 §1，§2 按成员组织（A/B/C/D/E），Week 3 验收对照与会签议题独立成 §3/§4；§5 镜像/网络配置内容不变；删除重复与过程性内容。
> **v0.3（2026-09-12）**：新增 A PR#28 审查与 D 接线实测、B PR#27 审查、全员任务跟踪、Week 3 验收对照；修复 A 带入的两处文档回退。
> **v0.2（2026-09-11）**：新增 B 第二周收尾（PR#26）审查与四实验指标真实性验证（三方三角验证）。
> **v0.1（2026-09-08）**：首版，覆盖 E 的 PR#22（`b871bf8`，merge `53e8099`）。
> 审查人：成员 D。审查方法沿用《week2-delivery-review》四步：基线核对 → pytest 全套 → 契约/格式核对 → 内容真值抽查。
> 同步状态：`feature/server-platform` 已 merge origin/develop（`fa39418`，含 PR#27 `7cf2687` + PR#28 `04c3327`）零冲突；合并时点 pytest 238/238，含 D 回归后终态 **239/239** 绿。

---

## 1. 第三周全员任务跟踪（指南 §7 对照，2026-09-12）

| 成员 | 指南 §7 任务 | 状态 | 交付物 / 阻塞 |
|---|---|---|---|
| **A 知识工程** | ① `html_loader.py` 解析 Doxygen HTML | ✅ PR#28 | 288 正文页、噪声过滤实测、质检全 0（§2.1） |
| | ② HTML Node 按 §7.2 Schema 落盘 `html_v1.jsonl` | ✅ PR#28 | 1305 chunk；Schema v1.0 未改即达标；URL 进 metadata；D 接线逐字节复现 |
| | ③（可选）第二 PDF《故障排查指南》接入 | ❌ 未做 | 可选项；偏移 −68 需先将 `PAGE_OFFSET` 参数化（html-loader.md §7.4 已记） |
| | 遗留：semantic 真实复测 | ◌ 复测完成，发现新问题 | 本机复测 583 块：碎块过滤有效（min=20、<50 块 166→50）；但 **18 块 >2500 字符（max 7175）**——`max_chunk_chars` 声明未消费，待 A 确认/修复后再替换产物；复测产物暂存 `semantic_v2.jsonl` |
| **B 检索** | ① Metadata Filtering 验证 | ◌ 设计定稿 | PR#27 §3（接口第二周已接线）；执行等多来源索引——**本日已建成**，可启动 |
| | ② Hybrid RRF 初版 | ◌ 设计定稿 | PR#27 §2 零重建方案；触发条件（A 就绪）已满足，待 B 实现；D 三项配套见 §4-1 |
| | ③ §7.5 四场景跨来源验证 | ◌ 方案定稿 | PR#27 §4 验证矩阵；正式评测等 E 题集 + C 口径；降级路径（4 样例冒烟）可用 |
| **C 生成与可靠性** | ① 多来源 Context 组装 + 冲突披露 | ✅ PR#19 提前交付 | Prompt v2（§7 多来源 + §8.4 规则 5）live 通路已实证生效 |
| | ② Source Priority 规则草案 | ✅ PR#19 | `docs/source-priority-draft.md` 待会签；会签后 D 填入各配置 `source_priority` |
| | ③ 错误案例集扩容（混版本/错来源 ≥10 例） | ◌ 部分 | C 的 20 例经真值核对为手写虚构 → 转第三周夹具；D 补采 37 例真实案例达标 |
| | （X2）response_metrics runner `answer_eval.py` | ❌ 未交付 | 验收项 4 阻塞方 C；D 侧 build_pipeline/answer_stream 钩子就绪 |
| **D 集成与实验平台** | ① ingest 多来源注册式接入 | ✅ 完成 | PR#23 骨架（17 例回归）+ 本日 PR#28 接线实测 1606 条端到端（§2.4） |
| | ② MCP Server 打底（OpenAI 门面条件未触发） | ✅ PR#23 | `server/mcp_server.py` stdio 端到端冒烟通；OpenAI 兼容门面经用户决策**不做** |
| | ③ 索引升级演练（全量重建 ≤30min、可回切） | ✅ 文档成文 | `docs/index-rebuild-drill.md` v0.1；本日 1606 节点重建实测 **24.8min——红线内**，记录表已填 |
| **E 前端与质量** | ① 问题集扩展跨来源题 | ❌ 阻塞 | P0 标注循环论证未整改（§2.5），跨来源题标注同受"逐题对 PDF/正文核对"约束 |
| | ② 来源徽标区分 PDF/HTML、HTML 引用跳转 URL | ◌ 待核对 | CitationsCard 视觉升级已交付（PR#22/25，7 字段含 source_url）；徽标与跳转 UI 细节 D 侧未逐项验证 |
| | ③ 回归：PDF-only 指标不低于 Week 2 基线 | ❌ 阻塞 | 四报告 metrics 视同 void（§2.2）；真值标注到位后 D 统一重跑，届时做回归对照 |

> 图例：✅ 完成 · ◌ 部分完成/进行中 · ⏳ 待条件 · ❌ 未开始或阻塞。

## 2. 各成员工作情况与未完成任务

### 2.1 成员 A —— 知识工程（PR#28，`04c3327`）审查 = 合格

四步审查：merge-base 干净（**PR#11 后 A 首次零基线漂移**）；pytest 239/239；契约核对 ✅；真值抽查 ✅。

**html_loader / html_v1.jsonl 契约要点**：source_id=`zrdds_dev_guide`（C 的 source_labels 已注册）、version=`"2.4"`（与 B 的等值过滤口径一致）、`source_url` 1305/1305 非空、双页码一律 null（**Schema v1.0 未改动**即覆盖 html 分支）、chunk_id 全局唯一；content_type 枚举受校验（api 952 / tutorial 159 / guide 123 / error 49 / faq 22），`error_code` 0 条与 8-30 审计"E1003 不存在"交叉吻合；**D 接线后实时产出与 A 入库产物逐字节一致**。

**semantic 两项遗留闭环**：`min_chunk_chars`（默认 20，可配可关）+ 全文档单 Document 一次 embedding batch（~287 次调用 → 1 次）+ 同批修掉页锚点控制字符泄漏与跨页 node 错页，patch 单测锁定。

**semantic 新代码真实复测（D 本机代测，2026-09-12；A 与 D 使用同一模型，经用户检验）**：583 块（旧 1059），min=20、<50 字符碎块 166→50——碎块过滤与性能修复有效。**但暴露疑似缺陷**：18 块 >2500 字符（max 7175）/ 17 块 >1200 token（旧产物 max 1341、0 块超限）。**根因已定位**：`max_chunk_chars` 在 `semantic.py` 仅赋值（L63 `self.max_chars`）从未消费，`_node_to_chunk` 只有 `min_chunk_chars` 下限过滤（L276）而无超长再切分；旧产物上限是"逐页 Document"的自然页长假象，全文档拼接后语义断点稀疏区（15.1 C接口简介 p221、9.3 DataReader p99 等长代码节）不再受页界约束。**待 A 确认**：是语义断点保护的有意设计（则需同步修改 §6.2 口径与文档）还是超长兜底缺失（则补 node 级句边界再切分）。复测产物存 `data/processed/semantic_v2.jsonl` 供对比，正式 semantic_v1 产物与索引未动。

**带入的两处文档回退（已由 D 当日修复）**：

| 文件 | 回退 | 修复 |
|---|---|---|
| `docs/ingest-pipeline.md` | 变更记录 v1.3 撞号：A 的 09-07 条目**替换**了 D 09-08 多来源条目；依赖清单仍标"⏳ 未交付" | D 条目恢复、A 升 v1.4、依赖状态 ✅、接缝章节更新为实际 API |
| `docs/week2-delivery-review.md` | §1 表 B 行回退到 PR#21 之前；出现两个 v1.2 版本头 | B 行按事实恢复、A 闭环内容并入升 v1.3 |

根因同 PR#11（旧工作树改动带病合并），仅文档域、代码零回退。**流程反馈（例会通报）**：修改他人维护的文档必须以 develop 最新版为基线，冲突时逐行核对 develop 侧内容。

### 2.2 成员 B —— 检索

**PR#27（`7cf2687`，第三周检索设计定稿）= 合格**：Hybrid RRF 零重建——`components` 引用既有 struct_v1(vector) + struct_bm25（同一节点集），运行时融合，避免重复编码；`components` 引实验名、`rrf_k` 入 params 袋、components 不入 index_identity_json（对 R5 语义理解正确）；score 量纲第三次对齐 X1 决议（RRF 分与 cosine/BM25 互不可比）；HTML version=`"2.4"` 前置条件已由 A 产物满足。

**PR#26（`4a83de1`，第二周收尾）= 代码合格 + 指标"真实测量但无效"**：

- 代码：chroma 1.5.9 flush 竞态修复（relpath 相对化 + 编码先行 + close() 轮询）方向合理，既有四索引兼容性经本地复跑确认；瑕疵：relpath 跨盘符 ValueError（B 域加守卫）、build_index"import 排列"注释无因果依据（向 B 提）。B 回签追认检索日志 D 补充约定 3 条 ✅。
- **指标三方三角验证**：本机同索引复跑与 B 报告逐题吻合（struct/bm25/semantic 100%、hybrid 97.8%）→ **B 确实真实运行**；但标注系检索 top-1 回显（§2.5）且出自**非规范 embedding 模型副本**（分数中位 0.80 vs 规范 0.67 系统性偏移）→ 四报告 metrics **视同 void**，不得用作结论或对比基线；四方案排序结构性偏向 struct_v1 系。B 引用无效标注未附 caveat，违反宁缺毋滥先例（例会通报）。

### 2.3 成员 C —— 生成与可靠性

- PR#19 第三周内容提前交付（多来源 Context + 冲突披露 + Source Priority 草案）已于 week2 review 审查（#18 必修缺陷 C1 已代修）；Prompt v2 在 live 通路实证生效。
- 错误案例集：C 的 20 例经真值核对为**手写虚构**（引用未接入的源、页码越界、正文零命中）→ 转第三周夹具；D 补采 37 例真实案例达标（2026-09-07 决议④）。
- **未完成**：X2 `evaluation/runners/answer_eval.py` 未交付（验收项 4 阻塞方 C，D 侧钩子就绪）；C2~C5 反馈未回应（C2 判分失败静默记 0 分 / C3 judge 未固定温度 / C4 relevance 惩罚正确拒答 / C5 拒答串不可机读）；`struct_bm25.yaml` 仍 prompt v0（议题 8，改前与 C 对齐）。

### 2.4 成员 D —— 集成与实验平台（PR#28 接线与端到端实测）

1. **接缝适配**：A 实际交付 `build_html_chunks(doc_dir, *, base_url, source_id, version, max_chunk_chars, min_chunk_chars)`（docs/html-loader.md §5），与预留签名 `load_html_nodes` 不同名——`scripts/ingest.py::_process_html_source` 已按实际 API 适配（params 袋透传 2500/20）。
2. **多来源基线配置** `struct_multisrc_v1.yaml` 入库：PDF 2.0 + HTML 2.4；source_priority 留空待 C 会签；compare_baseline=struct_v1。
3. **ingest 端到端**：301 + 1305 = **1606 条统一 Node 集**（`struct_v1__b95d1061.jsonl` 入库），跨来源契约校验全过（source_id ∈ 注册表 / version 一致 / 分组页码差值 / 跨来源 ID 唯一）；inspect 分来源统计全 0（html 缺 source_url 0 / pdf 缺双页码 0 / 重复 ID 0）。
4. **索引红线复核**：`struct_bge-m3_d57f695e` 全量重建 **1485.8s ≈ 24.8min——30min 红线内**（线性外推偏悲观：bge-m3 吞吐随 batch 规模改善）；`index-rebuild-drill.md` §5 记录表已填、§6 附实测修正。
5. **实验**：120 题 17.7s——`expected_sources` 显式置 null（EvaluationCfg 允许 null + runner 空值守卫 + 回归测试），只记检索明细、不产 void 指标；报告 `evaluation/reports/struct_multisrc_v1.json` 入库。
6. **⚠ 自测事故（当日修复）**：第一阶段的 html-only fail-fast 测试以"loader 未交付"为前提，A 交付后该前提失效——pytest 期真跑 html-only ingest，把工作树 `data/processed/struct_v1.jsonl` 覆盖为 html-only 内容（Git 版本无损，产物经单来源 ingest 确定性再生）；两个接缝测试改 monkeypatch 模拟 loader 缺席。**教训：接缝"缺席路径"测试在接缝交付后必须显式模拟缺席，否则测试会随交付变形成真实写操作。**

### 2.5 成员 E —— 前端与质量（PR#22，`b871bf8`）审查

格式整改合格：`questions.jsonl` 120 题 JSONL（PR#15 违约修复）+ `expected_sources.jsonl` 分文件，run_experiment 可消费；CitationsCard.vue 视觉升级合格（7 字段契约未破坏）。

- **P0 标注循环论证（阻断验收项 1/2/3）**：120/120 条标注页码 = 检索 top-1 页码——标注从检索结果**反推**，hit_rate@5=1.0 是构造产物，评测丧失发现缺陷的能力；语义错位实证 2 例（Q056 真值 10.7 印刷 127 被标到 10.34 印刷 163 等）。PR#26 三角验证再加一条：标注还出自**非规范 embedding 模型副本**的检索（分数中位 0.80 vs 规范 0.67 系统性偏移）。
- **P0 假验证脚本**：`improve_questions*.py` 的"吻合率"= 标注数 ÷ 题数（模拟值）；页码校验上限 1000（超出手册印刷页最大 289 的 309/316 全判"合理"）→ **作废重做或删除**。
- **P1 跨域环境私货（已由 D 清理）**：`build_index.py` / `embeddings.py` / `.env.example` 混入镜像默认值与个人机器路径（所设域名非 HF 镜像）——三文件已恢复会签状态随 PR 入库；若 E 本机需本地模型目录，在自己的 `.env`（不入 Git）解决。正确配置方式见 §5。
- **整改路径**：①逐题对 PDF **页眉印刷数字**核对，区分"策略定义页/操作页"口径（与 C 会签定稿）②禁用检索反推与"模拟吻合率"验证 ③提交前用 D 的真值核对脚本自查。

## 3. Week 3 验收口径对照（指南 §19）与结论

**"PDF 手册和 HTML 开发指南能否作为一个知识体系回答问题？"**

| 通过标准 | 现状 |
|---|---|
| 两种来源均可独立解析 | ✅ pdf 六步链路（301）/ html_loader（1305）各自质检全 0 |
| Metadata 统一 | ✅ metadata.py v1.0 冻结 Schema 双来源共用（html 分支页码 null + source_url 必填） |
| 可同时检索 | ✅ 1606 条统一 Node 集 → vector 索引建成（24.8min，红线内）→ 120 题跨来源检索实验通过（17.7s，明细落盘）；bm25 可即时构建；hybrid 待 B 实现 |
| Citation 能区分来源 | ✅ source_id / source_file / source_url / 双页码按来源分型（HTML 引用跳 URL，PDF 引用报双页码）；X3 修复后 error 路径引用可回查 |

**结论**：多来源知识库的数据面（解析 → 统一 Schema → 统一 Node 集 → 可建索引）与检索面（"可同时检索"）已闭环；hybrid 初版在 B（设计定稿、触发条件满足）。评测面（跨来源题 + 真值标注）仍阻塞在 E 的 P0 整改与 C 的口径定稿。

## 4. 会签与跨成员议题（例会带回）

1. **D 三项配套** ✅ **已会签（2026-09-12 用户四问拍板）并落地**：①接受 components 引用制设计（引实验名 / rrf_k 入 params 袋 / candidate_top_k 复用 / 不入索引身份段）②build_index 遇 hybrid 跳过 + 提示 + --list 标注子索引 ③三项现做——`RetrievalCfg.components` + hybrid 校验（必填/引用存在）、跳过分支、`run_experiment` 子索引存在性检查；+4 回归测试（全套 **243/243**）；跨域微调 B 的 test_retrieval hybrid 夹具（自引用配置满足存在性校验），**待 B 追认**。
2. **命名对齐**：B 设计 §4.4 提名 multi_v1/multi_bm25/multi_hybrid vs D 已建的 `struct_multisrc_v1`（struct_* 前缀惯例）——B 实现 hybrid 时 components 引用实际配置名，例会一次对齐。
3. **base_url 正式值**：现为文档站占位 `https://docs.zrtechnology.com/cdoc/html`，待例会确认。
4. **source_priority 填值**：等 C 的 source-priority-draft 会签后，D 填入各配置（草案建议 [zrdds_dev_guide, user_manual]）。
5. **X1/X2/X3 追认**：X1 按 mode 定标已落实（api.md v0.7，作废单一 0.5）；X3 已修复+回归；X2 阻塞方 C。B 补充约定 3 条已由 B 回签 ✅，仅剩 C 确认「result_count=0 → 拒答」。
6. **四报告 metrics void**：真值标注到位后 D 统一重跑刷新（struct_v1/struct_bm25/semantic/hybrid；multisrc 报告同为明细版，届时一并刷新）。
7. **向 B**：无效标注 caveat 纪律（宁缺毋滥）、"import 排列"注释删除或给出真实机制、B1（BM25 零分过滤）追认、relpath 跨盘符守卫。
8. **向 C**：C2~C5 反馈、X2 runner、题集大改写（135 行 diff）口径确认。
9. **向 E**：标注整改（§2.5 整改路径）、假验证脚本处置、跨来源题扩展。
10. **向 A**：semantic 真实复测（bge-m3 环境就绪后）、文档基线流程反馈（§2.1）。

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

> 变更记录：v0.4（2026-09-12）结构重排对齐 week2 版式（任务跟踪表提前至 §1、§2 按成员组织、§3 验收 / §4 会签独立成节、删重复与过程性内容，§5 不变）。v0.3（2026-09-12）新增 A PR#28 审查与接线实测、B PR#27 审查、全员任务跟踪、验收对照。v0.2（2026-09-11）新增 PR#26 审查与指标真实性验证。v0.1（2026-09-08）首版。
