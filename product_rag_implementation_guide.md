# ZRDDS 产品知识库构建与开发调试问答系统：一个月五人协作实施指南

> **项目目标**：构建针对 ZRDDS（臻融数据分发服务）的产品知识库与开发调试问答系统。第一阶段以《ZRDDS用户手册.pdf》为唯一知识源，完成一个可运行、可调试、可评价的最小 RAG 问答系统；随后逐步接入 HTML 开发指南等其他来源，形成统一的多来源知识库，并完成面向 ZRDDS 开发调试场景的问答、引用、可信度控制和系统评测。
>
> **开发周期**：4 周（约 1 个月）
>
> **团队规模**：5 人
>
> **总体技术路线**：`PDF → 解析/清洗 → Chunk/Node → Embedding → Vector Index → Retrieval → LLM → Citation`，第二阶段扩展为 `多来源独立解析 → 统一 Node/Metadata → Hybrid Retrieval/Rerank → RAG → Citation/Evaluation`。

---

## 1. 项目范围与最终交付物

### 1.1 核心目标

系统需要回答与 ZRDDS 有关的开发者问题，优先覆盖：

- API/SDK 使用
- 产品配置
- 错误码与异常排查
- 开发调试
- 操作流程
- 版本相关问题
- 知识库中不存在的信息的安全拒答

第一版不追求 Agent、多轮复杂工作流或 GraphRAG，而优先保证 **Retrieval 正确、答案有依据、来源可追溯、错误可控制**。

### 1.2 四周结束时的最低交付标准

- [ ] 能导入《ZRDDS用户手册.pdf》（295 页，原生文本型）
- [ ] 能完成 PDF 文本解析和结构化清洗
- [ ] 能生成带 Metadata 的知识节点（Node）
- [ ] 能建立向量索引并完成 Top-K 检索
- [ ] 能完成基础 RAG 问答
- [ ] 有一套至少 80~120 个开发者问题的测试集
- [ ] 能展示回答来源、页码/章节或原始 URL
- [ ] 对未知问题具备明确的“不确定/无法确认”机制
- [ ] 能统计至少 Hit Rate、MRR、Answer Relevance、Faithfulness 等指标
- [ ] 能比较至少两种 Chunking/检索策略
- [ ] 能接入至少一种 HTML 开发指南来源
- [ ] PDF 与 HTML 最终进入统一的知识表示和检索接口
- [ ] 有可运行的 Web/API Demo、README、部署说明和测试报告

---

# 2. 总体架构

## 2.1 第一阶段：单一 PDF Baseline

```text
                    用户手册 PDF
                         │
                         ▼
                 PDF Reader / Parser
                         │
                         ▼
                 文本清洗与结构恢复
                         │
                         ▼
                    Chunk / Node
                         │
                 Metadata 注入
                         │
                         ▼
                     Embedding
                         │
                         ▼
                    Vector Index
                         │
                         ▼
                     Retriever
                         │
                      Top-K
                         │
                         ▼
                  Context + Prompt
                         │
                         ▼
                         LLM
                         │
                  ┌──────┴──────┐
                  ▼             ▼
                Answer       Citation
```

## 2.2 第二阶段：多来源知识统合

```text
                 ┌───────────────┐
                 │ User Manual   │ PDF
                 └───────┬───────┘
                         │ PDF Parser
                         ▼
                    PDF Nodes
                         │
                         │
                 ┌───────┴────────┐
                 │                │
                 │ Unified Node   │
                 │ + Metadata     │
                 │                │
                 └───────┬────────┘
                         │
                 ┌───────┴───────┐
                 ▼               ▼
       Developer Guide      API/HTML Docs
            HTML                  HTML
                 │                 │
             HTML Parser       HTML Parser
                 │                 │
               Nodes             Nodes
                 └─────────┬───────┘
                           ▼
                    Unified Knowledge
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
              Vector               BM25
              Search              Search
                 │                   │
                 └────────┬──────────┘
                          ▼
                    Hybrid Retrieval
                          ▼
                       Reranker
                          ▼
                         LLM
                          │
                Answer + Evidence + Citation
```

---

# 3. 团队分工与职责边界

每个系统环节只有一个 Owner。具体“某周谁做什么、怎么做、用什么工具”统一写在第 5~8 节的每周任务分解中，本节只定义职责边界与交付物，避免两处维护同一份任务清单。

| 成员 | Owner 域 | 核心交付物 | 明确不做 |
|---|---|---|---|
| A 知识工程 | 解析 → 清洗 → 章节树 → 三方案分块 → Metadata | `data_pipeline/`、`data/processed/` 各方案 Node 集、文档结构与数据质量报告 | 检索调参、Prompt 编写、服务端代码 |
| B 检索 | Embedding → 索引 → Top-K/BM25/Hybrid/Rerank 实验 | `retrieval/`、检索对比实验报告、检索日志字段定义与分析 | 分块代码（只经配置选用 A 的产物）、日志基础设施、判分逻辑 |
| C 生成与可靠性 | Prompt → Context 组装 → Citation/Grounding/Abstention → 评测方法学 | `generation/`、`evaluation/judges/` 与指标口径文档、可靠性报告、错误案例集 | 问题集编写与标注（E 负责）、检索组件实现 |
| D 集成与实验平台 | 服务化门面 → 索引生命周期 → 实验流水线 → 日志/部署 | `server/`（api / openai_compat / mcp_server）、`scripts/run_experiment.py`、Docker 与 API 文档 | 实验结论解读（B/C）、前端页面 |
| E 前端与质量 | 前端路线落地 → Citation 呈现 → 问题集编写标注 → 回归执行 → Demo | `web/` 或 UI 改造补丁、`evaluation/datasets/` 问题集、测试报告、最终 Demo | 判分实现（C 负责）、管线代码 |

