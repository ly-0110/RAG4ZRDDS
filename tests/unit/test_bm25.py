"""B 检索包 BM25 通路（retrieval/bm25.py）的单元测试。

分词为字符 bigram + ASCII 词保留，无外部模型依赖；
BM25Store 接口对齐 VectorStore（add_nodes/query/save/load）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from retrieval._bootstrap import experiment_config
from retrieval.bm25 import BM25Store, tokenize
from retrieval.nodes import NodeRecord


def make_node(node_id: str, text: str, **metadata) -> NodeRecord:
    return NodeRecord(node_id=node_id, text=text, metadata=dict(metadata))


# ---------------------------------------------------------------- tokenize


def test_tokenize_chinese_text_into_bigrams():
    assert tokenize("数据分发") == ["数据", "据分", "分发"]


def test_tokenize_single_chinese_char_keeps_unigram():
    assert tokenize("域") == ["域"]


def test_tokenize_ascii_words_kept_whole_and_lowercased():
    assert tokenize("DomainParticipant E1003") == ["domainparticipant", "e1003"]


def test_tokenize_mixed_cjk_and_ascii():
    # 中文段切 bigram；ASCII 标识符整体保留；标点/空白作分隔符
    assert tokenize("如何调用 connect() 接口？") == [
        "如何", "何调", "调用", "connect", "接口",
    ]


def test_tokenize_empty_and_punctuation_only_return_empty():
    assert tokenize("") == []
    assert tokenize("  ，。？！ ") == []


# ---------------------------------------------------------------- BM25Store


def make_store() -> BM25Store:
    store = BM25Store()
    store.add_nodes([
        make_node("n_conn", "连接失败时如何排查错误",
                  source_id="user_manual", source_name="ZRDDS用户手册.pdf",
                  section="3.4", page_print=36, page_physical=42),
        make_node("n_qos", "QoS 策略配置",
                  source_id="user_manual", source_name="ZRDDS用户手册.pdf",
                  section="4.1", page_print=44, page_physical=50),
        make_node("n_qos2", "QoS 策略配置文件 XML 结构",
                  source_id="dev_guide", source_name="开发指南.html",
                  section="6.2", page_print=60, page_physical=66),
    ])
    return store


def test_store_query_ranks_by_term_overlap():
    store = make_store()
    results = store.query("连接失败如何排查", top_k=3)
    assert results[0]["node_id"] == "n_conn"
    scores = {r["node_id"]: r["score"] for r in results}
    assert scores["n_conn"] > 0
    # 2026-09-07 D 代修 B1：零词面重叠（旧行为是 score==0 仍返回）不再作为证据
    assert "n_qos" not in scores
    assert all(s > 0 for s in scores.values())


def test_store_query_returns_empty_when_no_lexical_overlap():
    # 无证据信号：语料里没有词面重叠时返回空列表，下游据此走拒答路径
    store = make_store()
    assert store.query("区块链共识机制", top_k=5) == []


def test_store_save_omits_tokens_and_load_recomputes(tmp_path: Path):
    # B2：tokens 可由 text 确定性重算，不该落盘（301 节点产物曾达 2.4MB）
    store = make_store()
    store.save(tmp_path / "idx")
    data = json.loads((tmp_path / "idx" / "bm25.json").read_text(encoding="utf-8"))
    assert "tokens" not in data

    loaded = BM25Store.load(tmp_path / "idx")
    orig = store.query("QoS 策略配置 XML", top_k=5)
    restored = loaded.query("QoS 策略配置 XML", top_k=5)
    assert [(r["node_id"], r["score"]) for r in orig] == \
           [(r["node_id"], r["score"]) for r in restored]


def test_store_query_respects_top_k():
    store = make_store()
    results = store.query("QoS 策略配置", top_k=1)
    assert len(results) == 1
    assert results[0]["node_id"] == "n_qos"


def test_store_query_filters_by_metadata():
    store = make_store()
    results = store.query("QoS 策略配置", top_k=5, filters={"source_id": "dev_guide"})
    assert [r["node_id"] for r in results] == ["n_qos2"]


def test_store_query_filter_matching_nothing_returns_empty():
    store = make_store()
    assert store.query("QoS", top_k=5, filters={"source_id": "不存在"}) == []


def test_store_query_on_empty_store_returns_empty_list():
    assert BM25Store().query("任意问题", top_k=5) == []


def test_store_query_with_blank_question_returns_empty():
    store = make_store()
    assert store.query("", top_k=5) == []
    assert store.query("   ，。 ", top_k=5) == []


def test_store_skips_blank_text_nodes():
    store = BM25Store()
    store.add_nodes([
        make_node("n_blank", "   \n\t"),
        make_node("n_real", "域参与者 连接"),
    ])
    results = store.query("域参与者连接", top_k=5)
    assert [r["node_id"] for r in results] == ["n_real"]


def test_store_query_returns_rich_chunk_shape():
    store = make_store()
    r = store.query("连接失败", top_k=1)[0]
    assert set(r) == {"node_id", "text", "metadata", "score"}
    assert r["node_id"] == "n_conn"
    assert r["text"] == "连接失败时如何排查错误"
    assert r["metadata"]["section"] == "3.4"
    assert isinstance(r["score"], float)


def test_store_save_and_load_roundtrip(tmp_path: Path):
    store = make_store()
    idx_dir = tmp_path / "index"
    store.save(idx_dir)
    assert (idx_dir / "bm25.json").exists()

    loaded = BM25Store.load(idx_dir)
    orig = store.query("QoS 策略配置 XML", top_k=5)
    restored = loaded.query("QoS 策略配置 XML", top_k=5)
    assert [(r["node_id"], r["score"]) for r in orig] == \
           [(r["node_id"], r["score"]) for r in restored]


def test_store_save_records_k1_b_params(tmp_path: Path):
    import json

    store = BM25Store(k1=2.0, b=0.5)
    store.add_nodes([make_node("n", "文本")])
    store.save(tmp_path / "idx")
    data = json.loads((tmp_path / "idx" / "bm25.json").read_text(encoding="utf-8"))
    assert data["k1"] == 2.0
    assert data["b"] == 0.5


def test_store_load_missing_index_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        BM25Store.load(tmp_path / "不存在")


# ---------------------------------------------------------------- 组装工厂分派


def _write_config(tmp_path: Path, retrieval_mode: str = "bm25",
                  params: str = "{}") -> Path:
    p = tmp_path / "baseline_bm25.yaml"
    p.write_text(
        f"""
