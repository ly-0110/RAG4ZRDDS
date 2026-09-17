# HTML 开发指南接入

> 交付物：`data_pipeline/html_loader.py` · `data/processed/html_v1.jsonl` · 质检报告 `logs/html_loader_report.json`
> 本稿只记录**实测结论**，数字取自全量跑产物（288 正文页 / 1337 chunk）。

---

## 1. 结论先行

| 项 | 结果 |
|---|---|
| 源目录 | `data/raw/developer-guides/cdoc_html/`（自 `G:\zrdds\ZRDDS-2.5.0\doc\cdoc\html` 迁入，832 文件逐字节校验一致） |
| 参与解析的正文页 | **288**（递归 527 个 html − 88 个 search 空壳 − 3 个 static − 147 个源码清单 = 289 个候选，再跳过 1 个无 `div.contents` 的独立工具页） |
| 产物 | `data/processed/html_v1.jsonl` —— **1337 chunk**，Metadata 100% 合规（282 个文档产出至少 1 个 chunk，其余 6 个为 `dir_*` 参考页与 `functions_vars_x/y` 索引存根） |
| Schema | `data_pipeline/metadata.py`，字段集与 `ALL_FIELDS` 完全一致 |
| 下游 | `scripts/ingest.validate_nodes_jsonl` 通过；`retrieval.nodes.load_nodes` 载入 1337 条、零空 ID；SourceRef 投影正常（页码为 `None`） |

---

## 2. 噪声过滤规则（每条都有全量实测依据）

| 层级 | 规则 | 实测规模 |
|---|---|---|
| 目录级 | 排除 `search/`、`static/` | 88 + 3 个 html，正文只有“载入中/搜索中”JS 空壳 |
| 文件名级 | 排除 `*_source.html`（`--include-source-listings` 可回退收录） | **147 个** C/C++ 头文件源码清单，3.5MB |
| 元素级 | 剥离 `script`/`style`/`noscript`、`div.navpath`、`div.tabs*`、`div.levels`、`div.header`/`div.footer`、`a.anchor`、`span.lineno` | 288/289 页含 `<script>`；`div.levels` 即 modules.html 的「详情级别」控件 |

实测口径：**裸 `**/*.html` 递归会抓到 527 个 → 正文只有 288 个**（527 − 88 − 3 − 147 − 1）。质检断言 `噪声残留 = 0`（检查 `详情级别`/`navpath`/`生成于`/`版权所有` 等标记）。

---

## 3. HTML 的「页等价物」

| PDF 侧 | HTML 侧 |
|---|---|
| `source_file` = PDF 文件名 | `source_file` = HTML 文件名 |
| 双页码四字段 = int 真值 | **一律 `None`**（metadata 的 html 分支允许） |
| 页码用于引用定位 | `source_url` 必填（html 分支强制），引用可跳转 |

`source_url = {base_url}/{文件名}`；`base_url` 由实验配置 `sources[].url` 提供（schema 对 `type: html` 强制要求该字段）。留空时退化为文件名定位符，保证契约非空。

---

## 4. 节点粒度与 `section_path`

标题驱动（h1~h5 与 `h2.groupheader` 构成层级），标题之间的正文归其最近的标题；**每个 `div.memitem` 独立成节点**，支撑 §7.5 B 组题。节点正文以本节标题开头（与 PDF 侧 struct 同口径——PDF 从标题偏移起切，标题天然在正文里），因此标题里的 API 名/节名也能被检索命中。

实测样例：

```text
发布模块 / 函数说明 / DDS_Publisher_create_datawriter
  chunk: DCPSDLL DDS_DataWriter * DDS_Publisher_create_datawriter ( DDS_Publisher * publisher , ... )
         创建DataWriter。
         参数
         | [in,out] | publisher | 指向目标。 |
         ...
  metadata: content_type=api  api_name=DDS_Publisher_create_datawriter  section_level=3

ZRDDS常见问题 / 1.技术支持 / 1.1.ZRDDS支持哪些操作系统以及编译器？   content_type=faq
ZRDDS版本记录 / ZRDDSv2.2.5 / 安装包                                content_type=guide（D 组版本冲突题素材）
臻融数据分发服务（ZRDDSv2.4.0）在线文档 / ZRDDS介绍 / QoS            content_type=guide
```