开源 Chat UI 与 MCP 封装只替代前端界面层；D 的职责在任何集成路线下都成立。

### 3.1 职责交界处的约定

- 日志：D 建采集与存储设施；B 定义检索日志字段并消费分析；C 定义回答日志字段。
- 问题集：E 编写并标注；C 审核标注口径并实现判分。
- Chunking：A 实现三方案；B 只通过 `configs/experiments/*.yaml` 选择方案，不改分块代码。
- 交接一律通过仓库产物（Node 文件、JSON 报告），不口头传数据。

### 3.2 共同责任

所有成员共同负责：

- Git 分支与 Code Review（目录 Owner 拥有对应目录的合并权）
- 每日同步关键进展
- 每周集成
- 记录技术决策
- 及时把发现的问题沉淀成 Issue

---

# 4. 项目仓库结构

顶层目录按职责域划分：谁的域谁拥有该目录的 Code Review 权（CODEOWNERS），与第 3 节一一对应。

```text
rag4zrdds/
├── README.md                      # D 维护：保证三行命令内可复现
├── docs/                          # 报告类，各自维护自己域的文档
│   ├── architecture.md            # D
│   ├── document-analysis.md       # A
│   ├── chunking-strategy.md       # A
│   ├── evaluation.md              # C（口径与方法学）/ B（检索实验数据）
│   └── api.md                     # D
│
├── data/
│   ├── raw/                       # 原始资料（大文件，gitignore）
│   │   ├── manuals/               # ZRDDS用户手册.pdf；ZRDDS故障排查指南.pdf（第三周可选接入）
│   │   └── developer-guides/cdoc_html/   # 自 source/cdoc/html 迁入：ZRDDS v2.4.0 Doxygen 文档（436 页）
│   ├── cleaned/                   # A：逐页清洗产物 pages.jsonl
│   └── processed/                 # A：各分块方案 Node 集 {struct,semantic,hybrid}_v*.jsonl（提交入库）
│
├── configs/experiments/           # D 定格式，A/B 填参数：一次实验一个 yaml
│
├── data_pipeline/                 # A
│   ├── pdf_loader.py              # PyMuPDF；物理页码与印刷页码双记录
│   ├── html_loader.py             # Doxygen HTML 解析（去导航/脚本，保 h1-h3/代码/表格/函数签名）
│   ├── cleaner.py                 # 页眉剥离等
│   ├── section_tree.py            # 双通道章节树（TOC 书签 × 正文标题）
│   ├── chunkers/                  # base.py + structure.py(A) + semantic.py(B) + hybrid.py(C)
│   ├── metadata.py                # Metadata Schema 单一事实源
│   └── quality_check.py           # 第 16 节清单的自动检查
│
├── retrieval/                     # B：embeddings / vector_store / bm25 / hybrid / reranker
│
├── generation/                    # C：prompt(版本化) / context_builder / query_engine / citation
│
├── evaluation/
│   ├── datasets/                  # E：questions.jsonl（80~120 题）+ expected_sources.jsonl
│   ├── runners/                   # retrieval_eval.py（B 口径）/ answer_eval.py（C 口径）
│   ├── judges/                    # C：LLM-as-judge prompt 与结果解析
│   └── reports/                   # D 流水线的落盘处（提交入库，回归对比依据）
│
├── server/                        # D
│   ├── main.py                    # FastAPI 入口
│   ├── api/                       # /query(SSE) /sources
│   ├── openai_compat/             # /v1/chat/completions 门面（对接开源 Chat UI）
│   └── mcp_server.py              # MCP 工具：query_knowledge_base / get_sources
│
├── web/                           # E：自研 Vue/React 或开源 Chat UI 改造补丁
│
├── indexes/                       # D：索引产物（gitignore），命名 {chunker}_{embed}_{hash}
│
├── scripts/                       # D 维护，全员使用
│   ├── ingest.py                  # raw → cleaned → processed
│   ├── build_index.py             # processed + config → indexes/
│   ├── run_experiment.py          # 重建索引 → 跑评测 → 写 reports/（第 10 节机制的载体）
│   ├── evaluate.py
│   └── inspect_nodes.py           # A 的 Node 抽查工具
│
├── tests/                         # unit（各自域内）/ integration / regression（E）
│
├── Makefile                       # make ingest / index / experiment / serve
├── .env.example
├── requirements.txt
└── docker-compose.yml
```

配套约定：

- 不入 Git：`data/raw/`、`data/cleaned/`、`indexes/`；必须提交：`configs/`、`data/processed/`、`evaluation/reports/`——这是实验可复现的最小集合。
- 初始化动作：把当前工作区 `source/` 下两份 PDF 与 `cdoc/html/` 移入 `data/raw/` 对应子目录后建立仓库。

---

# 5. 第一周：单一 PDF 知识库 Baseline

> **本周目标**：周末前打通《ZRDDS用户手册.pdf》→ 清洗 → 结构感知分块 → 向量索引 → Top-K 检索 → 基础 RAG → 最小 Demo。重点是链路跑通，不做指标、不磨界面。

## 本周任务分解

### 成员 A：知识工程

