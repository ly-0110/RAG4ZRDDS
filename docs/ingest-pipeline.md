# RAG4ZRDDS Ingest 编排管线（多来源注册式）

> 调用 `data_pipeline/` 的解析与分块模块，完成 raw → cleaned → processed 的自动化编排。
> 按配置 `sources[]` 注册表逐来源分派 loader，合并为统一 Node 集；
> 单来源配置行为保持向后兼容（四个单来源配置的 hash8 由回归测试钉死）。

## 概览

`scripts/ingest.py` 是 **raw → cleaned → processed** 三阶段编排的唯一入口。
由 `make ingest` 触发，读实验配置 → 调各处理模块 → 逐一校验产物 → 落盘。

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
| `PageRecord.physical_page` | PDF 物理页码，**1 基**（与阅读器页码一致） |
| `PageRecord.printed_page` | 印刷页码：优先解析页眉印刷数字（地面真值），解析不到按 `physical_page + PAGE_OFFSET` 兜底（`PAGE_OFFSET = −6`；前 6 页封面/罗马数字前言为 `None`） |
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
- 实测：295 页总字符 323,708，非空页 294/295；无整行页眉残留（正文中的产品名提及属合法内容）

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

**调用（真实接口）**：

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
| 质检 | `cfg.ingest.quality_check=true` 时运行 `data_pipeline.quality_check.check_nodes`，打印报告；质检异常仅告警 |
| 失败即停 | 分块器异常、产出 0 chunk、契约校验不通过 → 退出码 1 |

**实测基线（`struct_v1` 配置，120 题正式问题集所用产物）**：301 chunk，长度 min 24 / p50 777 / avg 990 / max 2,499；无空 Node、无重复、无代码块/表格切断，页码映射校验 0 错（印刷页 = 物理页 − 6）。对照方案：`semantic_v1` 622 块、`hybrid_v1` 906 块。

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

`metadata` 必填字段：`source_id`（对齐实验配置 `sources[].id`） `source_file` `source_type` `part` `chapter` `section_path` `section_level` `printed_page_start/end` `physical_page_start/end` `node_ids[]` `chunk_id` `version` `product`；
可选字段（HTML 来源回填，PDF 阶段为 None）：`language` `platform` `content_type` `api_name` `error_code` `source_url`（PDF 阶段均为 None）。

## 多来源注册式接入

**目标**：新来源放入 raw + 在配置注册即可重建索引；PDF 与 HTML 独立解析、统一 Node、统一检索（§7.4）。

### 来源注册（configs/experiments/*.yaml 的 sources）

每个来源声明 `id / type(pdf|html) / path / version / url`（html 必填 url，§7.2 引用可跳转）。
合并校验强制跨域一致性：

- `metadata.source_id` 必须等于注册 `id`（抓 loader 错挂来源）
- 注册声明了 `version` 时 `metadata.version` 必须一致（抓 2.0/2.4 错配）
- 双页码差值按 `source_id` **分组**校验——多 PDF 来源可各有偏移；HTML 无页码自然跳过
- `chunk_id` 全局唯一（跨来源重复在建库前暴露，避免不同来源的 ID 前缀撞车）

### 分派与产物命名

| | 单来源配置（现状，兼容冻结） | 多来源配置 |
|---|---|---|
| PDF 链路 | 六步全链路（既有产物名 pages.jsonl / section_tree_v1.jsonl） | 同链路，产物按来源拆分 `pages_{sid}.jsonl` / `section_tree_{sid}.jsonl` |
| HTML 链路 | —（不注册 html 即可） | 经 `html_loader.build_html_chunks`（见下接线） |
| Node 集 | `{method}_{version}.jsonl`（既有命名不变） | `{method}_{version}__{src8}.jsonl`（src8=来源集指纹，见 `experiment_config.sources_digest8`） |
| 索引身份 | hash8 不含 sources（**既有 4 个真实索引不受影响**，R5 回归钉死） | 来源集参与 `index_identity_json`——来源集变了索引名必变，与 R2 产物指纹双保险 |

**落盘顺序**：先合并校验、后写盘——坏合并不得覆盖既有好产物（Node 集同名覆盖即索引指纹翻转）。

### html_loader 接线

```python
# data_pipeline/html_loader.py 实际接口（docs/html-loader.md §5；Chunk.to_dict 同款顶层结构）
build_html_chunks(doc_dir, *, base_url="", source_id="zrdds_dev_guide", version="2.4",
                  max_chunk_chars=2500, min_chunk_chars=20,
                  include_source_listings=False, drop_index_pages=False, limit=None)
      -> (List[Chunk], stats)
```

metadata 经 `data_pipeline.metadata.build_chunk_metadata` 构建
（`source_type="html"`：双页码 None、`source_url`/`title` 必填、version=2.4）。
`_process_html_source` 从配置透传 `max_chunk_chars`/`min_chunk_chars`（params 袋缺省 2500/20）。

**接线实测**：多来源配置 `struct_multisrc_v1.yaml` 端到端通过——
PDF 301 + HTML 1337 = **1638 条统一 Node 集**（`struct_v1__b95d1061.jsonl`），跨来源契约校验全过；
独立入库的 `html_v1.jsonl` 与接线实时产出**逐字节一致**（可复现性验证）；
`inspect_nodes` 分来源统计：html 缺 source_url 0 / pdf 缺双页码 0 / 重复 ID 0。

## 依赖模块清单

| 模块 | 状态 | 备注 |
|---|---|---|
| `scripts/experiment_config.py` | ✅ | 配置加载与校验 |
| `data_pipeline/pdf_loader.py` | ✅ | PDF 逐页提取与页眉页码真值解析 |
| `data_pipeline/cleaner.py` | ✅ | 页眉/页码行清洗 |
| `data_pipeline/section_tree.py` | ✅ | 双通道章节树（书签 × 正文标题） |
| `data_pipeline/chunkers/` | ✅ | structure / semantic / hybrid 三策略 |
| `data_pipeline/metadata.py` | ✅ | 15 必填 + 7 可选 Schema 单一事实源（含 `source_id`） |
| `data_pipeline/quality_check.py` | ✅ | 数据质量清单自动化（页眉正则/精确判重/页码真值校验） |
| `data_pipeline/html_loader.py` | ✅ | HTML 来源 loader（Doxygen 436 页 → 288 正文页，接口 `build_html_chunks`，契约 `docs/html-loader.md`） |
