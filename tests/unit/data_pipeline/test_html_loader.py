"""Doxygen HTML 加载器单测（成员 A · 第三周 §7.1/§7.3）。

覆盖四类契约：
  1. 文件发现与噪声排除（search/static/*_source.html，两个待会签开关）；
  2. 解析正确性（标题、层级、成员签名与参数表、代码块、表格线性化）；
  3. 统一 Metadata Schema（html 分支：页码全 None、source_url/title 必填、
     字段集 == metadata.ALL_FIELDS）；
  4. 产物契约（顶层字段、chunk_id 唯一、碎片归并、下游 load_nodes 可消费）。

合成夹具按真实 Doxygen 结构构造（div.contents / h2.groupheader / div.memitem /
div.memproto+table.memname / div.memdoc+dl.params / div.fragment+div.line /
table.memberdecls / div.navpath / div.tabs / span.lineno），
另附真实语料守卫测试（语料缺失时 skip）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_pipeline.chunkers.base import Chunk
from data_pipeline.html_loader import (
    CHUNK_PREFIX,
    SOURCE_ID_DEFAULT,
    build_html_chunks,
    build_html_nodes,
    discover_html_files,
    load_html_documents,
    nodes_to_chunks,
    parse_html_document,
    quality_report,
    write_nodes_jsonl,
)
from data_pipeline.metadata import ALL_FIELDS, validate_metadata
from retrieval.nodes import load_nodes

REPO_ROOT = Path(__file__).resolve().parents[3]

# ==================== 合成夹具 ====================

_INDEX_HTML = """<!DOCTYPE html>
<html><head><title>ZRDDS: 臻融数据分发服务（ZRDDSv2.4.0）在线文档</title>
<script type="text/javascript" src="navtree.js"></script></head>
<body>
<div class="header">
  <div class="title">臻融数据分发服务（ZRDDSv2.4.0）在线文档</div>
  <div class="navpath"><b>ZRDDS</b> » 首页</div>
</div>
<div class="contents">
  <div class="navpath">导航残渣：首页 » 模块</div>
  <div class="tabs"><ul><li>[详情级别 1 2]</li></ul></div>
  <div class="levels">[详情级别 1 2 ]</div>
  <h1>ZRDDS介绍</h1>
  <p>ZRDDS 是服从 OMG DDS 规范的通信中间件。</p>
  <h2>实体</h2>
  <p>实体是通信的基本对象。</p>
  <h3>实体唯一标识</h3>
  <p>DDS_InstanceHandle_t 唯一标识一个实例。</p>
  <h2>QoS</h2>
  <p>QoS 通过策略控制通信行为。</p>
  <div class="fragment"><div class="line"><span class="lineno">1</span>DDS_Publisher *p = DDS_DomainParticipant_create_publisher(dp);</div>
<div class="line"><span class="lineno">2</span>if (p == NULL) return -1;</div></div>
  <table class="doxtable"><tr><th>策略</th><th>说明</th></tr>
  <tr><td>RELIABILITY</td><td>可靠传输</td></tr></table>
</div>
<div class="footer">生成于 2026 版权所有</div>
</body></html>
"""

_GROUP_HTML = """<!DOCTYPE html>
<html><head><title>ZRDDS: 发布模块</title></head>
<body><div class="contents">
  <table class="memberdecls">
    <tr class="heading"><td colspan="2"><h2 class="groupheader">函数</h2></td></tr>
    <tr class="memitem"><td class="memItemLeft">DDS_DataWriter *</td>
      <td class="memItemRight">DDS_Publisher_create_datawriter</td></tr>
    <tr class="memdesc"><td class="mdescLeft"></td>
      <td class="mdescRight">创建DataWriter。 更多...</td></tr>
  </table>
  <h2 class="groupheader">详细描述</h2>
  <p>本模块定义了ZRDDS发布模块提供的C用户接口。</p>
  <h2 class="groupheader">函数说明</h2>
  <div class="memitem">
    <div class="memproto"><table class="memname"><tr>
      <td class="memname">DCPSDLL DDS_DataWriter * DDS_Publisher_create_datawriter</td>
      <td>(</td><td class="paramtype">DDS_Publisher *</td><td class="paramname"><em>publisher</em></td>
      <td>, </td><td class="paramtype">DDS_Topic *</td><td class="paramname"><em>topic</em></td><td>)</td>
    </tr></table></div>
    <div class="memdoc">
      <p>创建DataWriter。</p>
      <dl class="params"><dt>参数</dt><dd>
        <table class="params"><tr><td class="paramname">publisher</td><td>指向目标发布者。 </td></tr>
        <tr><td class="paramname">topic</td><td>用于关联DataWriter的Topic实例指针。 </td></tr></table>
      </dd></dl>
      <dl class="return"><dt>返回</dt><dd>成功返回数据写者，失败返回 NULL。</dd></dl>
    </div>
  </div>
  <div class="memitem">
    <div class="memproto"><table class="memname"><tr>
      <td class="memname">DCPSDLL DDS_ReturnCode_t DDS_Publisher_delete_datawriter</td>
      <td>(</td><td class="paramtype">DDS_DataWriter *</td><td class="paramname"><em>writer</em></td><td>)</td>
    </tr></table></div>
    <div class="memdoc">
      <p>删除DataWriter。</p>
      <dl class="return"><dt>返回</dt><dd>DDS_RETCODE_OK 表示成功。</dd></dl>
    </div>
  </div>
