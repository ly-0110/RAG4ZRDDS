# G:\知识库克隆\RAG4ZRDDS\data_pipeline\html_loader.py
"""Doxygen HTML 加载器（成员 A · 第三周 §7.1 / §7.3）——HTML 源 → 统一知识节点。

职责（指南 §7.1 成员 A 任务 1、2）：
  * 解析 `data/raw/developer-guides/cdoc_html/` 的 Doxygen HTML（本机实测 436 个顶层页），
    去除导航栏/脚本污染，保留 h1~h5 层级、代码块、表格、成员函数签名（原则见指南 §7.3）；
  * 产出按 `data_pipeline/metadata.py` v1.0（冻结）Schema 的统一 Node 集，
    落盘 `data/processed/html_v1.jsonl`，URL 进 metadata.source_url；
  * 顶层字段与 PDF 三方案产物完全一致（chunk_id / text / metadata / token_count /
    char_start / char_end），因此 `scripts/ingest.py::validate_nodes_jsonl`、
    `retrieval/nodes.py::load_nodes`、B 的索引与 C 的 Citation 通路无需改动即可消费。

**HTML 的「页等价物」（第三周抽象决策，2026-09-10 定）**：
  * 一个 HTML 文件 = 一个文档单元，`source_file` = 文件名（= §7.2 的 document_id）；
  * 页码四字段一律 None（HTML 无页概念；metadata.py 的 html 分支已允许）；
  * `source_url` 必填（validate_metadata 的 html 分支强制），由 `base_url` + 文件名拼出。

**节点粒度（§7.3 的树形结构 → 检索单元）**：
  * 标题驱动：h1~h5 与 `h2.groupheader` 构成层级，标题之间的正文归其最近的标题；
  * 每个 `div.memitem`（成员函数/类型/变量）= 独立节点，带 `api_name`，
    `content_type="api"`——直接支撑 §7.5 B 组题（如「create_datawriter() 的参数是什么？」）；
  * 整页结构如：`发布模块 / 函数说明 / DDS_Publisher_create_datawriter`
    （文档标题 → 章节 → 成员），与指南 §7.3 的实体树一致。

**噪声过滤（全部有全量实测依据，289 个候选正文页）**：
  * 目录级：`search/`（88 个空壳 html，正文仅“载入中/搜索中”JS）、`static/`（3 个）；
  * 文件名级：`*_source.html`（147 个 C/C++ 头文件源码清单，3.5MB）默认排除，
    `include_source_listings=True` 可回退收录（决策可逆，便于后续单开代码通路）；
  * 元素级：script/style/noscript、`div.navpath`、`div.tabs*`、`div.levels`（“详情级别”控件）、
    `div.header`/`div.footer`、`a.anchor`、`span.lineno`。

用法：
  python -m data_pipeline.html_loader                     # 默认全量 → data/processed/html_v1.jsonl
  python -m data_pipeline.html_loader --limit 20 --report-json .tmp/html_report.json
  python -m data_pipeline.html_loader --base-url https://docs.example.com/cdoc/html

依赖：beautifulsoup4 + lxml（requirements.txt 已锁）；不依赖 llama_index/embedding。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
from urllib.parse import quote

from bs4 import BeautifulSoup, NavigableString, Tag

from data_pipeline.chunkers.base import Chunk
from data_pipeline.metadata import build_chunk_metadata, validate_metadata

# ========== 默认值与口径常量 ==========
REPO_ROOT = Path(__file__).resolve().parent.parent

DOC_DIR_DEFAULT = "data/raw/developer-guides/cdoc_html"
OUT_DEFAULT = "data/processed/html_v1.jsonl"

SOURCE_ID_DEFAULT = "zrdds_dev_guide"   # C 的 generation/source_labels.py 已按此名注册（勿改）
VERSION_DEFAULT = "2.4"                 # index.html 自称「ZRDDSv2.4.0 在线文档」（实测）
LANGUAGE_DEFAULT = "c"                  # 本目录是 C 用户接口文档集（cdoc）
PRODUCT_DEFAULT = "ZRDDS"

CHUNK_PREFIX = "html_v1"
MAX_CHUNK_CHARS_DEFAULT = 2500          # 与 struct/hybrid 方案同口径
MIN_CHUNK_CHARS_DEFAULT = 20            # 与 semantic 的 min_chunk_chars 同口径
TABLE_PART_CHARS = 1800                 # 超大表按行分段的上限（段内含表头）
OVERSIZE_ATOMIC_FACTOR = 2              # 原子块超过 max_chars×该系数时按行/段落强制再切
SMALL_PIECE_FLOOR = 120                 # 短于此长度的片并入相邻片（消除 10~20 字符噪声块）
SMALL_PIECE_OVERFLOW = 1.3              # 碎片归并允许的片上浮系数

# 目录级排除（全量实测：search/ 88 个空壳、static/ 3 个）
EXCLUDE_DIRS = ("search", "static")
# 文件名级排除（147 个 C 源码清单页，非文档正文）
EXCLUDE_FILE_SUFFIXES = ("_source.html",)
# 索引页（纯链接列表，非正文）：默认收录，可用 --drop-index-pages 剔除
INDEX_PAGE_GLOBS = ("annotated.html", "classes.html", "functions.html",
                    "functions_*.html", "pages.html", "modules.html", "dir_*.html",
                    "files.html", "globals*.html", "namespace*.html")

DROP_TAGS = ("script", "style", "noscript", "iframe", "form", "input", "button")
# 精确 class token 匹配（h2.groupheader 的 class 是 "groupheader"，不会被 "header" 误伤）
DROP_CLASS_TOKENS = ("navpath", "navtab", "tabs", "tabs2", "tabs3", "levels",
                     "ingroups", "header", "footer", "summary", "anchor", "lineno")
HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5}
# 容器：继续下钻（正文块可能嵌在 div.textblock / dd / li 里）
CONTAINER_TAGS = ("div", "p", "li", "dd", "dt", "ul", "ol", "dl", "section",
                  "article", "blockquote", "td", "th", "tr", "tbody", "thead",
                  "center", "font", "span", "em", "strong", "b", "i", "code",
                  "a", "tt", "sub", "sup", "small", "big")
ERROR_CODE_RE = re.compile(r"\bE\d{3,5}\b")
WS_RE = re.compile(r"[ \t\u00a0\u3000]+")
SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)

_TIKTOKEN_ENCODER = None


def _encoder():
    """惰性取 tiktoken 编码（与 A 的其他 chunker 同口径 cl100k_base）。"""
    global _TIKTOKEN_ENCODER
    if _TIKTOKEN_ENCODER is None:
        import tiktoken
        _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENCODER


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


# ========== 数据模型 ==========
@dataclass
class Block:
    """页面内的一级内容块（标题 / 正文 / 代码 / 表格 / 成员）。"""
    kind: str                       # heading | text | code | table | member
    text: str = ""
    level: int = 0                  # heading: 1~5
    lang: Optional[str] = None      # code: 语言（fence 标注）
    api_name: Optional[str] = None  # member: API 名
    signature: Optional[str] = None  # member: 签名原文


@dataclass
class HtmlDocument:
    """一个 HTML 文件解析后的结果。"""
    file_name: str
    title: str                      # 文档标题（<title> 去前缀；回退 div.title / 文件名）
    source_url: str
    blocks: List[Block] = field(default_factory=list)
    content_type: Optional[str] = None


@dataclass
class HtmlNode:
    """节点级中间产物（尚未分片）。"""
    doc_file: str
    doc_title: str
    source_url: str
    section_path: str
    section_level: int
    text: str
    api_name: Optional[str] = None
    content_type: Optional[str] = None
    language: Optional[str] = None
    error_code: Optional[str] = None
    seq: int = 0


# ========== 文件发现 ==========
def discover_html_files(
    doc_dir: str | Path,
    *,
    include_source_listings: bool = False,
    drop_index_pages: bool = False,
) -> List[Path]:
    """列出参与解析的 HTML 文件（确定性排序，供 ingest 注册式接入复用）。

    排除规则见模块 docstring；`include_source_listings` / `drop_index_pages`
    让两个待会签决策可逆（默认值与 docs 一致）。
    """
    root = Path(doc_dir)
    if not root.exists():
        raise FileNotFoundError(f"HTML 源目录不存在: {root}")
    out: List[Path] = []
    for p in sorted(root.rglob("*.html")):
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        if not include_source_listings and p.name.endswith(EXCLUDE_FILE_SUFFIXES):
            continue
        if drop_index_pages and any(p.match(g) for g in INDEX_PAGE_GLOBS):
            continue
        out.append(p)
    return out


def _doc_slug(file_name: str) -> str:
    """文件名 → 稳定 ASCII 短名（chunk_id/node_id 用）。"""
    stem = Path(file_name).stem
    slug = SLUG_RE.sub("_", stem).strip("_").lower()
    return slug or "doc"


def _title_slug(title: str, limit: int = 40) -> str:
    """标题 → 稳定短名（保留中文，去掉标点空白）。"""
    slug = SLUG_RE.sub("_", title).strip("_")
    return slug[:limit]


def _source_url(base_url: str, file_name: str) -> str:
    """HTML 引用 URL：base_url 非空时拼接，否则退化为文件名定位符（契约要求非空）。"""
    quoted = quote(file_name)
    if not base_url:
        return quoted
    return f"{base_url.rstrip('/')}/{quoted}"


# ========== DOM 工具 ==========
def _clean(text: str) -> str:
    """空白归一化（表格/标题/正文共用），保留换行由调用方处理。"""
    return WS_RE.sub(" ", text.replace("\r", "")).strip()


def _classes(el: Tag) -> set:
    return set(el.get("class") or [])


def _is_dropped(el: Tag) -> bool:
    if el.name in DROP_TAGS:
        return True
    return bool(_classes(el) & set(DROP_CLASS_TOKENS))


def _direct_text(el: Tag) -> str:
    """只取直接文本子节点（不递归），用于 div.title 这类含面包屑的结构。"""
    parts = [str(c) for c in el.children if isinstance(c, NavigableString)]
    return _clean(" ".join(parts))


def _table_rows(table: Tag) -> List[List[str]]:
    """取本表格自身的行（排除嵌套表格的行），单元格文本归一化。"""
    rows: List[List[str]] = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = []
        for cell in tr.find_all(["td", "th"], recursive=False):
            txt = _clean(cell.get_text(" ", strip=True)).replace("|", "\\|")
            cells.append(txt)
        if cells:
            rows.append(cells)
    return rows


def _render_rows(rows: Sequence[Sequence[str]]) -> List[str]:
    """行 → Markdown 管道表行；单格行（Doxygen 的分组标题行）独立成行。"""
    out: List[str] = []
    group: List[Sequence[str]] = []

    def flush_group():
        if not group:
            return
        w = max(len(r) for r in group)
        for i, r in enumerate(group):
            padded = list(r) + [""] * (w - len(r))
            out.append("| " + " | ".join(padded) + " |")
            if i == 0 and len(group) > 1:
                out.append("|" + "---|" * w)
        group.clear()

    for r in rows:
        filled = [c for c in r if c]
        if len(filled) <= 1:                      # 分组标题行（如「函数」「成员变量」）
            flush_group()
            if filled:
                out.append(filled[0])
            continue
        group.append(r)
    flush_group()
    return out


def _split_table_blocks(rows: List[List[str]], budget: int = TABLE_PART_CHARS) -> List[Block]:
    """表格 → 一个或多个 table block；超大表按行分段（段内重复表头）。

    743 行的 zrdds_log_info 调试表若整表原子化会产生 6 万字符单体 chunk（无法检索），
    故按行分段——这是第三周对「表格线性化」的处置（第四周质检报告续跟）。
    """
    if not rows:
        return []
    header = rows[0]
    body = rows[1:]
    rendered_header = _render_rows([header])
    head_len = sum(len(x) for x in rendered_header)

    parts: List[List[List[str]]] = []
    cur: List[List[str]] = []
    cur_len = head_len
    for r in body:
        r_len = sum(len(c) for c in r) + 4
        if cur and cur_len + r_len > budget:
            parts.append(cur)
            cur, cur_len = [], head_len
        cur.append(r)
        cur_len += r_len
    if cur:
        parts.append(cur)

    blocks: List[Block] = []
    for i, part in enumerate(parts):
        lines = _render_rows([header] + part)
        if i > 0:
            lines.insert(0, f"（表续 {i + 1}/{len(parts)}，表头重复）")
        blocks.append(Block("table", text="\n".join(lines)))
    return blocks


def _split_code_lines(text: str, budget: int) -> List[str]:
    """超长代码块按行切分（每段自带 fence，不破坏成对性）。"""
    lines = text.split("\n")
    parts: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for ln in lines:
        if cur and cur_len + len(ln) + 1 > budget:
            parts.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(ln)
        cur_len += len(ln) + 1
    if cur:
        parts.append("\n".join(cur))
    return parts


def _code_block(fragment: Tag) -> Block:
    """div.fragment / pre.fragment → 代码块（剥行号，保留原文换行）。"""
    for junk in fragment.select("span.lineno, div.lineno, a.lineno"):
        junk.decompose()
    lines = fragment.select("div.line")
    if lines:
        text = "\n".join(ln.get_text("", strip=False).rstrip() for ln in lines)
    else:
        text = fragment.get_text("\n", strip=False)
    text = "\n".join(ln.rstrip() for ln in text.replace("\r", "").split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    return Block("code", text=text, lang=LANGUAGE_DEFAULT)


def _api_name_from_proto(proto: Tag) -> Optional[str]:
    """从 memproto 提取 API 名：td.memname 里最后一个标识符（函数/类型/变量名）。"""
    cell = proto.select_one("td.memname")
    raw = cell.get_text(" ", strip=True) if cell is not None else proto.get_text(" ", strip=True)
    raw = _clean(raw)
    matches = re.findall(r"[A-Za-z_]\w*", raw)
    return matches[-1] if matches else None


def _member_block(memitem: Tag) -> Block:
    """div.memitem → 成员节点（签名 + 说明/参数/返回值/示例），整块原子。"""
    proto = memitem.select_one("div.memproto")
    signature = _clean(proto.get_text(" ", strip=True)) if proto is not None else ""
    api_name = _api_name_from_proto(proto) if proto is not None else None
    doc = memitem.select_one("div.memdoc")
    body_blocks: List[Block] = []
    if doc is not None:
        _walk_blocks(doc, body_blocks)
    body = _join_blocks(body_blocks)
    text = signature if not body else f"{signature}\n\n{body}"
    return Block("member", text=text.strip(), api_name=api_name, signature=signature)


def _walk_blocks(el: Tag, out: List[Block]) -> None:
    """把 DOM 子树按文档序摊平为 Block 流（标题/代码/表格/成员不透明，其余递归）。"""
    for child in el.children:
        if not isinstance(child, Tag) or _is_dropped(child):
            continue
        name = child.name
        cls = _classes(child)

        if name in HEADING_TAGS:
            txt = _clean(child.get_text(" ", strip=True))
            if txt:
                out.append(Block("heading", text=txt, level=HEADING_TAGS[name]))
            continue
        if name == "div" and "memitem" in cls:
            out.append(_member_block(child))
            continue
        if name == "div" and "fragment" in cls:
            blk = _code_block(child)
            if blk.text:
                out.append(blk)
            continue
        if name == "pre":
            blk = _code_block(child)
            if blk.text:
                out.append(blk)
            continue
        if name == "table":
            out.extend(_split_table_blocks(_table_rows(child)))
            continue
        if name == "br" or name == "hr":
            continue
        if name in CONTAINER_TAGS:
            nested = [c for c in child.children if isinstance(c, Tag) and not _is_dropped(c)]
            if nested:
                _walk_blocks(child, out)
            else:
                txt = _clean(child.get_text(" ", strip=True))
                if txt:
                    out.append(Block("text", text=txt))
            continue
        # 未知标签按文本处理
        txt = _clean(child.get_text(" ", strip=True))
        if txt:
            out.append(Block("text", text=txt))


def _block_to_text(block: Block) -> str:
    """Block → 落盘文本（代码加 fence，表格已渲染，成员含签名）。"""
    if block.kind == "code":
        fence = f"```{block.lang}" if block.lang else "```"
        return f"{fence}\n{block.text}\n```"
    if block.kind == "heading":
        return block.text
    return block.text


def _join_blocks(blocks: Iterable[Block], separator: str = "\n\n") -> str:
    texts = [t for t in (_block_to_text(b).strip() for b in blocks) if t]
    return separator.join(texts).strip()


# ========== 文档解析 ==========
def parse_html_document(
    path: str | Path,
    *,
    base_url: str = "",
) -> Optional[HtmlDocument]:
    """解析单个 HTML 文件；无 div.contents 的页面（如 dds_qos_editor.html）返回 None。"""
    p = Path(path)
    soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "lxml")
    contents = soup.select_one("div.contents")
    if contents is None:
        return None

    # 标题：<title> 去 "ZRDDS: " 前缀（实测最干净）→ div.title 直接文本 → 文件名
    title = ""
    if soup.title is not None:
        title = _clean(soup.title.get_text(" ", strip=True))
        title = re.sub(r"^ZRDDS\s*[:：]\s*", "", title)
    if not title:
        title_el = soup.select_one("div.header div.title") or soup.select_one("div.title")
        title = _direct_text(title_el) if title_el is not None else ""
    if not title:
        title = p.name

    blocks: List[Block] = []
    _walk_blocks(contents, blocks)
    return HtmlDocument(
        file_name=p.name,
        title=title,
        source_url=_source_url(base_url, p.name),
        blocks=blocks,
        content_type=_doc_content_type(p.name),
    )


def _doc_content_type(file_name: str) -> str:
    """文档级 content_type（枚举受 metadata.validate_metadata 校验）。"""
    name = file_name.lower()
    stem = Path(name).stem
    if stem == "faq":
        return "faq"
    if stem.endswith("-example"):
        return "tutorial"
    if "log_info" in stem:
        return "error"
    if stem.startswith(("group_", "struct_", "class_", "functions_", "dir_", "namespace")) \
            or "interface" in stem or stem == "annotated" or stem == "classes":
        return "api"
    return "guide"


def load_html_documents(
    doc_dir: str | Path = DOC_DIR_DEFAULT,
    *,
    base_url: str = "",
    include_source_listings: bool = False,
    drop_index_pages: bool = False,
    limit: Optional[int] = None,
) -> tuple[List[HtmlDocument], List[str]]:
    """批量解析；返回 (文档列表, 被跳过的文件名列表)。"""
    files = discover_html_files(
        doc_dir,
        include_source_listings=include_source_listings,
        drop_index_pages=drop_index_pages,
    )
    if limit is not None:
        files = files[:limit]
    docs: List[HtmlDocument] = []
    skipped: List[str] = []
    for f in files:
        doc = parse_html_document(f, base_url=base_url)
        if doc is None:
            skipped.append(f.name)
            continue
        docs.append(doc)
    return docs, skipped


# ========== 节点装配 ==========
def _split_text_segments(text: str, budget: int) -> List[str]:
    """正文按段落/换行/句末边界切分（结构信号，不涉语义）。"""
    pieces: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + budget, len(text))
        if end < len(text):
            boundary = -1
            for sep in ("\n\n", "\n", "。", "；", ".", ";"):
                pos = text.rfind(sep, start, end)
                if pos > start + budget // 2:
                    boundary = pos + len(sep)
                    break
            end = boundary if boundary != -1 else end
        piece = text[start:end]
        if piece.strip():
            pieces.append(piece)
        start = end
    return pieces


def _node_from_blocks(
    doc: HtmlDocument,
    path_titles: List[str],
    level: int,
    blocks: List[Block],
    *,
    api_name: Optional[str] = None,
    content_type: Optional[str] = None,
    text_override: Optional[str] = None,
    heading_title: Optional[str] = None,
    language: str = LANGUAGE_DEFAULT,
) -> Optional[HtmlNode]:
    """累积块 → 节点（text_override 供成员节点直接带入渲染好的整块文本）。

    节点正文以本节标题开头——与 PDF 侧 struct 方案同口径（PDF 块从标题偏移起切，
    标题天然在正文内），保证「标题里的 API/节名」也能被检索命中。
    """
    body = (text_override if text_override is not None else _join_blocks(blocks)).strip()
    if heading_title and not body.startswith(heading_title):
        body = f"{heading_title}\n\n{body}" if body else heading_title
    text = body.strip()
    if not text:
        return None
    section_path = " / ".join([doc.title] + path_titles) if path_titles else doc.title
    code_match = ERROR_CODE_RE.search(text)
    return HtmlNode(
        doc_file=doc.file_name,
        doc_title=doc.title,
        source_url=doc.source_url,
        section_path=section_path,
        section_level=max(1, min(5, level)),
        text=text,
        api_name=api_name,
        content_type=content_type or doc.content_type,
        language=language,
        error_code=code_match.group(0) if code_match else None,
    )


def build_html_nodes(
    docs: Sequence[HtmlDocument],
    *,
    min_chunk_chars: int = MIN_CHUNK_CHARS_DEFAULT,
) -> List[HtmlNode]:
    """文档 → 节点：标题驱动层级 + 成员独立成节点。"""
    nodes: List[HtmlNode] = []
    for doc in docs:
        stack: List[tuple[int, str]] = []
        pending: List[Block] = []
        seq = 0

        def flush(level: int) -> None:
            nonlocal pending, seq
            if not pending:
                return
            node = _node_from_blocks(
                doc,
                [t for _, t in stack],
                level,
                pending,
                content_type=doc.content_type,
                heading_title=stack[-1][1] if stack else None,
            )
            pending = []
            if node is not None:
                node.seq = seq
                seq += 1
                nodes.append(node)

        for block in doc.blocks:
            if block.kind == "heading":
                flush(stack[-1][0] if stack else 1)
                while stack and stack[-1][0] >= block.level:
                    stack.pop()
                stack.append((block.level, block.text))
                continue
            if block.kind == "member":
                flush(stack[-1][0] if stack else 1)
                member_level = (stack[-1][0] + 1) if stack else 1
                member_path = [t for _, t in stack] + [block.api_name or "成员"]
                node = _node_from_blocks(
                    doc,
                    member_path,
                    member_level,
                    [],
                    api_name=block.api_name,
                    content_type="api",
                    text_override=block.text,
                )
                if node is not None:
                    node.seq = seq
                    seq += 1
                    nodes.append(node)
                continue
            pending.append(block)

        flush(stack[-1][0] if stack else 1)

    return [n for n in nodes if len(n.text.strip()) >= min_chunk_chars]


def _pack_segments(
    segments: Sequence[tuple[str, bool]],
    max_chunk_chars: int,
) -> List[str]:
    """段落流 → 片文本流：原子块（代码/表格）不切开，正文贪心填充。

    原子块前的正文尽量与原子块同片（引文+示例代码同块更利于检索）。
    """
    pieces: List[str] = []
    buf = ""
    for seg, atomic in segments:
        if atomic:
            if buf and len(buf) + len(seg) + 2 <= max_chunk_chars:
                pieces.append(f"{buf}\n\n{seg}")
                buf = ""
                continue
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.append(seg)
            continue
        if buf and len(buf) + len(seg) + 2 > max_chunk_chars:
            pieces.append(buf)
            buf = ""
        buf = f"{buf}\n\n{seg}" if buf else seg
    if buf:
        pieces.append(buf)
    return [p for p in pieces if p.strip()]


def _coalesce_small_pieces(
    pieces: Sequence[str],
    max_chunk_chars: int,
    *,
    floor: int = SMALL_PIECE_FLOOR,
    overflow: float = SMALL_PIECE_OVERFLOW,
) -> List[str]:
    """碎片归并：短于 floor 的片并入相邻片（允许有限超限），消除检索噪声块。

    实测来源：成员节点的「返回/返回的结果。」这类尾部短段，或原子块前后的引导句，
    单独成片后成为 10~20 字符的无意义 chunk（全量跑首次暴露 43 例，最小 10 字符）。
    """
    allowance = int(max_chunk_chars * overflow)
    out: List[str] = []
    for piece in pieces:
        if out and len(piece) < floor and len(out[-1]) + len(piece) + 2 <= allowance:
            out[-1] = f"{out[-1]}\n\n{piece}"
            continue
        out.append(piece)
    # 首片过短时并入次片（保持文档序）
    if len(out) >= 2 and len(out[0]) < floor and len(out[0]) + len(out[1]) + 2 <= allowance:
        out[1] = f"{out[0]}\n\n{out[1]}"
        out.pop(0)
    return out


def _pieces_for_node(node: HtmlNode, max_chunk_chars: int) -> List[str]:
    """节点 → 片文本流（段落级切分 + 原子保护 + 超长兜底 + 碎片归并）。"""
    segments: List[tuple[str, bool]] = []
    for para in re.split(r"\n{2,}", node.text):
        para = para.strip()
        if not para:
            continue
        atomic = para.startswith("```") or para.startswith("|") or "\n|" in para
        if atomic and len(para) > max_chunk_chars * OVERSIZE_ATOMIC_FACTOR:
            if para.startswith("```"):
                body = para.strip("`")
                for part in _split_code_lines(body, max_chunk_chars):
                    segments.append((f"```\n{part}\n```", True))
            else:  # 超大表格按行降级为普通段落（表格已在上游按行分段，这里兜底）
                segments.extend((line, False) for line in para.split("\n"))
            continue
        if not atomic and len(para) > max_chunk_chars:
            segments.extend((p, False) for p in _split_text_segments(para, max_chunk_chars))
            continue
        segments.append((para, atomic))
    return _coalesce_small_pieces(_pack_segments(segments, max_chunk_chars), max_chunk_chars)


def nodes_to_chunks(
    nodes: Sequence[HtmlNode],
    *,
    source_id: str = SOURCE_ID_DEFAULT,
    version: str = VERSION_DEFAULT,
    product: str = PRODUCT_DEFAULT,
    max_chunk_chars: int = MAX_CHUNK_CHARS_DEFAULT,
) -> List[Chunk]:
    """节点 → Chunk（统一 Metadata Schema + 原子块保护 + 超长结构切分 + 碎片归并）。"""
    chunks: List[Chunk] = []
    for node in nodes:
        doc_slug = _doc_slug(node.doc_file)
        title_slug = _title_slug(node.section_path.split(" / ")[-1])
        node_id = f"{doc_slug}_{node.seq:03d}" + (f"_{title_slug}" if title_slug else "")
        section_title = node.section_path.split(" / ")[-1]

        for seq, piece in enumerate(_pieces_for_node(node, max_chunk_chars)):
            chunk_id = f"{CHUNK_PREFIX}_{node_id}_{seq:05d}"
            meta = build_chunk_metadata(
                source_id=source_id,
                source_file=node.doc_file,
                source_type="html",
                part="",
                chapter="",
                section_path=node.section_path,
                section_level=node.section_level,
                printed_page_start=None,
                printed_page_end=None,
                physical_page_start=None,
                physical_page_end=None,
                node_ids=[node_id],
                chunk_id=chunk_id,
                source_url=node.source_url,
                title=section_title,
                version=version,
                product=product,
                language=node.language,
                content_type=node.content_type,
                api_name=node.api_name,
                error_code=node.error_code,
            )
            text = piece.strip()
            chunks.append(Chunk(
                chunk_id=chunk_id,
                text=text,
                metadata=meta,
                token_count=count_tokens(text),
                # HTML 无全局字符坐标：偏移量按「节点内相对位置」记（PDF 侧是真值坐标）
                char_start=0,
                char_end=len(text),
            ))
    return chunks


def build_html_chunks(
    doc_dir: str | Path = DOC_DIR_DEFAULT,
    *,
    base_url: str = "",
    source_id: str = SOURCE_ID_DEFAULT,
    version: str = VERSION_DEFAULT,
    max_chunk_chars: int = MAX_CHUNK_CHARS_DEFAULT,
    min_chunk_chars: int = MIN_CHUNK_CHARS_DEFAULT,
    include_source_listings: bool = False,
    drop_index_pages: bool = False,
    limit: Optional[int] = None,
) -> tuple[List[Chunk], dict]:
    """一步到位：目录 → Chunk 集 + 解析统计。"""
    docs, skipped = load_html_documents(
        doc_dir,
        base_url=base_url,
        include_source_listings=include_source_listings,
        drop_index_pages=drop_index_pages,
        limit=limit,
    )
    nodes = build_html_nodes(docs, min_chunk_chars=min_chunk_chars)
    chunks = nodes_to_chunks(
        nodes, source_id=source_id, version=version, max_chunk_chars=max_chunk_chars
    )
    docs_with_chunks = {c.metadata["source_file"] for c in chunks}
    stats = {
        "documents": len(docs),
        "documents_with_nodes": len(docs_with_chunks),
        "documents_without_nodes": sorted(
            d.file_name for d in docs if d.file_name not in docs_with_chunks
        ),
        "skipped_no_contents": skipped,
        "nodes": len(nodes),
        "chunks": len(chunks),
    }
    return chunks, stats


def write_nodes_jsonl(chunks: Sequence[Chunk], out_path: str | Path) -> Path:
    """落盘 Node 集（顶层字段与 PDF 三方案产物一致）。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
    return out


