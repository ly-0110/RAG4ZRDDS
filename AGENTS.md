# RAG4ZRDDS 工作区记忆

> 本文件是本工作区的持久记忆。任何 Agent 会话开始前，先读本文件，再读《实施指南》对应章节。

## 项目定位

ZRDDS 产品知识库构建与开发调试问答系统：以《ZRDDS用户手册.pdf》为第一阶段唯一知识源，构建可运行、可调试、可评价的最小 RAG 问答系统；第二阶段接入 Doxygen HTML 文档形成多来源知识库；最终交付面向开发调试场景的问答、引用溯源、可信度控制与系统评测。

## 权威文档

- `product_rag_implementation_guide.md` —— 唯一权威计划：角色边界(§3)、仓库结构(§4)、四周任务分解(§5~8)、评测体系(§9)、验收标准(§19)。修改计划只改这里。
- `docs/` —— 各类报告落点（architecture / document-analysis / chunking-strategy / evaluation / api）。

## 关键实测事实（勿重复探测）

- 手册：295 页原生文本型 PDF；书签 405 条最深 5 级（11 PART → 27 章 → 127 三级节 → 145 四级 → 95 五级）；三级节长度中位数约 2263 字符，73/127 落在 800–2500 区间，50 个超 2500（最大 9.3 DataReader 约 27298）。
- 页码：印刷页码 = PDF 物理页码 + 6；Citation 必须双记录。
- 每页固定页眉“臻融数据分发服务DDS 系统软件”+页码，清洗时剥离。
- 表格会被线性化、150 张截图图分布在 29 页、原文有笔误（如 DomainParticipnt）——已列入质量检查清单(§16)。
- HTML 源：`data/raw/developer-guides/cdoc_html/` = ZRDDS v2.4.0 官方 Doxygen 文档（436 个 HTML），第三周接入。

## 既定决策（变更须更新本文件）

- Chunking 三方案对比：A 结构感知(主) / B 纯语义(对照, SemanticSplitterNodeParser) / C 结构+语义混合(预期主推)；固定尺寸分块不是研究主线（仅可选 sanity baseline）。详见 §6.2/§15。
- 角色 Owner：A 知识工程 / B 检索 / C 生成与可靠性 / D 集成与实验平台 / E 前端与质量。边界表见指南 §3，禁止跨域改代码。
- 前端三路线：自研轻量页 / 开源 Chat UI 改造 / MCP 封装；Citation（页码+章节）展示是硬性交付。
- 一切检索/分块实验经 `configs/experiments/*.yaml` 驱动 `scripts/run_experiment.py`，报告落 `evaluation/reports/`；禁止凭感觉合并变更（§10）。

## 工作约定

- 不入 Git：`data/raw/`、`data/cleaned/`、`indexes/`；必须入库：`configs/`、`data/processed/`、`evaluation/reports/`。
- Node metadata 双页码（印刷+物理）；表格/代码块分块原子性；交接只通过仓库产物文件。
- 环境：Python + LlamaIndex；向量库本地原型 Chroma/FAISS 二选一。

## 当前状态

- [x] 计划 v2 定稿（统一周模板、职责章程、仓库结构 v2）
- [x] 仓库目录骨架创建完成，source/ 已迁移至 data/raw/
- [x] Git 初始化与配套文件（.gitignore/.env.example/requirements.txt/Makefile/CODEOWNERS）
- [ ] 第一周任务（指南 §5）：清洗 → 章节树 → struct_v1 分块 → 向量索引 → 最小 RAG → Demo