- [ ] PDF 清洗：PyMuPDF(fitz) 逐页提取文本，剥离固定页眉“臻融数据分发服务DDS 系统软件”与页码行，同时记录物理页码（1 基）与印刷页码（页眉印刷数字；本手册 印刷页 = 物理页 − 6，2026-08-29 页眉真值核对定值，旧 +7 作废）；产物 `data/cleaned/pages.jsonl`
- [ ] 双通道章节树 v1：`get_toc()` 书签为主通道，正文编号标题正则为校验通道（方法详见第 15 节）
- [ ] 结构感知 Chunker v1：三级节为知识单元，超大节沿四/五级子节下切，表格与代码块原子保护；产物 `data/processed/struct_v1.jsonl`
- [ ] 组织全员抽查 10~20 个典型页面，标记解析异常

### 成员 B：检索

- [ ] 固化 Python 环境（requirements 锁定版本），安装 LlamaIndex 核心组件
- [ ] 选定第一版 Embedding（bge-m3 等中文友好模型，先跑通一个即可）与向量库（本地原型建议 Chroma/FAISS）
- [ ] 基于 struct_v1 建立索引，封装 Top-K Retriever，输出 node_id/score/source

### 成员 C：生成与可靠性

- [ ] 确定 LLM 与调用方式，密钥进 `.env` 不入 Git
- [ ] Baseline Prompt v0：只含两条硬规则——“仅依据检索内容作答”“回答必须给出来源”
- [ ] 连接 Retriever 与 LLM 形成最小 query_engine，定义 context 格式

### 成员 D：集成与实验平台

- [ ] 创建仓库骨架（按第 4 节目录）、分支保护与 CODEOWNERS
- [ ] FastAPI 骨架：流式 `/query` 初版，失败时返回可读错误
- [ ] 将 A/B 的手工步骤固化为 `scripts/ingest.py` / `build_index.py`，配套 Makefile

### 成员 E：前端与质量

- [ ] 确定前端路线（第 13 节三条路线二选一）并搭最小问答页：输入、流式回答、来源展示
- [ ] 手写 10 个冒烟测试问题验证全链路
- [ ] 基于 `scripts/inspect_nodes.py` 建立 Node 抽查视图

## 本周明确不做

Agent / GraphRAG / Hybrid / Reranker / 指标体系 / 漂亮 UI。

## 周五验收

- [ ] 任意输入 10 个问题均能返回带页码来源的回答
- [ ] `inspect_nodes` 显示无空 Node、长度分布正常
- [ ] 全员在同一环境一键复现：`make ingest && make index && make serve`

**第一周交付：Baseline RAG Demo。**

---

# 6. 第二周：开发者场景、Chunk 调优与可靠性基础

## 第二周目标

> **回答“这个系统到底好不好”，并找出第一版最主要的问题。**

## 本周任务分解

### 成员 A：知识工程

- [ ] 实现 `chunkers/semantic.py`（封装 SemanticSplitterNodeParser）与 `chunkers/hybrid.py`（超阈值节语义二次切分）——工具：LlamaIndex node_parser；方案设计与调优参数见 6.2
- [ ] 三方案 Node 集落盘 `{struct,semantic,hybrid}_v1.jsonl` 并跑 `quality_check.py`
- [ ] 冻结 Metadata Schema（`metadata.py`）：PART/章/节路径 + 双页码一次到位，第三周 HTML 直接复用（Schema 见 7.2）

### 成员 B：检索

- [ ] 对三方案跑 Hit Rate/MRR@K——实验变量只经由 `configs/experiments/*.yaml` 切换，禁止改代码换实验
- [ ] 实现 BM25（rank_bm25 或向量库内置），为下周 Hybrid 备料
- [ ] 给出检索日志字段定义，与 D 会签存储格式

### 成员 C：生成与可靠性

- [ ] 实现评测判分：retrieval 指标口径（与 B 对齐）+ Faithfulness/Answer Relevance 的 LLM-as-judge——工具：LlamaIndex Evaluators 或自写 judge prompt，落 `evaluation/judges/`
- [ ] Grounding/Abstention 规则写入 Prompt（见 6.4），用“不存在信息”类题目验证拒答行为
- [ ] Citation 字段定版（见 6.3）：文件名 + 印刷页码 + 节号；与 D/E 会签前后端字段约定

### 成员 D：集成与实验平台

- [ ] **本周核心交付** `scripts/run_experiment.py`：读 yaml → 重建索引 → 跑统一评测集 → 落盘 `evaluation/reports/*.json`
- [ ] 三级日志设施（请求/检索/回答），字段来自 B/C 的定义
- [ ] `/sources` 接口返回引用明细供前端渲染

### 成员 E：前端与质量

- [ ] 编写并标注 80~120 题初版问题集（类型配比见 6.1），交 C 审核口径后转 `evaluation/datasets/questions.jsonl`
- [ ] Citation 卡片渲染：“第 X 页 第 Y 节”可点击跳转
- [ ] 对三方案做人工盲评抽检 20 题，补充主观体感证据

本周验收标准见 6.5。

---

## 6.1 建立正式问题集

建议最终形成 80~120 个问题，初期可以分为：

| 类型 | 建议数量 | 示例 |
|---|---:|---|
| API 使用 | 15 | 如何调用某 API |
| 配置 | 15 | 如何配置某参数 |
| 操作 | 10 | 如何完成某功能 |
| Error Code | 15 | E1003 是什么 |
| Debug | 15 | 为什么连接失败 |
| 代码理解 | 10 | 这段代码哪里有问题 |
| 版本 | 5~10 | v2.3/v2.4 差异 |
| 不存在信息 | 10 | 文档未提及的能力 |

每道问题至少记录：

```json
{
  "id": "Q001",
  "question": "...",
  "type": "debug",
  "expected_sources": ["..."],
  "expected_answer": "...",
  "version": "...",
  "difficulty": "medium"
}
```

