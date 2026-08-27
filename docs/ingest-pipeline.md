# RAG4ZRDDS Ingest 编排管线（v1 · 骨架阶段）

> 维护人：成员 D。调用 A 交付物（data_pipeline/）完成 raw → cleaned → processed 的自动化编排。
> 当前 stage：章节树已就绪，分块步骤待 A 交付 chunkers/ 后自动启用。

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
         │  [D] 契约校验
         ▼
  pages_compact  │  pages_full（内存，含 blocks）
         │                  │
 步骤 4  │         步骤 5  │  [A] section_tree 双通道构建
         │                  ▼
         │         data/processed/section_tree_v1.jsonl
         │
 步骤 6  │  [预留] A 交付 chunkers/ 后自动分块
         │         data/processed/{method}_{version}.jsonl
```

## 用法

```bash
make ingest                              # 默认 configs/experiments/example_v1.yaml
python scripts/ingest.py                 # 同上
python scripts/ingest.py -c configs/experiments/example_v1.yaml  # 显式指定配置
python scripts/ingest.py --skip-section-tree   # 仅产出 pages.jsonl
```

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--config` / `-c` | `configs/experiments/example_v1.yaml` | 实验配置路径，`load()` 校验通过后作为全管线参数来源 |
| `--skip-section-tree` | 无 | 跳过章节树构建（调试清洗步骤时使用） |

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 配置加载失败 / A 交付物缺失 / 契约校验不通过 / 步骤异常 |

## 五个步骤（逐步说明）

### 步骤 0：配置加载

```python
from scripts.experiment_config import load
cfg = load(config_path)
```

- 失败时打印友好错误（未知字段 → 拼写建议；YAML 语法 → 定位行号）
- 校验 `sources` 中至少有一个 `type=pdf` 的条目，且文件存在
- 派生产物路径：pages.jsonl、section_tree_v1.jsonl、预留的 node 集路径

### 步骤 1：PDF 逐页提取

**调用**：`data_pipeline.pdf_loader.extract_pdf(pdf_src)`

| 产物 | 说明 |
|---|---|
| `PageRecord.physical_page` | PDF 物理页码，0-based |
| `PageRecord.printed_page` | 印刷页码，`physical_page + 7`（当前约定值；PAGE_OFFSET 在 A 的模块中定义） |
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

### 步骤 3：落盘 pages.jsonl + 契约校验

写入 `cfg.ingest.cleaned_output`（默认 `data/cleaned/pages.jsonl`）

与 A 的 `save_pages_jsonl` 区别：

| 方面 | A 的 `save_pages_jsonl` | `ingest.py` |
|---|---|---|
| blocks | 去掉（减小体积） | 去掉（避免 bytes 序列化报错） |
| 写入时机 | 提取后立即写入 | 清洗后写入 |
| 附带校验 | 无 | 写入后立即执行契约校验 |

**契约校验项**（`validate_pages_jsonl`）：

| 检查 | 误差容忍 |
|---|---|
| `physical_page` 为非负整数 | ❌ 不允许 |
| `printed_page` 为正整数 | ❌ 不允许 |
| `text` 为字符串 | ❌ 不允许 |
| `toc_entries` 为列表 | ❌ 不允许 |
| `physical_page` 从 0 开始连续 | 缺失 > 1 时报错（扉页/目录缺失常见，只警告不阻断） |
| `printed_page - physical_page` 差值全局一致 | ❌ 变化则报错，用于发现 PAGE_OFFSET 配置错误 |

### 步骤 4：双通道章节树

**调用 A 全套**：`build_toc_tree` → `extract_text_titles` → `match_toc_with_text` → `finalize_page_ranges` → `dump_section_tree`

**通道 1（TOC 书签骨架）**：逐页收集 `toc_entries`，按 level 还原父子关系，构建 `SectionNode` 树。
**通道 2（正文标题候选）**：遍历 `blocks` 中的 spans，按字号阈值、加粗、编号正则提取可能为标题的行。
**交叉验证**：在同一页 ±1 范围内，当 TOC 节点与正文候选层级相同、文本 Jaccard 相似度 ≥ 0.8 时，将对应节点标记为 `verified_by_text = True`。

的关键：`ingest.py` 将**内存中的完整 `pages_full`（含 blocks）** 传给章节树函数，因此通道 2 有数据可用；而 A 的 `section_tree.py::main()` 独立运行时读的是磁盘 pages.jsonl（无 blocks），通道 2 永远为空，故所有节点 `verified_by_text = False`。

### 步骤 5：[预留] 分块构建

```python
if (chunker_dir / "structure.py").exists():
    from data_pipeline.chunkers.structure import chunk
    chunk(pages=pages_full, tree=toc_tree, output=nodes_out)
```

当前状态：等待 A 交付 `data_pipeline/chunkers/` 后自动激活，不需额外配置。

## 产出文件

### `data/cleaned/pages.jsonl`

每条 JSON 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `physical_page` | int | 0-based PDF 物理页码 |
| `printed_page` | int | 1-based 印刷页码（= physical_page + 7） |
| `text` | string | 清洗后的页面正文（已去页眉、页码行） |
| `toc_entries` | list[dict] | 本页相关书签：`{level, title, physical_page}` |

略去的字段（避免序列化 bytes 报错；章节树步骤 4 使用的是内存完整版）：
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

## 已知边界

| 边界 | 影响 | 状态 |
|---|---|---|
| `finalize_page_ranges` 中的 `PAGE_OFFSET=7` 硬编码 | `printed_page` 比印刷页码大 1（实测差 6） | 已确认待 A 统一修正 |
| `extract_text_titles` 仅从已命名的 blocks 里提取 | PDF 中图片截断的文本行不会进入候选 | 属预期行为 |
| chunkers/ 未交付时静默跳过 | 周五验收前分块步骤不可用 | 持续阻塞 |
| pages.jsonl 不含 blocks | 后续消费若需 blocks 需重走 extract_pdf | 按需实现 |

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 第一周 | 骨架定稿：配置加载 → PDF 提取 → 清洗 → pages.jsonl + 契约校验 → 章节树 → 分块预留点 |

## 依赖模块清单

| 模块 | Owner | 状态 | 备注 |
|---|---|---|---|
| `scripts/experiment_config.py` | D | ✅ | 配置加载与校验 |
| `data_pipeline/pdf_loader.py` | A | ✅ | PDF 逐页提取 |
| `data_pipeline/cleaner.py` | A | ✅ | 页眉/页码行清洗 |
| `data_pipeline/section_tree.py` | A | ✅ | 双通道章节树 |
| `data_pipeline/chunkers/` | A | ❌ | 待交付 |
| `data_pipeline/metadata.py` | A | ❌ | 待交付 |
| `data_pipeline/quality_check.py` | A | ❌ | 待交付 |