# ========== HTML 专用质检 ==========
POLLUTION_MARKERS = ("详情级别", "导航树", "生成于", "版权所有", "保留所有权利",
                     "navpath", "tabs2", "function loadNavtree")


def quality_report(chunks: Sequence[Chunk], *, verbose: bool = True) -> dict:
    """HTML 节点质检（替代 PDF 版 check_nodes——后者按双页码/PAGE_OFFSET 判定，不适用）。

    检查项：metadata 契约、source_url/URL 定位符、页码必须为空、成员 API 名覆盖、
    噪声残留、代码块成对、表格成对、过长/过短/重复、chunk_id 唯一。
    """
    report = {
        "total_nodes": len(chunks),
        "documents": len({c.metadata.get("source_file") for c in chunks}),
        "empty_nodes": 0,
        "short_nodes": 0,
        "long_nodes": 0,
        "over_token_nodes": 0,
        "duplicate_nodes": 0,
        "chunk_id_dupes": 0,
        "metadata_incomplete": 0,
        "missing_source_url": 0,
        "pages_present": 0,
        "api_nodes": 0,
        "level_out_of_range": 0,
        "pollution_hits": 0,
        "code_block_broken": 0,
        "table_broken": 0,
        "len_distribution": {},
        "sample_issues": [],
    }
    if not chunks:
        return report

    ids: set = set()
    seen_text: set = set()
    lens: List[int] = []
    for i, c in enumerate(chunks):
        text = c.text.strip()
        meta = c.metadata
        lens.append(len(text))

        if not text:
            report["empty_nodes"] += 1
            _add_sample(report, i, "EMPTY", c.chunk_id)
        elif len(text) < MIN_CHUNK_CHARS_DEFAULT:
            report["short_nodes"] += 1
            _add_sample(report, i, "TOO_SHORT", c.chunk_id)
        if len(text) > 10000:
            report["long_nodes"] += 1
            _add_sample(report, i, "TOO_LONG", c.chunk_id)
        if c.token_count > 1200:
            report["over_token_nodes"] += 1

        if c.chunk_id in ids:
            report["chunk_id_dupes"] += 1
            _add_sample(report, i, "CHUNK_ID_DUP", c.chunk_id)
        ids.add(c.chunk_id)

        if text in seen_text:
            report["duplicate_nodes"] += 1
            _add_sample(report, i, "DUPLICATE", c.chunk_id)
        seen_text.add(text)

        problems = validate_metadata(meta)
        if problems:
            report["metadata_incomplete"] += 1
            _add_sample(report, i, f"META:{problems}", c.chunk_id)
        if not meta.get("source_url"):
            report["missing_source_url"] += 1
        if any(meta.get(k) is not None for k in
               ("printed_page_start", "printed_page_end",
                "physical_page_start", "physical_page_end")):
            report["pages_present"] += 1
            _add_sample(report, i, "PAGE_NOT_NONE", c.chunk_id)
        if meta.get("content_type") == "api":
            report["api_nodes"] += 1
        lvl = meta.get("section_level")
        if not isinstance(lvl, int) or not 1 <= lvl <= 5:
            report["level_out_of_range"] += 1
        if any(m in text for m in POLLUTION_MARKERS):
            report["pollution_hits"] += 1
            _add_sample(report, i, "POLLUTION", c.chunk_id)

        for block in re.findall(r"```[\s\S]*?```", text):
            if not (block.startswith("```") and block.endswith("```")):
                report["code_block_broken"] += 1
        for table in re.findall(r"(?:\|.*\|(?:\n\|.*\|)+)", text):
            rows = [r for r in table.split("\n") if r.strip()]
            if len(rows) >= 2 and not all(r.count("|") >= 2 for r in rows):
                report["table_broken"] += 1

    import numpy as np
    report["len_distribution"] = {
        "min": int(min(lens)),
        "max": int(max(lens)),
        "mean": int(sum(lens) / len(lens)),
        "p50": int(np.percentile(lens, 50)),
        "p95": int(np.percentile(lens, 95)),
    }

    if verbose:
        _print_report(report)
    return report