schema_version: 1
experiment:
  name: baseline_bm25
  stage: baseline
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
chunking:
  method: struct
  version: v1
embedding:
  provider: local
  model: bge-m3
index:
  backend: chroma
retrieval:
  mode: {retrieval_mode}
  top_k: 5
  params: {params}
""".strip() + "\n",
        encoding="utf-8",
    )
    return p


def _write_nodes(tmp_path: Path, cfg) -> Path:
    nodes_file = experiment_config.nodes_path(cfg)
    nodes_file.parent.mkdir(parents=True, exist_ok=True)
    nodes_file.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in [
            {"node_id": "n1", "text": "连接失败时如何排查错误",
             "metadata": {"source_id": "user_manual",
                          "source_name": "ZRDDS用户手册.pdf", "section": "3.4",
                          "page_print": 36, "page_physical": 42}},
            {"node_id": "n2", "text": "QoS 策略配置文件结构",
             "metadata": {"source_id": "user_manual",
                          "source_name": "ZRDDS用户手册.pdf", "section": "4.1"}},
        ]) + "\n",
        encoding="utf-8",
    )
    return nodes_file


class _RaisingEmbed:
    def __call__(self, texts):
        raise AssertionError("bm25 通路不应调用 embedding")


def test_build_index_bm25_writes_index_and_is_queryable(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    _write_nodes(tmp_path, cfg)

    from retrieval.index import build_index
    from retrieval.retriever import build_retriever

    index_path = build_index(cfg, embed_fn=None)  # bm25 不需要 embedding 模型

    assert (index_path / "bm25.json").exists()
    retriever = build_retriever(cfg, embed_fn=None)
    results = asyncio.run(retriever.retrieve("连接失败如何排查", top_k=5))
    assert results[0]["node_id"] == "n1"
    assert results[0]["source_name"] == "ZRDDS用户手册.pdf"
    assert results[0]["page_print"] == 36
    assert results[0]["page_physical"] == 42


def test_build_index_bm25_ignores_embed_fn(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    _write_nodes(tmp_path, cfg)

    from retrieval.index import build_index

    index_path = build_index(cfg, embed_fn=_RaisingEmbed())
    assert (index_path / "bm25.json").exists()


def test_build_index_bm25_passes_k1_b_from_params(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(
        _write_config(tmp_path, params="{k1: 2.0, b: 0.5}")
    )
    _write_nodes(tmp_path, cfg)

    from retrieval.index import build_index

    index_path = build_index(cfg, embed_fn=None)
    data = json.loads((index_path / "bm25.json").read_text(encoding="utf-8"))
    assert data["k1"] == 2.0
    assert data["b"] == 0.5


def test_build_retriever_bm25_missing_index_raises(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    from retrieval.retriever import build_retriever

    with pytest.raises(FileNotFoundError, match="build_index"):
        build_retriever(cfg, embed_fn=None)


def test_build_retriever_bm25_ignores_embed_fn(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    _write_nodes(tmp_path, cfg)

    from retrieval.index import build_index
    from retrieval.retriever import build_retriever

    build_index(cfg, embed_fn=None)
    retriever = build_retriever(cfg, embed_fn=_RaisingEmbed())
    results = asyncio.run(retriever.retrieve("QoS 配置文件", top_k=5))
    assert results[0]["node_id"] == "n2"


def test_bm25_retriever_returns_source_ref_contract(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    _write_nodes(tmp_path, cfg)

    from retrieval.index import build_index
    from retrieval.retriever import build_retriever, to_source_refs

    build_index(cfg, embed_fn=None)
    retriever = build_retriever(cfg, embed_fn=None)
    results = asyncio.run(retriever.retrieve("连接失败如何排查", top_k=5))

    assert set(results[0]) == {
        "node_id", "text", "source_id", "source_name", "section",
        "page_print", "page_physical", "score",
    }
    refs = to_source_refs(results)
    assert set(refs[0]) == {
        "node_id", "source_id", "source_name", "section",
        "page_print", "page_physical", "score",
    }
    assert "text" not in refs[0]


# ---------------------------------------------------------------- CLI 与真实产物


def test_cli_build_and_query_bm25_roundtrip(tmp_path, monkeypatch, capsys):
    import retrieval.cli as cli

    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))
    _write_nodes(tmp_path, cfg)
    cfg_path = str(tmp_path / "baseline_bm25.yaml")

    assert cli.main(["build", "--config", cfg_path]) == 0
    out = capsys.readouterr().out
    assert "索引已就绪" in out

    assert (
        cli.main(
            ["query", "--config", cfg_path, "--question", "连接失败如何排查", "--top-k", "3"]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "n1" in out
    assert "ZRDDS用户手册.pdf" in out


def test_real_struct_v1_artifact_bm25_build_and_query():
    # 真实产物（301 块）直接走 BM25 通路：不碰 embedding 模型，秒级完成
    artifact = Path(__file__).resolve().parents[2] / "data" / "processed" / "struct_v1.jsonl"
    if not artifact.exists():
        pytest.skip("struct_v1.jsonl 未生成（先运行 make ingest）")

    from retrieval.nodes import load_nodes

    store = BM25Store()
    store.add_nodes(load_nodes(artifact))

    results = store.query("如何创建 DataWriter？", top_k=5)
    assert len(results) == 5
    assert all(r["node_id"] for r in results)
    assert all(r["score"] > 0 for r in results)
    # 页码契约：真实产物经 NodeRecord 映射后必须可呈现
    for r in results:
        rec = NodeRecord(r["node_id"], r["text"], r["metadata"])
        assert rec.page_print is not None
        assert rec.page_physical is not None