`content_type` 分类实测分布：`api 952 / tutorial 159 / guide 123 / error 49 / faq 22`（枚举受 Schema 校验）；`api_name` 非空 482 条，全部来自成员节点。代码块加 ` ```c ` fence、表格线性化为 Markdown 管道表——两者按**原子块**处理，绝不从中间切断（743 行的调试日志表按行分段为 49 块，每块重复表头）。

`error_code` 实测全空（0 条）：与 8-30 审计「E1003 在语料中不存在」的结论一致，可作交叉验证。

---

## 5. 运行方式

```bash
# 全量（默认 doc-dir + 默认输出）
python -m data_pipeline.html_loader --base-url https://docs.zrtechnology.com/cdoc/html

# 调试：只跑前 20 个文件 + 报告落盘
python -m data_pipeline.html_loader --limit 20 --report-json .tmp/html_report.json
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--doc-dir` | `data/raw/developer-guides/cdoc_html` | HTML 源目录 |
| `--out` | `data/processed/html_v1.jsonl` | Node 集输出 |
| `--base-url` | 空 | 引用基址；**由实验配置 `sources[].url` 传入** |
| `--source-id` | `zrdds_dev_guide` | 与本仓库配置一致，勿改（`generation/source_labels.py` 已按此名注册） |
| `--version` | `2.4` | index.html 自称「ZRDDSv2.4.0 在线文档」（实测） |
| `--max-chars` / `--min-chars` | `2500` / `20` | 与 struct / semantic 方案同口径 |
| `--include-source-listings` | 关 | 收录 147 个源码清单页（决策可逆） |
| `--drop-index-pages` | 关 | 剔除纯索引页（annotated/classes/functions/pages/modules/dir_*） |

**接线接口**（`scripts/ingest.py` 多来源注册式接入）：

```python
from data_pipeline.html_loader import build_html_chunks, write_nodes_jsonl
chunks, stats = build_html_chunks(s.path, base_url=s.url, source_id=s.id, version=s.version)
write_nodes_jsonl(chunks, "data/processed/html_v1.jsonl")
```

`discover_html_files(doc_dir, ...)` 返回确定性排序的文件清单，可直接用于按来源注册/重建索引。

---

## 6. 实测质检（`logs/html_loader_report.json`）

| 指标 | 结果 | 说明 |
|---|---|---|
| Metadata 不合规 / 缺 source_url / 页码非空 | 0 / 0 / 0 | html 分支契约全绿 |
| 噪声残留 / 代码块切断 / 表格异常 | 0 / 0 / 0 | 过滤与原子保护生效 |
| chunk_id 重复 | 0 | 1337 条全局唯一 |
| 长度分布 | min 15 / p50 305 / p95 2042 / max 4135 | 平均 584 字符 |
| 超 1200 token | 8 | 均为被原子保护的代码块（与 PDF 侧同策略） |
| 重复文本 94 条 | 已核 | **源 HTML 自身冗余**，非解析重访：如 `downloads.html` 同一安装包表在 3 个版本节各出现一次（源码实测出现 5 次）、`group___c_publication.html` 多个函数共用同一段返回码清单（源码 19 次） |

已知的两条 15~16 字符短块为 XML 示例页的引导句（其后是超长 XML 代码块，无法并入）——保留比丢弃更忠实，未做特殊处理。

---

## 7. 复现与验证

```bash
# 单测（合成 Doxygen 夹具 + 真实语料守卫）
python -m pytest tests/unit/data_pipeline/test_html_loader.py -q

# 全量重建（产物 → 后续由 ingest/检索层消费）
python -m data_pipeline.html_loader --doc-dir data/raw/developer-guides/cdoc_html \
    --out data/processed/html_v1.jsonl --source-id zrdds_dev_guide --version 2.4
```

单测 29 条覆盖：文件发现与开关可逆、标题层级与 `section_path`、成员签名/`api_name`/参数表、代码 fence 与行号剥离、表格线性化与超大表分段（表头重复）、Schema html 分支、URL 拼接、chunk_id 唯一、碎片归并、`load_nodes` 可消费、混合内容容器（行内下标/代码不丢正文、直系文本按文档序、注释不入正文），以及 289 内容页与真实成员页的守卫断言。
