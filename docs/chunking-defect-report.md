# RAG4ZRDDS 分块交付物缺陷报告（第一周 · 提交 A 修复）

> 诊断人：成员 D（集成与实验平台）· 日期：2026-08-27
> 修复责任人：成员 A（知识工程）——本报告只做根因定位与修复方向，D 不跨域改代码
> 证据来源：`make ingest` 全链路复跑、原始 PDF 地面真值（fitz 逐页解析）、`struct_v1.jsonl` 逐条核查；**文中数字全部实测**
> 前提：A 的分块交付已合入 `feature/server-platform`（4b2a368）

## 结论速览

| # | 缺陷 | 影响 | 严重度 |
|---|---|---|---|
| D1 | 整页抓取，页内章节边界不切分 | 76/105 个三级节 chunk（72%）头部串色，文本与标题不符 | 🔴 高 |
| D2 | 同页兄弟节点页码区间颠倒 | 22/127 个三级节整节缺失，内容被相邻节吞并 | 🔴 高 |
| D3 | 四/五级 `section_path` 未嵌套父级标题 | 超大节下切机制完全失效，最大单 chunk 28,180 字符 | 🟠 中高 |
| D4 | `quality_check.HEADER_RE` 未按行锚定 | 3 处正文合法产品名被误判"页眉残留" | 🟡 低 |
| D5 | `__main__` 自测在 Windows GBK 控制台崩溃 | 仅影响手工自测，不影响管线 | ⚪ 轻微 |

**D1 与 D2 同根**（页级粒度太粗，页内边界不可表达），建议一次修掉；D3 独立。

---

## D1 整页抓取导致内容串色（文本与标题对不上）

**症状**（用户抽查发现）：`struct_v1.jsonl` 第 2 行 `1.2 中间件` 的 chunk 以"服务器，分别为不同区域的web 浏览器提供内容"开头——这是 **1.1 分布式系统**的 web 服务器例子，不是 1.2 的内容。

**地面真值**（fitz 直接解析 `data/raw/manuals/ZRDDS用户手册.pdf`）：

| 物理页 | 印刷页 | 实际内容 |
|---|---|---|
| 7 | 2 | **顶部**是 1.1 的 web 架构例子（图1-1）；**中段**才是 `1.2 中间件` 标题与正文 |
| 8 | 3 | 同一页先后出现 `1.3 发布/订阅模型` 与 `1.4 DDS 介绍` 两个标题 |

**书签页码本身没有错**（1.2→页7、1.3→页8、1.4→页8 均与正文吻合），错在抽取粒度。

**根因**：`data_pipeline/chunkers/structure.py::_extract_text_by_pages` 按 `[physical_page_start, physical_page_end]` **整页**拼接文本；章节边界在页中间，页级区间无法表达，于是每个 chunk 头部混入上一节尾部、尾部混入下一节开头。

**实测影响**：105 个三级节 chunk 中 **76 个（72%）开头 200 字内找不到本节标题关键词**；整体覆盖率仅 93%（301,449 / 323,708 字符）。

**修复方向**：
- 用通道 2（`blocks`/`spans` 的 y 坐标 + 编号正则）定位每个节点标题在**页内的字符偏移**，按标题偏移切分文本，替代整页抓取。
- 建议偏移在**建树时**算好：`ingest.py` 步骤 5 时 `blocks` 还在内存，把每个节点的标题偏移作为新字段（如 `heading_char_offset` / `heading_physical_page`）写进 `section_tree_v1.jsonl`；chunker 继续消费扁平列表即可——**不要让 chunker 依赖 blocks**（ingest 传给 chunker 的 `pages_compact` 按契约不含 blocks）。
- 验收：全部三级节 chunk 开头含本节标题；抽样串色为 0。

---

## D2 同页兄弟节点页码区间颠倒（整节缺失 + 内容被吞）

**症状**：`1.3 发布/订阅模型` 等章节在 `struct_v1.jsonl` 中整节缺失；且 1.3 的内容并未消失，而是被 `1.4 DDS 介绍` 的 chunk 整页吞掉（1.4=[8,8] 抓走含 1.3 内容的整个页 8）。

**根因**：`data_pipeline/section_tree.py::finalize_page_ranges`（第 226 行）：

```python
n.physical_page_end = nxt.physical_page_start - 1   # nxt = 下一个 level≤本节点 的节点
```

当**两个兄弟节点起始于同一物理页**（1.3 与 1.4 都在页 8）：`1.3.end = 8 − 1 = 7 < start=8` → 区间颠倒 → chunker 里 `range(start, end+1)` 为空 → 零产出。