---

## 6.2 Chunking 对比实验

比较三种策略：

```text
A. 结构感知 Chunk（主）：三级节为一个知识单元，超大节沿四/五级子节下切
B. 纯语义 Chunk（对照）：SemanticSplitterNodeParser 按 embedding 相似度确定句子边界
C. 结构 + 语义混合：结构分块后对超阈值节做语义二次切分（预期主推方案）
```

公平性约束（三条路线必须共享同一前提）：

- 共用同一套清洗产物（页眉页脚剥离后的文本）
- B 的 Citation 依赖事后把 Node 映射回章节树——章节树是三条路线共用的地基
- 相同 Embedding
- 相同 LLM
- 相同 Retrieval Top-K
- 相同测试集

C 方案调优参数清单（全部进入回归矩阵，禁止凭感觉定参）：

```text
超大节阈值        建议 2500 字符附近（127 个三级节中位数约 2263 字符）
二次切分方式      SemanticSplitter 或句子切分
表格/代码块保护   二次切分时的原子性开关
```

预期结论（必须以实测数据验证）：约 73% 的三级节天然落在 800–2500 字符区间，A 可能已够好；C 在约 50 个超大节上占优；B 在引用定位上吃亏。若实测与此相悖，本身就是有价值的研究发现。可选追加一组固定尺寸 sanity baseline（约半天成本），为最终报告提供对照参考系。

测量：

- Hit Rate
- MRR
- Answer Relevance
- Faithfulness

