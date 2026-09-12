"""多来源 ingest 注册式接入（指南 §7 任务 1）单元测试。

覆盖三块纯逻辑，不触碰真实 PDF/HTML 数据与索引：
  1. 派生命名回归——单来源配置的 hash8 / nodes 路径与 Week2 冻结版逐字节一致
     （R5 教训：身份输入的静默变化会孤儿化全部真实索引，用四个真实配置钉死）；
     多来源配置的 nodes 文件名与索引身份按来源集区分。
  2. 合并 Node 集契约校验——来源注册一致性（source_id / version）、
     按来源分型的 metadata 校验（PDF 双页码 / HTML source_url）、
     双页码差值按 source_id 分组、跨来源 chunk_id 唯一。
  3. HTML 来源分派——A 的 html_loader 未交付时给可读错误（接缝见
     scripts/ingest.py 模块 docstring）。

端到端（真实 PDF 链路逐字节回归、HTML 真数据）由 `make ingest` 人工验收。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import experiment_config as ec  # noqa: E402
from data_pipeline.metadata import build_chunk_metadata  # noqa: E402

import ingest as ing  # noqa: E402


# ---------------------------------------------------------------- 基础夹具

_SINGLE_YAML = """\
schema_version: 1
experiment:
  name: {name}
  description: 单来源对照
  stage: ablation
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"
chunking:
  method: struct
  version: v1
  params: {{}}
embedding:
  provider: local
  model: bge-m3
"""

_MULTI_YAML = """\
schema_version: 1
experiment:
  name: {name}
  description: PDF+HTML 双来源
  stage: ablation
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
    version: "2.0"
  - id: zrdds_dev_guide
    type: html
    path: data/raw/developer-guides/cdoc_html
    version: "2.4"
    url: https://docs.example.com/zrdds/2.4/
chunking:
  method: struct
  version: v1
  params: {{}}
embedding:
  provider: local
  model: bge-m3