**实测影响**：22 个零产出三级节，**22/22（100%）全部是"同页兄弟"情形**：1.3、2.1、2.4、2.6、3.1、10.6、10.8、10.22、10.34、10.35、10.36、11.1、20.1、21.1、21.3、21.5、22.2、23.1、24.2、25.1、26.1、27.1。

**修复方向**：
- 同页兄弟节点应按**页内标题先后顺序**划界——D1 的"标题偏移"方案落地后此问题自然消除（推荐一并修）。
- 过渡性兜底：至少保证 `end >= start`（同页兄弟共享该页或按序切分），杜绝颠倒区间落盘。
- 验收：127 个三级节全部产出（除真空页）；不存在"某 chunk 正文含其他节标题"的情况。

---

## D3 四/五级 `section_path` 未嵌套父级标题（超大节下切失效）

**症状**：没有任何一个节被拆成多块（105 个 node 各恰好 1 chunk）；37/105 chunk 超过超大节阈值 2500 字符，4 个超 10000，最大 **28,180 字符 / 12,606 token**（9.3 DataReader 整节未切），远超 embedding 截断参考（1200 token 有 43 个超标）。

**根因**：**不是树缺子节**——树中四/五级节点共 240 个（145+95，与书签吻合）。问题在两处代码的接口错位：

- `section_tree.py::build_toc_tree`（第 123 行）拼路径为 `part / chapter / title`，**四级路径不含三级节标题**：

```
三级 4.1 路径:  PART 2 … / 第4章 数据类型 / 4.1 数据类型介绍
四级 4.1.1 路径: PART 2 … / 第4章 数据类型 / 4.1.1 sequence   ← 缺父级段
```

- `chunkers/structure.py::_is_descendant` 要求 `child.section_path.startswith(ancestor.section_path)` → 恒为 False → `_split_by_subsections` 恒返回空 → 超大节回退为整节单块。

（页码区间包含判断本身正确，实测 4.1.1 ⊂ 4.1 为 True；仅路径前缀一条卡死整个机制。）

**修复方向**（二选一，推荐①）：
1. `_split_by_subsections` 改用**树的父子关系**判定后代，不做字符串前缀匹配（扁平列表可由 `node_id` 前缀或落盘时附 `parent_id` 重建）。
2. `build_toc_tree` 的 `section_path` 改为逐级拼接祖先标题，使前缀关系成立。
- 验收：原 37 个超阈值三级节全部沿四/五级子节拆开；单 chunk 长度（除原子块外）不超过 `max_chunk_chars`。

---

## D4 质检页眉正则未按行锚定（误报）

**症状**：质检报告"页眉残留比例 2.9%"（3 个 chunk）。

**根因**：`data_pipeline/quality_check.py::HEADER_RE = re.compile(r"臻融数据分发服务DDS 系统软件")` 做子串搜索；正文中 3 处合法提及（如"臻融数据分发服务DDS 系统软件已经成功安装"）被计入残留。清洗本身没有问题（`pages.jsonl` 中整行页眉残留为 0）。

**修复方向**：改为逐行整行匹配（`^\s*臻融数据分发服务DDS 系统软件\s*$`，multiline），与 cleaner 的判定口径一致。

---

## D5 `__main__` 自测在 Windows GBK 控制台崩溃（轻微）