def _add_sample(report: dict, idx: int, issue: str, chunk_id: str) -> None:
    if len(report["sample_issues"]) < 5:
        report["sample_issues"].append({"index": idx, "chunk_id": chunk_id, "issue": issue})


def _print_report(r: dict) -> None:
    print("\n========== HTML 节点质检报告 ==========")
    print(f"总节点数:            {r['total_nodes']}")
    print(f"文档数:              {r['documents']}")
    print(f"空节点:              {r['empty_nodes']}")
    print(f"过短(<{MIN_CHUNK_CHARS_DEFAULT}c):        {r['short_nodes']}")
    print(f"过长(>10000c):       {r['long_nodes']}")
    print(f"超Token(>1200):      {r['over_token_nodes']}")
    print(f"重复节点:            {r['duplicate_nodes']}")
    print(f"chunk_id 重复:       {r['chunk_id_dupes']}")
    print(f"Metadata 不合规:     {r['metadata_incomplete']}")
    print(f"缺 source_url:       {r['missing_source_url']}")
    print(f"页码非空(应为 0):    {r['pages_present']}")
    print(f"API 节点:            {r['api_nodes']}")
    print(f"层级越界(应为 0):    {r['level_out_of_range']}")
    print(f"噪声残留(应为 0):    {r['pollution_hits']}")
    print(f"代码块切断(应为 0):  {r['code_block_broken']}")
    print(f"表格异常:            {r['table_broken']}")
    if r["len_distribution"]:
        ld = r["len_distribution"]
        print(f"长度分布: min={ld['min']}, max={ld['max']}, "
              f"avg={ld['mean']}, p50={ld['p50']}, p95={ld['p95']}")
    if r["sample_issues"]:
        print("问题样本(前5):")
        for s in r["sample_issues"]:
            print(f"  [{s['issue']}] idx={s['index']} id={s['chunk_id']}")
    print("======================================\n")