"""


def _write_cfg(tmp_path: Path, template: str, name: str) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(template.format(name=name), encoding="utf-8")
    return p


def _pdf_rec(cid: str, sid: str = "user_manual", printed: int = 127,
             physical: int = 133, version: str = "2.0") -> dict:
    md = build_chunk_metadata(
        source_id=sid, source_file="ZRDDS用户手册.pdf", source_type="pdf",
        section_path="PART2 基本概念 / 第10章 QoS策略 / 10.7 DurabilityQosPolicy",
        section_level=3, printed_page_start=printed, printed_page_end=printed,
        physical_page_start=physical, physical_page_end=physical,
        node_ids=["s_n1"], chunk_id=cid, part="PART2 基本概念",
        chapter="第10章 QoS策略", version=version,
    )
    return {"chunk_id": cid, "text": "DurabilityQosPolicy 正文内容测试。" * 3,
            "metadata": md, "token_count": 12, "char_start": 0, "char_end": 42}


def _html_rec(cid: str, sid: str = "zrdds_dev_guide", version: str = "2.4",
              url: str = "https://docs.example.com/zrdds/2.4/api/DataWriter") -> dict:
    md = build_chunk_metadata(
        source_id=sid, source_file="DataWriter_8h.html", source_type="html",
        section_path="ZRDDS Developer Guide / 实体 API / DataWriter / create_datawriter",
        section_level=4, printed_page_start=None, printed_page_end=None,
        physical_page_start=None, physical_page_end=None,
        node_ids=[], chunk_id=cid, source_url=url, version=version,
        content_type="api", api_name="create_datawriter", language="cpp",
    )
    return {"chunk_id": cid, "text": "create_datawriter() 创建 DataWriter 实体。",
            "metadata": md, "token_count": 9, "char_start": 0, "char_end": 30}


# ---------------------------------------------------------------- 派生命名

@pytest.mark.parametrize(
    ("config", "hash8"),
    [
        ("struct_v1.yaml", "0a7830b7"),
        ("struct_bm25.yaml", "677d777f"),
        ("semantic_v1.yaml", "7415d375"),
        ("hybrid_v1.yaml", "ade09e39"),
    ],
)
def test_single_source_identity_frozen(config, hash8):
    """R5 回归钉：四个真实配置的索引身份不得因本次多来源改造漂移。"""
    cfg = ec.load(REPO_ROOT / "configs" / "experiments" / config)
    assert ec.config_hash8(cfg) == hash8, (
        f"{config} 的 hash8 从 {hash8} 漂移——索引身份输入被意外改动，"
        "既有真实索引将全部孤儿化（R5 事故类）"
    )
    assert "sources" not in ec.index_identity_json(cfg)
    assert "__" not in ec.nodes_path(cfg).name


def test_multi_source_nodes_path_gets_sources_suffix(tmp_path):
    single = ec.load(_write_cfg(tmp_path, _SINGLE_YAML, "ms_single"))
    multi = ec.load(_write_cfg(tmp_path, _MULTI_YAML, "ms_multi"))
    assert ec.nodes_path(single).name == "struct_v1.jsonl"
    assert ec.nodes_path(multi).name == f"struct_v1__{ec.sources_digest8(multi)}.jsonl"
    assert ec.nodes_path(multi) != ec.nodes_path(single)


def test_multi_source_identity_differs_from_single(tmp_path):
    single = ec.load(_write_cfg(tmp_path, _SINGLE_YAML, "ms_single"))
    multi = ec.load(_write_cfg(tmp_path, _MULTI_YAML, "ms_multi"))
    assert "sources" in ec.index_identity_json(multi)
    assert "sources" not in ec.index_identity_json(single)
    assert ec.config_hash8(multi) != ec.config_hash8(single)


def test_multi_source_identity_order_independent(tmp_path):
    """来源注册顺序不影响派生命名（身份按 id 排序规范化）。"""
    a = ec.load(_write_cfg(tmp_path, _MULTI_YAML, "ms_order_a"))
    import yaml
    from scripts.experiment_config import ExperimentConfig
    raw = yaml.safe_load(_MULTI_YAML.format(name="ms_order_a"))
    raw["sources"] = list(reversed(raw["sources"]))
    reversed_cfg = ExperimentConfig.model_validate(raw)
    assert ec.sources_digest8(a) == ec.sources_digest8(reversed_cfg)
    assert ec.config_hash8(a) == ec.config_hash8(reversed_cfg)
    assert ec.nodes_path(a) == ec.nodes_path(reversed_cfg)


def test_multi_source_html_source_requires_url():
    """type=html 的来源缺 url 必须在配置层拒绝（指南 §7.2 引用可跳转）。"""
    import yaml
    from pydantic import ValidationError

    from scripts.experiment_config import ExperimentConfig
    raw = yaml.safe_load(_MULTI_YAML.format(name="ms_url"))
    raw["sources"][1].pop("url")
    with pytest.raises(ValidationError, match="url"):
        ExperimentConfig.model_validate(raw)


# ---------------------------------------------------------------- 合并校验

def _registered(*sources):
    return {s.id: s for s in sources}


def _source(id_, type_, version=None):
    from scripts.experiment_config import SourceCfg
    kw = {"id": id_, "type": type_, "path": "x"}
    if version:
        kw["version"] = version
    if type_ == "html":
        kw["url"] = "https://docs.example.com/"
    return SourceCfg.model_validate(kw)


def test_validate_mixed_sources_ok():
    reg = _registered(_source("user_manual", "pdf", "2.0"),
                      _source("zrdds_dev_guide", "html", "2.4"))
    recs = [_pdf_rec("p1"), _pdf_rec("p2"),
            _html_rec("h1"), _html_rec("h2")]
    ing.validate_nodes_jsonl(recs, label="mixed", registered_sources=reg)


def test_validate_html_missing_source_url_fails():
    reg = _registered(_source("zrdds_dev_guide", "html", "2.4"))
    recs = [_html_rec("h1", url="")]
    with pytest.raises(ValueError, match="source_url"):
        ing.validate_nodes_jsonl(recs, label="x", registered_sources=reg)


def test_validate_unknown_source_id_fails():
    reg = _registered(_source("user_manual", "pdf", "2.0"))
    recs = [_pdf_rec("p1", sid="not_registered")]
    with pytest.raises(ValueError, match="未在配置 sources 注册"):
        ing.validate_nodes_jsonl(recs, label="x", registered_sources=reg)


def test_validate_version_mismatch_fails():
    reg = _registered(_source("zrdds_dev_guide", "html", "2.4"))
    recs = [_html_rec("h1", version="2.0")]
    with pytest.raises(ValueError, match="version"):
        ing.validate_nodes_jsonl(recs, label="x", registered_sources=reg)


def test_validate_duplicate_chunk_id_across_sources_fails():
    reg = _registered(_source("user_manual", "pdf", "2.0"),
                      _source("zrdds_dev_guide", "html", "2.4"))
    recs = [_pdf_rec("dup"), _html_rec("dup")]
    with pytest.raises(ValueError, match="chunk_id 重复"):
        ing.validate_nodes_jsonl(recs, label="x", registered_sources=reg)


def test_validate_pdf_delta_grouped_by_source():
    """两个 PDF 来源可各有页码偏移（分组校验）；同来源内部不一致必须报错。"""
    reg = _registered(_source("user_manual", "pdf", "2.0"),
                      _source("troubleshooting", "pdf", "1.0"))
    ok = [
        _pdf_rec("a1", sid="user_manual", printed=127, physical=133),
        _pdf_rec("a2", sid="user_manual", printed=200, physical=206),
        _pdf_rec("b1", sid="troubleshooting", printed=5, physical=3, version="1.0"),
        _pdf_rec("b2", sid="troubleshooting", printed=9, physical=7, version="1.0"),
    ]
    ing.validate_nodes_jsonl(ok, label="ok", registered_sources=reg)

    bad = [
        _pdf_rec("c1", sid="user_manual", printed=127, physical=133),
        _pdf_rec("c2", sid="user_manual", printed=200, physical=205),  # 差值变 5
    ]
    with pytest.raises(ValueError, match="双页码差值"):
        ing.validate_nodes_jsonl(bad, label="bad", registered_sources=reg)


def test_validate_without_registry_keeps_legacy_behavior():
    """不传 registered_sources（旧行为）时仅做通用契约校验，缺页码的 HTML
    记录靠 validate_metadata 的 html 分支把关。"""
    recs = [_html_rec("h1")]
    ing.validate_nodes_jsonl(recs, label="legacy")


# ---------------------------------------------------------------- HTML 分派

def test_html_source_without_loader_gives_readable_error(monkeypatch):
    """html_loader 缺席时（loader 未交付/环境缺失），html 来源分派给出含接口签名的可读错误。"""
    import types
    # A 的 loader 第三周已交付（PR#28）；本测试模拟其缺席（sys.modules 置 None → ImportError）
    monkeypatch.setitem(sys.modules, "data_pipeline.html_loader", None)
    src = _source("zrdds_dev_guide", "html", "2.4")
    cfg = types.SimpleNamespace(chunking=types.SimpleNamespace(params={}))
    with pytest.raises(RuntimeError, match="html_loader") as ei:
        ing._process_html_source(src, cfg)
    assert "build_html_chunks" in str(ei.value)


def test_ingest_main_fails_fast_on_html_only_config(tmp_path, capsys, monkeypatch):
    """仅注册 html 来源且 loader 缺席：main 退出码 1，错误可读且不落任何产物。

    loader 必须显式模拟缺席（sys.modules 置 None）——A 的 loader 交付后，若不拦截，
    本测试会在 pytest 期真跑 288 页 HTML 解析并把单来源命名产物 struct_v1.jsonl
    覆盖成 html-only 内容（2026-09-12 实际发生过，产物经确定性重跑再生）。
    """
    yaml_text = _MULTI_YAML.format(name="ms_html_only").replace(
        "  - id: user_manual\n    type: pdf\n"
        "    path: data/raw/manuals/ZRDDS用户手册.pdf\n    version: \"2.0\"\n", ""
    )
    p = tmp_path / "ms_html_only.yaml"
    p.write_text(yaml_text, encoding="utf-8")

    import ingest as ing_mod
    monkeypatch.setitem(sys.modules, "data_pipeline.html_loader", None)
    orig_argv = sys.argv
    sys.argv = ["ingest.py", "--config", str(p)]
    try:
        rc = ing_mod.main()
    finally:
        sys.argv = orig_argv
    assert rc == 1
    err = capsys.readouterr().err
    assert "html_loader" in err
