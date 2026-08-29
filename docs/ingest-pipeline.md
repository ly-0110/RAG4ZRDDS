# RAG4ZRDDS Ingest 编排管线（v1.1 · 全链路打通）

> 维护人：成员 D。调用 A 交付物（data_pipeline/）完成 raw → cleaned → processed 的自动化编排。
> 当前 stage：全链路打通——分块步骤已接入 A 的 StructureChunker（2026-08-27 测试验证后启用）。

## 概览

`scripts/ingest.py` 是 **raw → cleaned → processed** 三阶段编排的唯一入口。
由 `make ingest` 触发，读实验配置 → 调各 Owner 模块 → 逐一校验产物 → 落盘。

```
  data/raw/manuals/ZRDDS用户手册.pdf
         │
 步骤 1  │  [A] pdf_loader.extract_pdf
         ▼
 清洗前 PageRecord（内存，含 blocks）
         │
 步骤 2  │  [A] cleaner.clean_page_text
         ▼
 清洗后 PageRecord（内存）
         │
 步骤 3  │  [D] 落盘 → data/cleaned/pages.jsonl（去 blocks）
         │
 步骤 4  │  [D] pages.jsonl 契约校验
         ▼
  pages_compact  │  pages_full（内存，含 blocks）
         │                  │
 步骤 5  │         [A] section_tree 双通道构建
         │                  ▼
         │         data/processed/section_tree_v1.jsonl
         │
 步骤 6  │  [A] get_chunker(strategy, params).chunk(pages, tree)
         │  [D] Chunk.to_dict() 落盘 + Node 集契约校验
         │  [D] 质检报告（配置 ingest.quality_check 开关）
         ▼
  data/processed/{method}_{version}.jsonl
```

## 用法