LlamaIndex 提供 Retrieval Evaluation 和 Response Evaluation；官方示例包含 `hit_rate`、`mrr`、Faithfulness 等指标。 [LlamaIndex Evaluation](https://llamaindex.openml.io/python/framework/understanding/evaluating/evaluating/)

---

## 6.3 Citation

每个 Node 保留：

```text
source_file
page
section
node_id
source_url（若有）
```

回答中至少显示：

```text
来源：ZRDDS用户手册.pdf，第 42 页，第 3.4 节
```

不要只显示“来源于知识库”。

---

## 6.4 Grounding / Unknown 控制

Prompt 明确要求：

1. 优先依据检索内容回答。
2. 不得虚构不存在的 API、参数、错误码。
3. 如果证据不足，明确说“当前知识库无法确认”。
4. 如果资料之间存在版本差异，要指出版本。

测试集要特别加入“知识库不存在的问题”，观察系统是否会自信胡编。

---

## 6.5 第二周验收

- [ ] 80~120 个问题完成初版标注
- [ ] 至少 3 种 Chunking/参数方案完成比较
- [ ] 有 Retrieval 指标
- [ ] 有回答质量指标
- [ ] 有 20 个以上真实错误案例
- [ ] Citation 正常
- [ ] Unknown 问题不会稳定地产生虚构答案

---

# 7. 第三周：从单一 PDF 扩展到多来源知识库

## 第三周目标

> **接入 HTML 开发指南，同时保持原有 PDF 能力不退化。**

核心思想：

> **多来源独立解析，统一知识节点；统一 Metadata，统一检索接口。**

## 本周任务分解

### 成员 A：知识工程

- [ ] `html_loader.py`：解析 Doxygen HTML（`developer-guides/cdoc_html/`，436 页）——去除导航栏/脚本污染，保留 h1-h3 层级、代码块、表格、成员函数签名；工具：BeautifulSoup；原则见 7.3
- [ ] HTML Node 按 7.2 Schema 统一落盘 `processed/html_v1.jsonl`，URL 进 metadata
- [ ] （可选）将《ZRDDS故障排查指南.pdf》作为第二 PDF 源接入，复用 pdf_loader

### 成员 B：检索

- [ ] Metadata Filtering：按 source_type/version 过滤，进 retrieval 统一接口
- [ ] Hybrid 初版：向量 + BM25 以 RRF 融合，为第四周正式对比热身
- [ ] 用 7.5 的 A/B/C/D 四类场景样例验证跨来源检索行为

### 成员 C：生成与可靠性

- [ ] 多来源 Context 组装：来源标签注入 Prompt；冲突披露话术（8.4 Conflict disclosure 提前至本周实现）
- [ ] Source Priority 规则草案（API Reference > Developer Guide > User Manual > FAQ），并用实测校准
- [ ] 错误案例集扩容专项：混版本、错来源两类各 ≥10 例

### 成员 D：集成与实验平台

- [ ] ingest 支持多来源注册式接入：新来源放入 raw 即可重建索引
- [ ] 若 E 选开源 Chat UI 路线：联调 OpenAI 兼容门面；同时完成 MCP Server 打底（`query_knowledge_base` / `get_sources`）
- [ ] 索引升级演练：全量重建 ≤ 半小时、旧版本可回切

### 成员 E：前端与质量

- [ ] 问题集扩展跨来源题：两来源联合类、版本差异类（对应 7.5 C/D 场景）
- [ ] 来源徽标区分 PDF / HTML，HTML 引用点击跳转 URL
- [ ] 回归：PDF-only 指标不低于 Week 2 报告基线

周五验收对应第 19 节 Week 3。

---

## 7.1 原始资料分层保存

```text
data/raw/
├── manuals/
│   ├── ZRDDS用户手册.pdf
│   └── ZRDDS故障排查指南.pdf      # 第三周可选接入的第二 PDF 源
└── developer-guides/
    └── cdoc_html/                # 自 source/cdoc/html 迁入：ZRDDS v2.4.0 Doxygen 文档（436 页）
```

不要先把 PDF 和 HTML 合并成一个纯文本文件。

---

## 7.2 统一 Metadata Schema

建议至少包含：

```json
{
  "document_id": "...",
  "source_type": "pdf|html",
  "source_name": "...",
  "source_url": "...",
  "title": "...",
  "section": "...",
  "page": 42,
  "version": "2.4",
  "language": "java",
  "platform": "linux",
  "content_type": "api|guide|faq|error|tutorial",
  "product": "ZRDDS"
}
```

其中 PDF 的 `page` 可以存在，HTML 的 `page` 可以为空；URL 则反过来。

---

## 7.3 HTML 解析原则

HTML 开发指南往往比 PDF 更适合进行结构化解析，应尽量保留：

```text
<h1> / <h2> / <h3>
代码块
表格
列表
链接
API 名称
参数名称
```

不要先把 HTML 全部变成纯文本再使用固定长度 Chunk。

建议结构化成：

```text
ZRDDS Developer Guide
 └── 实体 API
      └── DataWriter
           └── create_datawriter()
                ├── Description
                ├── Parameters
                ├── Return
                ├── Exceptions
                └── Example
```

---

## 7.4 多来源 Node 统一

```text
PDF Parser → PDF Nodes ─────┐
                            ├→ Unified Nodes → Index
HTML Parser → HTML Nodes ───┘
```

统一后的 Node 不要求文本结构完全一致，但 Metadata Schema 必须兼容。

---

## 7.5 多来源检索实验

用开发者问题测试以下几类情况：

### A. 单一来源即可回答

> 产品如何安装？

理想结果：User Manual。

### B. HTML 更适合回答

> `create_datawriter()` 的参数是什么？

理想结果：Developer/API Guide。

### C. 多来源联合

> 用户手册里的设备连接功能在 Java SDK 中如何实现？

理想结果：同时检索 Manual + Developer Guide。

### D. 冲突/版本问题

> v2.4 的 API 是否仍使用旧参数？

理想结果：能够区分版本和来源。

---

# 8. 第四周：Hybrid Retrieval、Reranker、Evaluation 与产品化

## 第四周目标

> **从“能用”提升到“可验证、可解释、可展示”。**

## 本周任务分解

### 成员 A：知识工程

- [ ] 按 W2/W3 数据质量报告修复解析缺陷（表格线性化、图片缺失登记）；产出最优分块方案的终版 Node 集与数据质量终版报告

### 成员 B：检索

- [ ] 正式四组对比实验：Vector / BM25 / Hybrid / Hybrid+Reranker（8.1/8.2）——Reranker 选 bge-reranker 类交叉编码器；结论写入 docs/evaluation.md
- [ ] Version-aware 检索（8.3）：版本作为过滤条件与排序加权

### 成员 C：生成与可靠性

- [ ] Abstention 行为定版：20 个“不存在信息”专项题全部不虚构
- [ ] 全量终跑评测：Retrieval + Response 全指标（第 9 节体系）+ 人工抽检 30 题（9.3）
- [ ] 可靠性测试报告与错误案例集终版

### 成员 D：集成与实验平台

- [ ] 回归自动化：变更一键触发 run_experiment 并与 reports/ 历史比对（第 10 节机制生效）
- [ ] Docker/compose 打包；README 保证三行命令内可跑
- [ ] 最终 Demo 环境（含可选的 MCP 宿主演示）

### 成员 E：前端与质量

- [ ] “有帮助/无帮助”反馈按钮与数据落库
- [ ] 全量回归与兼容性检查，输出测试报告
- [ ] 汇报材料：按第 22 节清单组织 Baseline → 结构分块 → Hybrid → Reranker 的指标证据链

周五验收对应第 19 节 Week 4。

---

## 8.1 Hybrid Retrieval

开发者问题中会出现大量精确 token：

```text
DomainParticipant
create_datawriter()
E1003
HistoryQosPolicy
v2.4
```

因此建议加入：

```text
Vector Search
      +
BM25 / Keyword Search
      ↓
Fusion
```

然后比较：

```text
Vector
BM25
Hybrid
Hybrid + Reranker
```

---

## 8.2 Reranker

推荐将第一阶段 Retrieval 输出 Top 20~50，再由 Reranker 选择最相关的 Top 3~8。

```text
Question
   ↓
Hybrid Retrieval
   ↓
Top 30
   ↓
Reranker
   ↓
Top 5
   ↓
LLM
```

不要在第一周就接 Reranker；必须先有 Baseline，才知道它是否真的产生提升。

---

## 8.3 Version-aware Retrieval

如果资料包含多个版本，版本必须进入 Metadata，并成为 Retrieval 条件或排序依据。

例如：

```text
user_manual_v2.3.pdf
api_v2.4.html
```

用户指定 `v2.4` 时，应优先检索 v2.4 内容，不能把不同版本内容无提示地拼接成一个答案。

---

## 8.4 可靠性策略

实现以下规则：

### Evidence first

先检索证据，再生成答案。

### Citation required

技术性事实原则上应该能对应一个来源 Node。

### Abstention

没有足够证据时不猜。

### Conflict disclosure

不同文档/版本冲突时明确说明。

### Source priority

可以为来源增加优先级，例如：

```text
API Reference > Developer Guide > User Manual > FAQ > 非官方资料
```

这不是绝对规则，应通过实际产品资料验证。

---

# 9. Evaluation 体系

## 9.1 Retrieval Evaluation

每个问题定义期望节点或期望来源集合：

```text
Q001
expected:
  - api-deviceclient-connect
```

比较实际检索结果。

建议指标：

- Hit Rate@K
- MRR@K
- Precision@K
- Recall@K

LlamaIndex 官方评测模块支持 Retriever Evaluation，并给出 MRR、Hit Rate 等排名指标。 [LlamaIndex Evaluation](https://llamaindex.openml.io/python/framework/understanding/evaluating/evaluating/)

---

## 9.2 Response Evaluation

建议至少包含：

- Correctness
- Faithfulness
- Answer Relevance
- Context Relevance
- Citation Accuracy

LlamaIndex 当前评测体系将 Retrieval Evaluation 与 Response Evaluation 分开，并提供 Faithfulness、Answer Relevancy、Correctness 等评估维度。 [LlamaIndex Evaluation](https://llamaindex.openml.io/python/framework/understanding/evaluating/evaluating/)

---

## 9.3 人工评测

LLM-based evaluation 不能完全替代人工检查，因此建议每周随机抽取 20~30 个问题人工检查：

```text
1. 是否回答了问题？
2. 技术事实是否正确？
3. 是否有文档依据？
4. Citation 是否准确？
5. 是否出现虚构 API？
6. 是否混用了版本？
```

---

# 10. 回归测试机制

每当发生以下变化，都要运行固定测试集：

- Chunking 修改
- Embedding 修改
- Retriever 修改
- Reranker 修改
- Prompt 修改
- LLM 修改
- 新增知识源

建立：

```text
evaluation/reports/
├── baseline.json
├── chunking_v2.json
├── hybrid_v1.json
└── final.json
```

禁止只凭“感觉效果更好”合并 Retrieval/Prompt 重大变更。

---

# 11. 每周团队协作方式

## 每日

每天 10~15 分钟同步：

- 昨天完成什么
- 今天做什么
- 当前阻塞是什么

只讨论影响进度的问题，不进行长时间技术争论。

## 每周

### 周一

明确本周验收目标和负责人。

### 周三

中期集成，所有成员在统一环境运行。

### 周五

完成：

- Demo
- Regression
- 指标
- 技术总结

然后确定下周优先级。

---

# 12. Git 与分支策略

建议：

```text
main
 └── develop
      ├── feature/pdf-parser
      ├── feature/chunking
      ├── feature/retrieval
      ├── feature/rag
      ├── feature/web
      └── feature/evaluation
```

规则：

- `main` 只接受稳定版本
- 每个功能使用 feature branch
- PR 必须至少 1 人 Review
- Evaluation/Regression 通过后才合并
- 不直接把 API key 等密钥提交到 Git

---

# 13. 第一版技术栈建议

## 核心

```text
Python
LlamaIndex
```

## PDF

优先验证：

```text
PyMuPDFReader / PyMuPDF
```

LlamaIndex 当前提供 `PyMuPDFReader` 用于读取 PDF。 [LlamaIndex File Readers](https://docs.llamaindex.org.cn/en/stable/api_reference/readers/file/)

## Chunk

```text
Structure-aware Chunker       自研，基于 TOC 书签 + 正文标题双通道章节树
SemanticSplitterNodeParser    对照组与超大节二次切分
```

固定尺寸 SentenceSplitter 不再作为研究主线；如需 sanity baseline 可临时启用。

## Index

第一版可以：

```text
VectorStoreIndex
```

VectorStore 的具体选型可以根据团队部署条件确定，例如本地原型使用 FAISS/Qdrant/Chroma 等；如果已经有 PostgreSQL，也可以评估 pgvector。

## Web/API

根据团队已有经验选择 FastAPI/Flask 等，不需要为了 RAG 框架强制更换后端技术。

## Frontend

三条可选路线：

```text
自研轻量页面      Vue/React + SSE + Markdown/代码高亮；第一版只实现问答、来源、状态和反馈
开源 Chat UI 改造  LibreChat / Open WebUI / assistant-ui 等；主要改造点是 Citation 渲染与来源跳转
MCP 封装          无需自建界面，把检索/问答暴露为 MCP 工具接入现有 Agent 宿主
```

无论哪条路线，最终 Demo 都必须能展示 Citation（页码 + 章节），这是四周交付物的硬性要求。注意：通用聊天 UI 默认不渲染“第 X 页 第 Y 节”式溯源卡片，选开源改造路线时这就是主要改造工作量；纯 MCP 路线下引用展示取决于宿主客户端能力。省下的前端时间应转投测试集与回归测试（见成员 E 职责）。

---

# 14. LlamaIndex 的实际职责边界

推荐把 LlamaIndex 当成**RAG 编排框架**，而不是“自动生成好知识库”的黑盒。

## 适合交给 LlamaIndex

- Document 表示
- Node/Node Parser
- SentenceSplitter
- Ingestion Pipeline
- Embedding 接口
- VectorStoreIndex
- Retriever
- Query Engine
- Response/ Retriever Evaluation

LlamaIndex 的 Node Parser 文档明确说明 Node Parser 可以独立使用、加入 ingestion pipeline，也可以在建立 Index 时作为 transformations 使用。 [Node Parser Usage Pattern](https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/loading/node_parsers/index.md)

## 必须由项目自己决定

- 产品文档结构如何理解
- 什么内容应该成为一个知识单元
- Metadata Schema
- 哪个来源更可信
- 版本冲突如何处理
- 哪些问题必须拒答
- 开发者问题集如何设计
- 最终 Evaluation 指标和通过标准

这一边界要明确，否则很容易把整个项目变成“调用 LlamaIndex API”。

---

# 15. Chunking 的推荐实施方法

本项目跳过固定尺寸分块研究，直接采用**结构为主、语义为辅**的路线。

## 手册实测结构结论

- 295 页，Word 2007 原生文本型 PDF，非扫描件，中文提取干净
- 内嵌书签 405 条、最深 5 级：11 个 PART → 27 章 → 127 个三级节 → 145 个四级节 → 95 个五级节，每条带页码
- 编号标题清晰且字号分层明显（章标题 14pt、三级节 12pt、四级节加粗 vs 正文常规），可与书签交叉验证
- 三级节长度中位数约 2263 字符；73/127 落在 800–2500 字符区间（embedding 舒适区）；50 个节超过 2500 字符（最大 9.3 DataReader 约 27298 字符），几乎均有四/五级子节可下切
- 内容天然按语义单元组织：第 10 章约 30 个 QoS Policy 各成一节
- 数据质量点：固定页眉待剥离；表格会被线性化；150 张截图图片分布在 29 页（日志示例多为图）；印刷页码比物理页码小 6（印刷页 = 物理页 − 6，前 6 页封面/罗马数字前言不编号；2026-08-29 页眉真值核对定值，此前 +7/+6 记录均为方向错误）；原文有笔误（如 DomainParticipnt），可作检索测试素材

## 主方案：Structure-aware Chunking

```text
TOC 书签通道   get_toc() 提取书签 → 章节树骨架（含页码）
正文标题通道   编号正则 + 字号信号
       ↓
交叉验证 → 带页码区间的章节树 → 以三级节为知识单元
```

超大节沿四/五级子节递归下切，全程保护表格与代码块原子性。推荐原则不变：

> **能够独立回答一个典型开发者问题的语义单元，优先作为一个 Chunk。**

例如一个 QoS Policy、一组实体操作应尽量保持在同一语义单元中。

## 对照方案：纯语义 Chunk

`SemanticSplitterNodeParser` 基于 embedding 相似度寻找句子边界，开箱可用；但其 Node 缺少稳定章节身份，Citation 需事后映射回章节树——章节树是所有方案共用的地基。

## 合成方案：结构 + 语义混合

对超过阈值的结构节点做语义二次切分，调优参数清单见 6.2 节。

## 必要时引入 Parent-Child

手册的四/五级子节天然支持该模式：

```text
Parent:
  某个 API 操作小节

Children:
  Description
  Parameters
  Exceptions
  Example
```

检索 Child，回答时带 Parent 上下文。不是第一版的必需项。

---

# 16. 数据质量检查清单

每次重新构建知识库，都自动检查：

- [ ] Node 是否为空
- [ ] Node 是否过短
- [ ] Node 是否过长
- [ ] 是否存在重复 Node
- [ ] 页眉页脚比例是否异常（本手册每页固定页眉应已被完全剥离）
- [ ] 是否丢失代码块
- [ ] 代码块是否被二次切分切断
- [ ] 表格是否异常（表格线性化是否丢失列语义）
- [ ] 截图图片承载的内容缺失是否有记录（全书 150 张图分布 29 页）
- [ ] 印刷页码与 PDF 物理页码映射是否正确（本手册：物理页 − 印刷页 = 6，以页眉印刷数字为准）
- [ ] Metadata 是否完整
- [ ] source/page/section 是否可定位
- [ ] 版本信息是否正确

建议写一个：

```text
scripts/inspect_nodes.py
```

输出：

```text
Total documents: 1
Total pages: 295
Total nodes: 1240
Empty nodes: 3
Duplicated nodes: 12
Nodes without page: 0
Nodes > 1200 tokens: 21
```

---

# 17. 必须重点测试的典型错误

## Retrieval 错误

- [ ] 找不到正确章节
- [ ] 找到相似但错误 API
- [ ] 找到旧版本
- [ ] Error Code 检索失败
- [ ] 精确 API 名称检索失败

## Generation 错误

- [ ] 虚构 API
- [ ] 虚构参数
- [ ] 把多个来源内容错误拼接
- [ ] 把不同版本混在一起
- [ ] 来源与回答不匹配

## Parsing 错误

- [ ] PDF 页眉/页脚污染
- [ ] 表格顺序错误
- [ ] 代码行被打散
- [ ] 标题和正文分离
- [ ] HTML 导航/脚本混入正文

---

# 18. 最终四周里程碑

| 时间 | 目标 | 核心交付 |
|---|---|---|
| 第 1 周 | 单一 PDF Baseline | PDF → Node → Vector → RAG Demo |
| 第 2 周 | 调试和评测 | 问题集、Chunk 对比、Citation、基础可靠性 |
| 第 3 周 | 多来源统合 | HTML 接入、统一 Node/Metadata、跨来源检索 |
| 第 4 周 | 系统优化 | Hybrid、Reranker、Evaluation、回归、最终 Demo |

---

# 19. 详细周验收标准

## Week 1

**必须能回答：**

> “基于这一本手册，AI 能否回答基本产品问题？”

通过标准：

- PDF 成功解析
- Node 可人工检查
- Retrieval 可运行
- RAG 可运行
- 有最小 Web/API

## Week 2

**必须能回答：**

> “哪种 Chunking 和 Retrieval 更好？”

通过标准：

- 有问题集
- 有指标
- 有对比实验
- 能发现并修复典型错误

## Week 3

**必须能回答：**

> “PDF 手册和 HTML 开发指南能否作为一个知识体系回答问题？”

通过标准：

- 两种来源均可独立解析
- Metadata 统一
- 可同时检索
- Citation 能区分来源

## Week 4

**必须能回答：**

> “这个系统是否可靠到可以给开发者使用？”

通过标准：

- Hybrid Retrieval 可运行
- Reranker 有实验数据
- Unknown/Abstention 可工作
- 有 Citation
- 有自动/半自动 Evaluation
- 有最终 Demo

---

# 20. 项目最终建议的回答格式

最终前端建议让 AI 回复遵循类似结构：

```text
结论

简要说明解决方法。

示例

```java
...
```

注意事项

- ...
- ...

来源

[1] 《ZRDDS用户手册》, 第 42 页，3.4 节
[2] ZRDDS 开发指南, QoS 策略相关 API
```

如果没有足够证据：

```text
当前知识库没有找到足够资料确认该功能是否存在，因此无法可靠判断。
建议参考：...
```

---

# 21. 最终开发顺序：不要倒置

最重要的执行原则是：

```text
① 先解决 PDF Parsing
        ↓
② 再解决 Chunking
        ↓
③ 再做 Retrieval
        ↓
④ 再接 LLM
        ↓
⑤ 再建立问题集
        ↓
⑥ 再做 Evaluation
        ↓
⑦ 再接 HTML
        ↓
⑧ 再做 Hybrid/Reranker
        ↓
⑨ 最后做完整产品化
```

不要一开始就：

```text
Agent
GraphRAG
多智能体
复杂工作流
```

因为在当前项目阶段，最大的风险不是 LLM 不够强，而是：

```text
PDF 没解析好
      ↓
Chunk 不合理
      ↓
检索错误
      ↓
LLM 得到错误 Context
      ↓
答案看起来合理但实际上错误
```

因此整个项目的技术主线应该始终围绕：

> **“正确知识 → 正确检索 → 有依据的回答”**

---

# 22. 最终项目成果建议

如果项目最终需要进行汇报、答辩或提交报告，建议至少展示以下内容：

1. **产品文档结构分析**
2. **PDF 知识库构建流程**
3. **Chunking 策略与对比实验**
4. **RAG 系统架构**
5. **开发者问题分类**
6. **Retrieval 对比实验**
7. **多来源知识统合架构**
8. **Citation 与可信度控制**
9. **Unknown/Abstention 案例**
10. **最终 Evaluation 数据**

最有说服力的结果不是“用了 LlamaIndex”，而是展示：

```text
Baseline
   ↓
结构化 Chunk
   ↓
Hybrid Retrieval
   ↓
Reranker
   ↓
Citation + Abstention

Retrieval Hit Rate ↑
MRR ↑
Answer Relevance ↑
Faithfulness ↑
Hallucination ↓
```

这样能够完整证明从**知识工程 → 检索 → 生成 → 可靠性**的改进过程。

---

# 23. 参考资料

- LlamaIndex Node Parser Usage Pattern：<https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/loading/node_parsers/index.md>
- LlamaIndex SentenceSplitter API：<https://docs.llamaindex.ai/en/latest/api_reference/node_parsers/sentence_splitter/>
- LlamaIndex Evaluation：<https://llamaindex.openml.io/python/framework/understanding/evaluating/evaluating/>
- LlamaIndex VectorStoreIndex：<https://llamaindex.openml.io/python/framework/module_guides/indexing/vector_store_index/>
- LlamaIndex File Readers / PyMuPDFReader：<https://docs.llamaindex.org.cn/en/stable/api_reference/readers/file/>

> **版本说明**：LlamaIndex API 在不同版本之间有过模块路径和接口调整。正式开发时应固定 `llama-index` 及相关 integration package 的版本，并以该版本的官方文档与实际 IDE/API 提示为准。本文给出的代码用于说明架构和实施顺序，不应替代实际版本的 API 核对。

---

# 24. 一个月项目的最终 Checklist

## 产品与数据

- [x] 产品确定：ZRDDS（臻融数据分发服务）
- [x] 用户手册 PDF 确认：《ZRDDS用户手册.pdf》，295 页原生文本型
- [x] HTML 开发指南来源确认：`source/cdoc/html`（ZRDDS v2.4.0 Doxygen 在线文档，436 页，含 FAQ/示例/类索引）
- [ ] 版本信息确认

## 文档处理

- [ ] PDF Parsing
- [ ] HTML Parsing
- [ ] 清洗
- [ ] 结构识别
- [ ] Chunking
- [ ] Metadata

## Retrieval

- [ ] Embedding
- [ ] Vector Index
- [ ] Top-K Retrieval
- [ ] BM25
- [ ] Hybrid Retrieval
- [ ] Reranker

## RAG

- [ ] Prompt
- [ ] Context Builder
- [ ] LLM
- [ ] Citation
- [ ] Streaming

## 可靠性

- [ ] Grounding
- [ ] Abstention
- [ ] Version Conflict
- [ ] Source Priority
- [ ] Hallucination Cases

## Evaluation

- [ ] Developer Question Set
- [ ] Retrieval Metrics
- [ ] Answer Metrics
- [ ] Chunking Comparison
- [ ] Retrieval Comparison
- [ ] Regression Test

## 产品化

- [ ] Web UI
- [ ] API
- [ ] Logging
- [ ] Feedback
- [ ] Docker/部署
- [ ] README
- [ ] Final Report

---

## 最终执行原则

**第一周求“跑通”，第二周求“可测”，第三周求“可扩展”，第四周求“可靠和可展示”。**

不要把一个月耗在一开始的框架选型上。先用最简单的 LlamaIndex + 单一 PDF + Vector RAG 建立可信 Baseline，再通过真实开发者问题驱动 Chunking、Retrieval、Citation 和错误控制的迭代；这样既适合五人并行开发，也最容易在一个月内得到可量化的成果。
