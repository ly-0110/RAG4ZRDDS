# G:\DSH workspace\data_pipeline\metadata.py
"""
统一 Metadata Schema（单一事实源）—— v1.0 已冻结（Week 2），Week 3 HTML 直接复用。

冻结声明（2026-08-31，Week 2 验收）：
  * 本文件是 Metadata 的唯一事实源；任何新增/删除/改名必填字段都必须
    走「升级 v2.0 + 迁移映射」流程，禁止就地修改 REQUIRED_FIELDS。
  * 消费方（Chunker / Retriever / Citation / API / HTML Loader）只允许
    引用本文件定义的字段名与枚举值。
  * PDF 与 HTML 双来源统一落盘此 Schema；来源差异只体现在字段取值
    （html 必填 source_url，pdf 必填双页码），字段名完全一致。

与指南 §7.2 建议 Schema 的对应关系（HTML 复用对照表）：
  §7.2 字段   → 本 Schema 字段
  document_id → source_file（文档级唯一标识；HTML 可为规范 URL 的文件名）
  source_name → source_file
  source_url  → source_url（html 必填）
  title       → title（节标题，可由 section_path 末段派生）
  section     → section_path（完整 PART/章/节 路径，比 §7.2 更细）
  page        → printed_page_start/end + physical_page_start/end（双页码）
  version     → version
  language    → language（可选）
  platform    → platform（可选）
  content_type→ content_type（可选）
  product     → product
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

# ========== Schema 版本（冻结标记） ==========
SCHEMA_VERSION = "v1.0"
FROZEN_SINCE = "2026-W2"   # 冻结周次；v2.0 升级时必须提供迁移映射

# ========== 字段白名单 ==========
# 必填字段（缺一不可）—— Week 2 冻结，Week 3 复用
REQUIRED_FIELDS = [
    "source_id",            # 知识源注册名（=实验配置 sources[].id，如 "user_manual"；
                            # 2026-08-28 会签必填，B 检索日志/Citation 依赖，勿删）
    "source_file",          # 来源文件标识（PDF 文件名 / HTML 文档名）＝§7.2 document_id
    "source_type",          # "pdf" | "html"
    "part",                 # PART 级标题（HTML 可为 ""，section_path 仍完整）
    "chapter",              # 章级标题（HTML 可为 ""）
    "section_path",         # 完整路径 "PART1 / 第1章 / 1.1 节"（HTML: "文档 / 章节 / 节"）
    "section_level",        # 1~5（HTML 按 h1~h5 对应）
    "printed_page_start",   # 印刷页码起（HTML 可 None）
    "printed_page_end",     # 印刷页码止（HTML 可 None）
    "physical_page_start",  # 物理页码起（HTML 可 None）
    "physical_page_end",    # 物理页码止（HTML 可 None）
    "node_ids",             # List[str] 关联的 SectionNode IDs（HTML 可为 []）
    "chunk_id",             # 本 Chunk 唯一 ID
    "version",              # 文档版本 "2.0" / "2.4"
    "product",              # "ZRDDS"
]

# 可选字段（HTML 专用 / 检索过滤 / 前端展示）
OPTIONAL_FIELDS = [
    "language",             # "java" | "c" | "cpp" | "python" | ...
    "platform",             # "linux" | "windows" | "macos" | ...
    "content_type",         # "api" | "guide" | "faq" | "error" | "tutorial"
    "api_name",             # 具体 API 名（如 "create_datawriter"）
    "error_code",           # 错误码（如 "E1003"）
    "source_url",           # HTML 必填；PDF 留空
    "title",                # 节标题（可由 section_path 末段派生；HTML h1~h5）
]

ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# 枚举取值（检索过滤与前端展示复用；缺省 None 表示未标注）
CONTENT_TYPES = ("api", "guide", "faq", "error", "tutorial")
SOURCE_TYPES = ("pdf", "html")
LANGUAGES = ("c", "cpp", "java", "python", "csharp", "go")
PLATFORMS = ("linux", "windows", "macos")

# 字段说明（Week 3 HTML Loader / 检索过滤 / 前端渲染共用）
FIELD_DOCS: Dict[str, str] = {
    "source_id": "知识源注册名（=实验配置 sources[].id，如 user_manual）；跨 chunk 相同",
    "source_file": "来源文件标识（PDF 文件名 / HTML 文档名）；文档级唯一，跨 chunk 相同",
    "source_type": "来源类型：pdf | html",
    "part": "PART 级标题（一级分区）",
    "chapter": "章级标题（二级分区）",
    "section_path": "完整节路径，'/' 分隔；PDF 格式 'PART / 章 / 节'，HTML 格式 '文档 / 章节 / 节'",
    "section_level": "节层级 1~5（HTML 与 h1~h5 对应）",
    "printed_page_start": "印刷页码起点（封面目录无印刷页可 None）",
    "printed_page_end": "印刷页码终点",
    "physical_page_start": "物理页码起点（PDF 解析页码）",
    "physical_page_end": "物理页码终点",
    "node_ids": "关联的 SectionNode ID 列表（HTML 可空）",
    "chunk_id": "Chunk 全局唯一 ID",
    "version": "文档版本号（检索过滤条件）",
    "product": "产品名（跨文档过滤条件）",
    "language": "代码语言（API 文档标注）",
    "platform": "目标平台",
    "content_type": "内容类型：api|guide|faq|error|tutorial",
    "api_name": "API 名称（如 create_datawriter）",
    "error_code": "错误码（如 E1003）",
    "source_url": "HTML 来源 URL；PDF 留空",
    "title": "节标题（HTML 必填；PDF 可由 section_path 派生）",
}


# ========== 构建函数 ==========
def build_chunk_metadata(
    *,
    source_id: str = "",
    source_file: str,
    source_type: str,
    section_path: str,
    section_level: int,
    printed_page_start: Optional[int],
    printed_page_end: Optional[int],
    physical_page_start: Optional[int],
    physical_page_end: Optional[int],
    node_ids: List[str],
    chunk_id: str,
    part: str = "",
    chapter: str = "",
    source_url: str = "",
    version: str = "2.0",
    product: str = "ZRDDS",
    **optional
) -> Dict[str, Any]:
    """
    统一入口：所有 Chunker / HTML Loader 产出 metadata 时必须调用此函数。
    返回包含 ALL_FIELDS 的 dict，缺失可选字段填 None。

    冻结约束：
      * REQUIRED_FIELDS 不可缺；缺失抛 ValueError（缺省值仅允许 part/chapter 为空串，
        因为 HTML 可能无 PART/章 概念，但 section_path 必须完整）。
      * 页码四字段现在允许 None（HTML 无页码）；PDF 侧由 validate_metadata
        按 source_type="pdf" 强制要求非 None。
      * 可选字段可经 optional 传入，未传则填 None。
    """
    # 类型/来源校验
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"source_type 非法: {source_type!r}（允许 {SOURCE_TYPES}）")

    # 必填校验（页码允许 None，由 validate_metadata 按来源类型把关）
    missing = [f for f in REQUIRED_FIELDS
               if f not in locals() and f not in optional and f != "printed_page_start"
               and f != "printed_page_end" and f != "physical_page_start"
               and f != "physical_page_end"]
    if missing:
        raise ValueError(f"Missing required metadata fields: {missing}")

    meta: Dict[str, Any] = {}
    for f in REQUIRED_FIELDS:
        v = locals().get(f, optional.get(f))
        meta[f] = v

    # 可选字段补全：优先取命名参数（如 source_url/title），再取 optional，缺省 None
    for f in OPTIONAL_FIELDS:
        v = locals().get(f, optional.get(f))
        meta[f] = v if v is not None else None

    # 派生字段：title 缺省从 section_path 末段取；source_url 缺省 ""
    if not meta.get("title"):
        segs = [s.strip() for s in (section_path or "").split("/") if s.strip()]
        meta["title"] = segs[-1] if segs else ""
    if meta.get("source_url") is None:
        meta["source_url"] = ""
    return meta


def validate_metadata(meta: Dict[str, Any]) -> List[str]:
    """
    质检用：返回缺失/非法的必填字段列表（空列表 = 通过）。

    v1.0 冻结后的校验规则：
      * 通用必填：source_file / source_type / section_path / section_level /
        chunk_id / version / product 必须有值。
      * source_type="pdf"：双页码四字段必须为 int（HTML 允许 None）。
      * source_type="html"：source_url 必须非空；页码四字段可为 None。
      * 枚举校验：source_type / content_type / language / platform 非法值计入。
    """
    problems: List[str] = []

    st = meta.get("source_type")
    if st not in SOURCE_TYPES:
        problems.append(f"source_type({st!r})")

    # 通用必填（pdf/html 均要求）；part/chapter 仅 pdf 必填（HTML 无 PART/章 概念）
    for f in REQUIRED_FIELDS:
        if f in ("printed_page_start", "printed_page_end",
                 "physical_page_start", "physical_page_end"):
            continue  # 页码按来源类型单独把关
        if f in ("part", "chapter") and st == "html":
            continue  # HTML 允许无 PART/章
        if meta.get(f) in (None, ""):
            problems.append(f)

    # 按来源类型校验页码 / URL
    if st == "pdf":
        for f in ("printed_page_start", "printed_page_end",
                  "physical_page_start", "physical_page_end"):
            if not isinstance(meta.get(f), int):
                problems.append(f)
    elif st == "html":
        if not meta.get("source_url"):
            problems.append("source_url")
        if not meta.get("title"):
            problems.append("title")

    # 枚举可选字段
    if meta.get("content_type") and meta["content_type"] not in CONTENT_TYPES:
        problems.append(f"content_type({meta['content_type']!r})")
    if meta.get("language") and meta["language"] not in LANGUAGES:
        problems.append(f"language({meta['language']!r})")
    if meta.get("platform") and meta["platform"] not in PLATFORMS:
        problems.append(f"platform({meta['platform']!r})")

    return problems


def get_field_docs() -> Dict[str, str]:
    """返回字段说明字典（供文档生成 / 前端渲染引用）。"""
    return dict(FIELD_DOCS)


# ========== CLI 自测 ==========
if __name__ == "__main__":
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # GBK 控制台防崩（D5 同款）
    # PDF 示例（Week 2 产物同款；页码真值：印刷页 = 物理页 − 6，物理页 1 基）
    m = build_chunk_metadata(
        source_id="user_manual",
        source_file="ZRDDS用户手册.pdf",
        source_type="pdf",
        section_path="PART1 背景介绍 / 第1章 概述 / 1.1 分布式系统",
        section_level=3,
        printed_page_start=1,
        printed_page_end=2,
        physical_page_start=7,
        physical_page_end=8,
        node_ids=["s_PART1_ch1_1_1"],
        chunk_id="struct_v1_s_PART1_ch1_1_1_00000",
        part="PART1 背景介绍",
        chapter="第1章 概述",
    )
    print(f"✅ Schema {SCHEMA_VERSION}（冻结于 {FROZEN_SINCE}）")
    print("PDF 示例校验:", validate_metadata(m) or "通过")
    print()

    # HTML 示例（Week 3 复用同一 Schema）
    h = build_chunk_metadata(
        source_id="zrdds_dev_guide",
        source_file="zrdds-dev-guide.html",
        source_type="html",
        section_path="ZRDDS Developer Guide / 实体 API / DataWriter / create_datawriter",
        section_level=4,
        printed_page_start=None,
        printed_page_end=None,
        physical_page_start=None,
        physical_page_end=None,
        node_ids=[],
        chunk_id="html_v1_00000",
        source_url="https://docs.zrtechnology.com/api/datawriter#create",
        version="2.4",
        content_type="api",
        api_name="create_datawriter",
        language="cpp",
    )
    print("HTML 示例字段（复用同一 Schema，双页码为 None，URL 必填）:")
    for k, v in h.items():
        print(f"  {k}: {v}")
    print("HTML 示例校验:", validate_metadata(h) or "通过")