```bash
make ingest                              # 默认 configs/experiments/example_v1.yaml
python scripts/ingest.py                 # 同上
python scripts/ingest.py -c configs/experiments/<实验>.yaml  # 显式指定配置
python scripts/ingest.py --skip-section-tree   # 跳过重建章节树（用磁盘上已有的树继续分块）
```

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--config` / `-c` | `configs/experiments/example_v1.yaml` | 实验配置路径，`load()` 校验通过后作为全管线参数来源 |
| `--skip-section-tree` | 无 | 跳过章节树重建，分块步骤改读磁盘上已有的 `section_tree_v1.jsonl`（调试清洗/分块步骤时使用；树文件不存在会在步骤 6 报错） |

配置开关：`ingest.quality_check`（默认 true）——步骤 6 落盘后运行 A 的 `quality_check.check_nodes` 质检报告；质检异常只告警、不影响产物落盘。

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 配置加载失败 / A 交付物缺失或无法导入 / 契约校验不通过 / 分块器运行失败 / 产出 0 chunk |

## 六个步骤（逐步说明）

### 步骤 0：配置加载

```python
from scripts.experiment_config import load
cfg = load(config_path)
```

- 失败时打印友好错误（未知字段 → 拼写建议；YAML 语法 → 定位行号）
- 校验 `sources` 中至少有一个 `type=pdf` 的条目，且文件存在
- 派生产物路径：`cleaned_output`、section_tree_v1.jsonl、Node 集 = `data/processed/{chunking.method}_{chunking.version}.jsonl`（`nodes_path(cfg)`）

### 步骤 1：PDF 逐页提取

**调用**：`data_pipeline.pdf_loader.extract_pdf(pdf_src)`

| 产物 | 说明 |
|---|---|
| `PageRecord.physical_page` | PDF 物理页码，**1 基**（与阅读器页码一致；2026-08-29 前曾为 0 基，已修正） |
| `PageRecord.printed_page` | 印刷页码：优先解析页眉印刷数字（地面真值），解析不到按 `physical_page + PAGE_OFFSET` 兜底（`PAGE_OFFSET = −6`，2026-08-29 页眉逐页核对定值；前 6 页封面/罗马数字前言为 `None`）。旧 `+7` 为方向错误，已作废 |
| `PageRecord.text` | 页全文（含页眉页码，步骤 2 清洗） |
| `PageRecord.blocks` | PyMuPDF `get_text("dict")` 原始块结构：bbox、字体、字号、加粗——章节树正文标题候选所需 |
| `PageRecord.toc_entries` | 本页涉及的书签条目（`[{level, title, physical_page}]`） |

失败场景：PDF 不存在、PyMuPDF 不支持的文件格式。

### 步骤 2：页眉/页码行清洗

**调用**：`data_pipeline.cleaner.clean_page_text(page.text)`

- 逐行扫描，去除固定页眉"臻融数据分发服务DDS 系统软件"
- 正则匹配页码行：纯数字、`第 X 页`、`X/Y` 等
- 压缩连续空行至最多 1 个，首尾去空行
- 不修改双页码、toc_entries、blocks
- 实测（2026-08-27）：295 页总字符 323,708，非空页 294/295；无整行页眉残留（正文中的产品名提及属合法内容）

### 步骤 3：落盘 pages.jsonl

写入 `cfg.ingest.cleaned_output`（默认 `data/cleaned/pages.jsonl`）

与 A 的 `save_pages_jsonl` 区别：

| 方面 | A 的 `save_pages_jsonl` | `ingest.py` |
|---|---|---|
| blocks | 去掉（减小体积） | 去掉（避免 bytes 序列化报错） |
| 写入时机 | 提取后立即写入 | 清洗后写入 |
| 附带校验 | 无 | 写入后立即执行契约校验（步骤 4） |

### 步骤 4：契约校验（`validate_pages_jsonl`）

| 检查 | 误差容忍 |
|---|---|
| `physical_page` 为非负整数 | ❌ 不允许 |
| `printed_page` 为正整数 | ❌ 不允许 |
| `text` 为字符串 | ❌ 不允许 |
| `toc_entries` 为列表 | ❌ 不允许 |
| `physical_page` 连续 | 缺失即报错（列出前 10 个缺失页） |
| `printed_page - physical_page` 差值全局一致 | ❌ 变化则报错，用于发现 PAGE_OFFSET 配置错误 |

### 步骤 5：双通道章节树

**调用 A 全套**：`build_toc_tree` → `extract_text_titles` → `match_toc_with_text` → `finalize_page_ranges` → `dump_section_tree`

**通道 1（TOC 书签骨架）**：逐页收集 `toc_entries`，按 level 还原父子关系，构建 `SectionNode` 树。
**通道 2（正文标题候选）**：遍历 `blocks` 中的 spans，按字号阈值、加粗、编号正则提取可能为标题的行。
**交叉验证**：在同一页 ±1 范围内，当 TOC 节点与正文候选层级相同、文本 Jaccard 相似度 ≥ 0.8 时，将对应节点标记为 `verified_by_text = True`。

关键：`ingest.py` 将**内存中的完整 `pages_full`（含 blocks）** 传给章节树函数，因此通道 2 有数据可用；而 A 的 `section_tree.py::main()` 独立运行时读的是磁盘 pages.jsonl（无 blocks），通道 2 永远为空，故所有节点 `verified_by_text = False`。

### 步骤 6：分块构建 + Node 集校验 + 质检

**调用（A 交付的真实接口，2026-08-27 会签实测）**：

```python
from data_pipeline.chunkers.base import get_chunker
chunker = get_chunker(strategy, cfg.chunking.params)   # strategy: structure|semantic|hybrid
chunks = chunker.chunk(pages_compact, tree_records)    # 均为扁平 List[dict]
node_records = [c.to_dict() for c in chunks]           # 落盘由编排层负责
```

| 环节 | 说明 |
|---|---|
| method → strategy 映射 | 配置 `chunking.method=struct` → chunker `strategy=structure`（semantic/hybrid 同名）；`fixed` 等无实现的 method 直接报错 |
| 输入 | `pages_compact`（内存）+ 磁盘 `section_tree_v1.jsonl` 扁平列表 |
| 输出 | `nodes_path(cfg)` = `data/processed/{method}_{version}.jsonl`，逐行 `Chunk.to_dict()` |
| 契约校验 | `validate_nodes_jsonl`：6 个顶层字段齐全、chunk_id 唯一、text 非空、metadata 必填字段完整（以 `data_pipeline/metadata.py` 白名单为准）、双页码差值全局一致 |
| 质检 | `cfg.ingest.quality_check=true` 时运行 `data_pipeline.quality_check.check_nodes`（指南 §16 清单），打印报告；质检异常仅告警 |
| 失败即停 | 分块器异常、产出 0 chunk、契约校验不通过 → 退出码 1 |

**实测基线（2026-08-27，example_v1 配置）**：105 chunk，长度 min 409 / p50 1,411 / avg 2,870 / p95 8,809 / max 28,180；无空 Node、无重复、无代码块/表格切断、页码映射全一致（差值 7）。

## 产出文件

### `data/cleaned/pages.jsonl`

每条 JSON 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `physical_page` | int | 0-based PDF 物理页码 |
| `printed_page` | int | 1-based 印刷页码（= physical_page + PAGE_OFFSET） |
| `text` | string | 清洗后的页面正文（已去页眉、页码行） |
| `toc_entries` | list[dict] | 本页相关书签：`{level, title, physical_page}` |

略去的字段（避免序列化 bytes 报错；章节树步骤 5 使用的是内存完整版）：
- `blocks` — PyMuPDF 块结构，含图像字节

### `data/processed/section_tree_v1.jsonl`

每条 JSON 字段（由 A 的 `dump_section_tree` 定义）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `node_id` | str | 全局唯一 ID，如 `s_PART1_背景介绍` |
| `level` | int | 1=PART, 2=章, 3=三级节, 4=四级, 5=五级 |
| `title` | str | 章节标题 |
| `part` | str | 所属分部名称 |
| `chapter` | str | 所属章名称 |
| `section_path` | str | 完整面包屑，如 `PART 2 基本概念 / 第4章 数据类型 / 4.1 数据类型介绍` |
| `physical_page_start` | int | 本节点起始物理页 |
| `physical_page_end` | int | 本节点结束物理页 |
| `printed_page_start` | int | 起始印刷页 |
| `printed_page_end` | int | 结束印刷页 |
| `toc_source` | bool | 是否来自 PDF 书签 |
| `verified_by_text` | bool | 是否被正文排版信号交叉验证通过 |

### `data/processed/{method}_{version}.jsonl`（Node 集）

顶层字段（`data_pipeline/chunkers/base.py::Chunk`，单一事实源）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `chunk_id` | str | 全局唯一，如 `struct_v1_{node_id}_{seq:05d}` |
| `text` | str | 正文（代码块/表格/图片原子保护，不被切断） |
| `metadata` | dict | 21 字段 Schema，见 `data_pipeline/metadata.py`（15 必填 + 6 可选） |
| `token_count` | int | cl100k_base token 数，供 Embedding 截断判断 |
| `char_start` / `char_end` | int | 在本节拼接文本中的字符偏移（溯源高亮用） |

`metadata` 必填字段：`source_id`（对齐实验配置 `sources[].id`，2026-08-28 新增） `source_file` `source_type` `part` `chapter` `section_path` `section_level` `printed_page_start/end` `physical_page_start/end` `node_ids[]` `chunk_id` `version` `product`；
可选字段（第三周 HTML 回填）：`language` `platform` `content_type` `api_name` `error_code` `source_url`（PDF 阶段均为 None）。

## 已知边界

> 分块交付物的缺陷根因、实测证据与修复方向统一见 **`docs/chunking-defect-report.md`**（D1~D5，2026-08-27 诊断，修复责任人 A）。下表仅登记对管线的影响与状态。

| 边界 | 影响 | 状态 |
|---|---|---|
| `finalize_page_ranges` 中的 `PAGE_OFFSET` 硬编码 | 曾与指南旧约定 +6 冲突 | **已销项**（2026-08-29 页眉真值核对：`printed = physical − 6`，常量统一走 `pdf_loader.PAGE_OFFSET`；**旧 +7 为方向错误**——2026-08-28 会签值使全部 Citation 页码偏移 +12/物理页差 1，用户前端验收时发现，已修复并新增：页眉解析地面真值、1 基物理页、ingest 偏离公式告警、`tests/unit/data_pipeline/test_page_numbering.py` 真值回归） |
| **D1 整页抓取、页内章节边界不切分**：76/105 三级节 chunk（72%）头部串色，文本与标题不符 | 检索命中率与 Citation 可信度的根本风险 | **已修复**（6c0e6e3 标题页内偏移切分；实测 127/127 零串色，回归测试锁定） |
| **D2 同页兄弟节点区间颠倒**：22/127 三级节零产出（1.3、2.1、10.6 等），内容被相邻节吞并 | 覆盖率仅 93%（301,449 / 323,708 字符）；缺节且归属错 | **已修复**（6c0e6e3 与 D1 同根；实测 127/127 零缺失，覆盖率 92%→缺口为目录/引言类文本，见下行） |
| **D3 四/五级 `section_path` 未嵌套父级标题**：`_is_descendant` 恒 False，超大节下切完全失效（37/105 超 2500 字符，最大 28,180 字符/12,606 token） | 超 embedding 截断上限，检索质量风险 | **已修复**（6c0e6e3 路径嵌套+子节点迭代+超长段兜底；实测非原子块全 ≤2500） |
| PART 引言、章引言等非三级节文本不参与分块 | 覆盖率缺口的另一来源 | 重测后仍成立：缺口=目录页+前言+PART/章引言，是否纳入待会签 |
| **D4 `quality_check.HEADER_RE` 未按行锚定** | 3 处正文合法产品名提及被误判"页眉残留 2.9%" | **已修复**（6c0e6e3 行锚定+精确判重；实测页眉残留 0） |
| **D5 `metadata.py`/`structure.py` 的 `__main__` 自测含 emoji** | Windows GBK 控制台 UnicodeEncodeError；不影响管线 | **已修复**（6c0e6e3 `__main__` stdout reconfigure UTF-8） |
| 提交说明"1,342 个 chunk"与实测 105 条不符 | 产物本身完整可复现（重新生成与提交版逐字节一致），仅说明文字有误 | 已与产物核对，待 A 更正说明 |
| `extract_text_titles` 仅从已命名的 blocks 里提取 | PDF 中图片截断的文本行不会进入候选 | 属预期行为 |
| pages.jsonl 不含 blocks | 后续消费若需 blocks 需重走 extract_pdf | 按需实现 |
| chunkers 依赖 `tiktoken`，首次运行需联网下载 cl100k_base 词表 | 干净环境 `make setup` 后首次 `make ingest` 略慢 | 已列入 requirements |

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 第一周 | 骨架定稿：配置加载 → PDF 提取 → 清洗 → pages.jsonl + 契约校验 → 章节树 → 分块预留点 |
| v1.1 | 2026-08-27 | 分块步骤接入 A 的 StructureChunker（`get_chunker` 工厂）；新增 `validate_nodes_jsonl` Node 集契约校验与 `quality_check` 质检挂接；A 交付物经实测登记上表 9 条边界 |

## 依赖模块清单

| 模块 | Owner | 状态 | 备注 |
|---|---|---|---|
| `scripts/experiment_config.py` | D | ✅ | 配置加载与校验 |
| `data_pipeline/pdf_loader.py` | A | ✅ | PDF 逐页提取 |
| `data_pipeline/cleaner.py` | A | ✅ | 页眉/页码行清洗 |
| `data_pipeline/section_tree.py` | A | ✅ | 双通道章节树（页码区间颠倒问题待修） |
| `data_pipeline/chunkers/` | A | ✅ | base + structure 已交付并接入；semantic/hybrid 第二周 |
| `data_pipeline/metadata.py` | A | ✅ | 20 字段 Schema 单一事实源 |
| `data_pipeline/quality_check.py` | A | ✅ | §16 清单自动化；页眉正则待修正 |