# ========== CLI ==========
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Doxygen HTML → 统一 Node 集（成员 A · 第三周 §7.1）",
    )
    parser.add_argument("--doc-dir", default=DOC_DIR_DEFAULT,
                        help=f"HTML 源目录（默认 {DOC_DIR_DEFAULT}）")
    parser.add_argument("--out", default=OUT_DEFAULT,
                        help=f"Node 集输出（默认 {OUT_DEFAULT}）")
    parser.add_argument("--base-url", default="",
                        help="HTML 引用基址（实验配置 sources[].url；留空则用文件名定位符）")
    parser.add_argument("--source-id", default=SOURCE_ID_DEFAULT,
                        help=f"知识源注册名（默认 {SOURCE_ID_DEFAULT}，C 的标签表已注册）")
    parser.add_argument("--version", default=VERSION_DEFAULT,
                        help=f"文档版本（默认 {VERSION_DEFAULT}）")
    parser.add_argument("--max-chars", type=int, default=MAX_CHUNK_CHARS_DEFAULT)
    parser.add_argument("--min-chars", type=int, default=MIN_CHUNK_CHARS_DEFAULT)
    parser.add_argument("--include-source-listings", action="store_true",
                        help="收录 *_source.html 源码清单页（默认排除）")
    parser.add_argument("--drop-index-pages", action="store_true",
                        help="剔除纯索引页（annotated/classes/functions/pages/modules...）")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个文件（调试）")
    parser.add_argument("--report-json", default=None, help="质检报告落盘路径")
    parser.add_argument("--no-quality", action="store_true", help="跳过质检")
    args = parser.parse_args(argv)

    chunks, stats = build_html_chunks(
        args.doc_dir,
        base_url=args.base_url,
        source_id=args.source_id,
        version=args.version,
        max_chunk_chars=args.max_chars,
        min_chunk_chars=args.min_chars,
        include_source_listings=args.include_source_listings,
        drop_index_pages=args.drop_index_pages,
        limit=args.limit,
    )
    print(f"[html_loader] 文档 {stats['documents']} 个"
          f"（跳过无 contents 页 {len(stats['skipped_no_contents'])}: "
          f"{stats['skipped_no_contents'][:5]}）→ 节点 {stats['nodes']} → chunk {len(chunks)}")
    if not chunks:
        print("[html_loader] 错误: 产出 0 个 chunk", file=sys.stderr)
        return 1

    out = write_nodes_jsonl(chunks, args.out)
    print(f"[html_loader] 已写入 {out}")

    report = None
    if not args.no_quality:
        report = quality_report(chunks, verbose=True)
        if args.report_json:
            rp = Path(args.report_json)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[html_loader] 质检报告 → {rp}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # GBK 控制台防崩
    raise SystemExit(main())