</div></body></html>
"""

_FAQ_HTML = """<!DOCTYPE html>
<html><head><title>ZRDDS: ZRDDS常见问题</title></head>
<body><div class="contents"><div class="textblock">
  <h1>1.技术支持</h1>
  <h2>1.1.ZRDDS支持哪些操作系统以及编译器？</h2>
  <p>ZRDDS支持Windows XP及以上，已测试编译器：VS2008、VS2010。</p>
</div></div></body></html>
"""

_EXAMPLE_HTML = """<!DOCTYPE html>
<html><head><title>ZRDDS: DurabilityQos/main_pub.c</title></head>
<body><div class="contents">
  <p>该程序展示了使用DurabilityQos为后上线的接收端保留历史数据的逻辑。</p>
  <div class="fragment"><div class="line"><span class="lineno">1</span>#include "DomainParticipant.h"</div>
<div class="line"><span class="lineno">2</span>int main(void) { return 0; }</div></div>
</div></body></html>
"""

_SOURCE_LISTING_HTML = """<!DOCTYPE html>
<html><head><title>ZRDDS: Duration_t.h 源文件</title></head>
<body><div class="contents"><div class="fragment"><div class="line">typedef struct Duration_t { int sec; } Duration_t;</div></div></div></body></html>
"""

_EMPTY_HTML = """<!DOCTYPE html><html><head><title>ZRDDS: 工具</title></head>
<body><div class="navpath">无 contents 的独立工具页</div></body></html>
"""

_TINY_HTML = """<!DOCTYPE html><html><head><title>ZRDDS: 极短页</title></head>
<body><div class="contents"><p>短。</p></div></body></html>
"""

_BIG_TABLE_HTML = "<!DOCTYPE html><html><head><title>ZRDDS: 调试日志信息表</title></head>\n<body><div class=\"contents\"><table class=\"doxtable\">\n<tr><th>debug_no</th><th>file</th><th>content</th></tr>\n" + "".join(
    f"<tr><td>{i}</td><td>BuiltinParticipantWriter.cpp</td><td>local create locator {i} 填充填充填充填充填充</td></tr>\n"
    for i in range(120)
) + "</table></div></body></html>\n"


def _write_fixture_tree(root: Path) -> Path:
    """写出合成 Doxygen 目录（含被排除项），返回 cdoc_html 根。"""
    doc = root / "cdoc_html"
    (doc / "search").mkdir(parents=True)
    (doc / "static").mkdir(parents=True)
    files = {
        "index.html": _INDEX_HTML,
        "group___c_publication.html": _GROUP_HTML,
        "faq.html": _FAQ_HTML,
        "_durability_qos_2main_pub_8c-example.html": _EXAMPLE_HTML,
        "_z_r_duration__t_8h_source.html": _SOURCE_LISTING_HTML,
        "dds_qos_editor.html": _EMPTY_HTML,
        "tiny.html": _TINY_HTML,
        "zrdds_log_info.html": _BIG_TABLE_HTML,
        "annotated.html": _FAQ_HTML,
        "search/all_0.html": "<html><head><title></title></head><body>载入中...</body></html>",
        "static/header.html": "<html><body>页头残渣</body></html>",
    }
    for name, content in files.items():
        p = doc / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return doc


@pytest.fixture()
def fixture_dir(tmp_path: Path) -> Path:
    return _write_fixture_tree(tmp_path)


# ==================== 1. 文件发现与噪声排除 ====================


def test_discover_excludes_search_static_and_source_listings(fixture_dir: Path):
    names = [p.name for p in discover_html_files(fixture_dir)]
    # 目录级排除：search/（空壳页）、static/
    assert "all_0.html" not in names
    assert "header.html" not in names
    # 文件名级排除：147 个 C 源码清单页同款
    assert "_z_r_duration__t_8h_source.html" not in names
    # 正文页保留
    assert {"index.html", "group___c_publication.html", "faq.html",
            "dds_qos_editor.html", "zrdds_log_info.html"} <= set(names)
    assert len(names) == 8  # 11 个文件中 3 个被排除


def test_discover_is_deterministic_and_switches_reversible(fixture_dir: Path):
    a = [p.name for p in discover_html_files(fixture_dir)]
    b = [p.name for p in discover_html_files(fixture_dir)]
    assert a == b == sorted(a)
    # 两个待会签决策必须可逆（收录源码清单 / 剔除索引页）
    with_listings = [p.name for p in discover_html_files(fixture_dir, include_source_listings=True)]
    assert "_z_r_duration__t_8h_source.html" in with_listings
    no_index = [p.name for p in discover_html_files(fixture_dir, drop_index_pages=True)]
    assert "annotated.html" not in no_index


def test_discover_missing_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        discover_html_files(tmp_path / "nope")


# ==================== 2. 解析正确性 ====================


def test_title_from_title_tag_with_prefix_stripped(fixture_dir: Path):
    doc = parse_html_document(fixture_dir / "index.html")
    assert doc is not None
    assert doc.title == "臻融数据分发服务（ZRDDSv2.4.0）在线文档"


def test_navigation_and_script_pollution_stripped(fixture_dir: Path):
    doc = parse_html_document(fixture_dir / "index.html")
    text = "\n".join(b.text for b in doc.blocks)
    assert "导航残渣" not in text          # div.navpath
    assert "详情级别" not in text          # div.tabs / div.levels
    assert "版权所有" not in text          # div.footer（在 contents 外，双保险）
    assert "navtree.js" not in text        # script
    assert "载入中" not in text


def test_heading_hierarchy_becomes_section_path(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    paths = [n.section_path for n in nodes]
    doc_title = "臻融数据分发服务（ZRDDSv2.4.0）在线文档"
    assert f"{doc_title} / ZRDDS介绍" in paths                     # h1
    assert f"{doc_title} / ZRDDS介绍 / QoS" in paths                # h2 嵌在 h1 下
    assert f"{doc_title} / ZRDDS介绍 / 实体 / 实体唯一标识" in paths  # h3 嵌在 h2 下
    assert "ZRDDS常见问题 / 1.技术支持 / 1.1.ZRDDS支持哪些操作系统以及编译器？" in paths
    qos = next(n for n in nodes if n.section_path.endswith("/ QoS"))
    assert qos.section_level == 2 and "QoS 通过策略控制通信行为" in qos.text


def test_member_node_signature_api_name_and_param_table(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    member = next(n for n in nodes if n.api_name == "DDS_Publisher_create_datawriter")
    assert member.section_path == "发布模块 / 函数说明 / DDS_Publisher_create_datawriter"
    assert member.content_type == "api"
    assert member.section_level == 3           # h2 函数说明 + 1
    assert member.text.startswith("DCPSDLL DDS_DataWriter * DDS_Publisher_create_datawriter")
    assert "参数" in member.text and "publisher" in member.text   # dl.params 线性化
    assert "返回" in member.text and "NULL" in member.text        # dl.return


def test_node_text_starts_with_its_heading(fixture_dir: Path):
    """正文带本节标题（与 PDF 侧 struct 同口径），标题里的 API/节名可被检索命中。"""
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    node = next(n for n in nodes if n.section_path.endswith("/ 实体唯一标识"))
    assert node.text.startswith("实体唯一标识"), node.text[:40]
    assert "DDS_InstanceHandle_t" in node.text


def test_code_block_is_fenced_and_line_numbers_removed(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    node = next(n for n in nodes if "create_publisher" in n.text)
    assert node.text.count("```") == 2, "代码块必须成对闭合"
    assert "```c" in node.text
    assert "DDS_Publisher *p =" in node.text
    # 行号 span.lineno 不得进正文
    assert "\n1DDS_Publisher" not in node.text
    assert "1DDS" not in node.text


def test_table_linearized_to_pipe_table(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    qos = next(n for n in nodes if n.section_path.endswith("/ QoS"))
    assert "| 策略 | 说明 |" in qos.text
    assert "|---|---|" in qos.text
    assert "| RELIABILITY | 可靠传输 |" in qos.text


def test_oversized_table_split_with_header_repeated(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir)
    nodes = build_html_nodes(docs)
    log_nodes = [n for n in nodes if n.doc_file == "zrdds_log_info.html"]
    chunks = nodes_to_chunks(log_nodes)
    assert len(chunks) > 1, "743 行量级的表必须分段，不能整表单体"
    assert all("| debug_no | file | content |" in c.text for c in chunks), "每段都要重复表头"
    assert any("表续" in c.text for c in chunks)
    assert chunks[0].chunk_id.endswith("_00000")


def test_page_without_contents_is_skipped(fixture_dir: Path):
    docs, skipped = load_html_documents(fixture_dir)
    assert "dds_qos_editor.html" in skipped
    assert all(d.file_name != "dds_qos_editor.html" for d in docs)


# ==================== 3. 统一 Metadata Schema ====================


def test_metadata_matches_frozen_schema_html_branch(fixture_dir: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    assert chunks
    for c in chunks:
        md = c.metadata
        assert set(md) == set(ALL_FIELDS), "字段集必须与 metadata.py 白名单一致"
        assert validate_metadata(md) == [], f"metadata 不合规: {validate_metadata(md)}"
        assert md["source_type"] == "html"
        assert md["source_id"] == SOURCE_ID_DEFAULT          # C 的标签表已注册此名
        assert md["version"] == "2.4"
        assert md["product"] == "ZRDDS"
        # HTML 无页码：四字段必须全 None（PDF 侧才是 int 真值）
        assert md["printed_page_start"] is None and md["printed_page_end"] is None
        assert md["physical_page_start"] is None and md["physical_page_end"] is None
        # html 分支强制项
        assert md["source_url"]
        assert md["title"]
        assert md["content_type"] in ("api", "guide", "faq", "error", "tutorial")
        assert md["language"] == "c"
        assert 1 <= md["section_level"] <= 5


def test_source_url_composition(fixture_dir: Path):
    docs, _ = load_html_documents(fixture_dir, base_url="https://docs.example.com/cdoc/html/")
    doc = next(d for d in docs if d.file_name == "faq.html")
    assert doc.source_url == "https://docs.example.com/cdoc/html/faq.html"
    # 无 base_url 时退化为文件名定位符（契约要求非空）
    docs2, _ = load_html_documents(fixture_dir)
    assert next(d for d in docs2 if d.file_name == "faq.html").source_url == "faq.html"


def test_source_id_and_version_are_parameterized(fixture_dir: Path):
    chunks, _ = build_html_chunks(fixture_dir, source_id="api_ref", version="2.5")
    assert {c.metadata["source_id"] for c in chunks} == {"api_ref"}
    assert {c.metadata["version"] for c in chunks} == {"2.5"}


# ==================== 4. 产物契约 ====================


def test_chunk_top_level_fields_and_unique_ids(fixture_dir: Path, tmp_path: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    out = write_nodes_jsonl(chunks, tmp_path / "html_v1.jsonl")
    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == len(chunks)
    ids = []
    for rec in recs:
        assert set(rec) == {"chunk_id", "text", "metadata", "token_count",
                            "char_start", "char_end"}
        assert rec["chunk_id"].startswith(CHUNK_PREFIX + "_")
        assert rec["text"].strip() and rec["token_count"] > 0
        assert rec["metadata"]["node_ids"] == [rec["metadata"]["node_ids"][0]]
        ids.append(rec["chunk_id"])
    assert len(ids) == len(set(ids)), "chunk_id 必须全局唯一"


def test_artifact_consumable_by_downstream_loader(fixture_dir: Path, tmp_path: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    out = write_nodes_jsonl(chunks, tmp_path / "html_v1.jsonl")
    nodes = load_nodes(out)                      # B 的输入契约
    assert len(nodes) == len(chunks)
    assert all(n.node_id for n in nodes)         # 无空 node_id
    member = next(n for n in nodes if n.metadata.get("api_name"))
    assert member.source_id == SOURCE_ID_DEFAULT
    assert member.source_name == member.metadata["source_file"]
    assert member.section.endswith(member.metadata["api_name"])
    assert member.page_print is None and member.page_physical is None


def test_short_nodes_filtered_out(fixture_dir: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    assert all(c.metadata["source_file"] != "tiny.html" for c in chunks), \
        "低于 min_chunk_chars 的碎片不应进产物"
    chunks_keep, _ = build_html_chunks(fixture_dir, min_chunk_chars=0)
    assert any(c.metadata["source_file"] == "tiny.html" for c in chunks_keep), \
        "min_chunk_chars=0 时应保留（口径可关闭）"


def test_no_tiny_noise_chunks_after_coalescing(fixture_dir: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    short = [c for c in chunks if len(c.text.strip()) < 15]
    assert not short, f"碎片归并后不应有 <15 字符的噪声块: {[c.chunk_id for c in short]}"


def test_quality_report_flags_nothing_on_fixture(fixture_dir: Path):
    chunks, _ = build_html_chunks(fixture_dir)
    report = quality_report(chunks, verbose=False)
    assert report["total_nodes"] == len(chunks)
    assert report["metadata_incomplete"] == 0
    assert report["missing_source_url"] == 0
    assert report["pages_present"] == 0
    assert report["chunk_id_dupes"] == 0
    assert report["pollution_hits"] == 0
    assert report["code_block_broken"] == 0
    assert report["api_nodes"] > 0


def test_build_stats_reports_skipped_and_empty_documents(fixture_dir: Path):
    chunks, stats = build_html_chunks(fixture_dir)
    assert stats["documents"] == 8 - 1                 # 排除 3 个，其中 1 个无 contents
    assert stats["skipped_no_contents"] == ["dds_qos_editor.html"]
    assert stats["chunks"] == len(chunks)
    assert "tiny.html" in stats["documents_without_nodes"]


# ==================== 5. 真实语料守卫（语料/产物缺失时 skip） ====================


CORPUS = REPO_ROOT / "data" / "raw" / "developer-guides" / "cdoc_html"
ARTIFACT = REPO_ROOT / "data" / "processed" / "html_v1.jsonl"


def test_real_corpus_discovery_count():
    if not CORPUS.exists():
        pytest.skip("HTML 语料未就位（data/raw/developer-guides/cdoc_html）")
    files = discover_html_files(CORPUS)
    assert len(files) == 289, (
        "内容页应为 289 = 527 个递归 html − 88 个 search 空壳 − 3 个 static − 147 个源码清单"
    )


def test_real_corpus_member_page_parses_create_datawriter():
    if not CORPUS.exists():
        pytest.skip("HTML 语料未就位")
    doc = parse_html_document(CORPUS / "group___c_publication.html")
    assert doc is not None and doc.title == "发布模块"
    nodes = build_html_nodes([doc])
    member = next(n for n in nodes if n.api_name == "DDS_Publisher_create_datawriter")
    assert member.content_type == "api"
    assert "writerQos" in member.text and "参数" in member.text
    joined = "\n".join(n.text for n in nodes)
    assert "详情级别" not in joined and "navpath" not in joined


def test_real_artifact_metadata_all_valid():
    if not ARTIFACT.exists():
        pytest.skip("html_v1.jsonl 未生成（先运行 python -m data_pipeline.html_loader）")
    chunks = [Chunk(**json.loads(line))
              for line in ARTIFACT.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = quality_report(chunks, verbose=False)
    assert report["metadata_incomplete"] == 0
    assert report["missing_source_url"] == 0
    assert report["pages_present"] == 0
    assert report["chunk_id_dupes"] == 0
    assert report["pollution_hits"] == 0
    assert report["total_nodes"] > 1000