**症状**：`python -m data_pipeline.metadata` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`。

**根因**：自测输出含 emoji（✅），Windows 默认 GBK 控制台无法编码。`structure.py` 的 CLI 输出同理。

**修复方向**：去掉输出里的 emoji，或在 `__main__` 入口 `sys.stdout.reconfigure(encoding="utf-8")`（`scripts/ingest.py` 已用此法）。不影响管线运行。

---

## 修复红线：不得影响第二周三方案对比实验

1. **修复只能使用结构信号**（书签/编号正则/字号/坐标）。语义分块在本项目有明确定义——`SemanticSplitterNodeParser` 基于 embedding 相似度找边界（指南 §6.2 方案 B），修复中不得引入。
2. **"超阈值节语义二次切分"是方案 C（混合）的专属调优参数**（§6.2 调优清单挂在 C 名下）。方案 A 的超大节处理限于"沿四/五级子节递归下切"（§15），严禁为快速消掉超长 chunk 往方案 A 注入语义切分——否则 A 被污染成"半个 C"，三路线不再互斥，对比实验失效。
3. §6.2 公平性约束（同一清洗产物 / 同一 Embedding / 同一 LLM / 同一 Top-K / 同一测试集）与本次修复正交，不受影响。
4. **修复 A 是对比实验成立的前提**：当前 72% 串色 + 22 节缺失的"坏 A"与 B、C 对比不产生有效结论。

## 修复后验收流程（D 侧执行）

1. A 修复合并后，D 复跑 `make ingest`（六步管线，含 `validate_nodes_jsonl` 契约校验与 `quality_check` 质检）。
2. 验收指标：
   - 零缺失：127 个三级节全部产出（除真空页）；
   - 零串色：每个三级节 chunk 开头含本节标题（可自动检查）；
   - 超大节全部下切：除原子块外单 chunk ≤ `max_chunk_chars`；
   - 质检报告：空节点 0、重复 0、页眉残留 0、页码映射一致。
3. 通过后：`docs/ingest-pipeline.md` 已知边界表销项，AGENTS.md 同步；随后创建正式基线配置 `configs/experiments/struct_v1.yaml` 并进入 `build_index`。

## 关联待决项（非分块缺陷，修复时顺带确认）

- **双页码偏移**：`pdf_loader.py`/`section_tree.py` 的 `PAGE_OFFSET=7` 与指南 §16"相差 6"冲突；只影响 Citation 展示不影响分块文本，需三方会签定真值后全链路统一。**已决（2026-08-29）**：以 PDF 页眉印刷数字为地面真值逐页核对，真值 `印刷页 = 物理页 − 6`（前 6 页封面/罗马数字前言不编号）；2026-08-28 会签的 `+7` 为方向错误（致全部 Citation 印刷页 +12、物理页差 1），已全链路修复并加真值回归测试（`tests/unit/data_pipeline/test_page_numbering.py`）。
- **PART/章引言未参与分块**：chunker 只处理三级节，PART/章级引言文本未入库；D1/D2 修复后重新实测覆盖率缺口，再决定是否纳入。

---

## 修复记录（2026-08-27 · 已合入）

> 执行人：成员 D（经 A 授权代为修复）· 分支：`feature/server-platform`
> 原则：只用结构信号（书签/编号正则/标题文本定位），未引入任何语义切分，方案 A 与 B/C 的互斥性不受影响。

### 修复方案

| # | 方案 |
|---|---|
| D1 | `section_tree.py` 新增 `attach_heading_offsets`：归一化整标题匹配（编号前缀+剩余首段字符兜底）定位每个节点标题在**清洗后页文本**中的字符偏移，写入新字段 `heading_physical_page` / `heading_char_offset`（ingest 步骤 5 落盘前计算）。`structure.py` 的文本提取改为"起于自身标题偏移、止于下一边界节点标题偏移"，页内章节边界可表达 |
| D2 | `finalize_page_ranges` 末页改为 `max(start, 下一节点起始页)`：标题偏移口径下节点内容延伸到下一节标题所在页（页内截断），同时恒有 `end >= start`，同页兄弟不再颠倒/零产出 |
| D3 | `build_toc_tree` 四级及以下 `section_path` 沿父级路径逐级嵌套，`_is_descendant` 前缀判定恢复成立；`_split_by_subsections` 只迭代直接子节点（修复重复产出）、新增节首引导段、超长非原子段按段落/换行/句末结构兜底切分 |
| D4 | `HEADER_RE` 改为 `^\s*…\s*$`（multiline）逐行整行锚定；重复判定同步改为全文精确匹配（原前 200 字符字符集 Jaccard 对代码无区分度，误报原文笔误示例为重复） |
| D5 | `metadata.py` / `structure.py` / `section_tree.py` 的 `__main__` 入口 `sys.stdout.reconfigure(encoding="utf-8")` |

### 实测验收（`make ingest` 全链路，2026-08-27）

| 验收项 | 修复前 | 修复后 |
|---|---|---|
| 三级节产出 | 105/127（22 缺失） | **127/127** |
| 串色（首块不含本节标题） | 76/105 | **0/116**（1.2 中间件等抽查正确） |
| 超 `max_chunk_chars` 非原子块 | 37 个（最大 28,180） | **0**（最大 2,499） |
| 质检：空节点/重复/页眉残留/页码映射 | 0/0/2.9%/0 | **0/0/0.0%/0** |
| chunk 数 / 覆盖率 | 105 / 93%（含重复计数虚高） | 301 / 92%（无重叠；缺口=目录页+前言+PART/章引言，见关联待决项） |
| 标题偏移定位 | — | 405/405 全部命中 |

### 回归测试

`tests/unit/data_pipeline/test_chunking_defects.py`（8 用例，合成语料，不依赖 PDF）：
D1 同页零串色、D2 区间不倒置且同页兄弟双产出、D3 路径嵌套+超大节下切+引导段保留、
D4 正则行锚定（含质检端到端）、D5 GBK 控制台子进程实跑（`PYTHONIOENCODING=gbk`）。
`python -m pytest tests/` 14/14 通过。
