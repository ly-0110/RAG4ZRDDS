"""B 检索包（retrieval/）的单元测试。

嵌入函数通过依赖注入使用确定性假向量，不下载真实模型；
向量库用 chromadb EphemeralClient（内存态），不落盘。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest

from retrieval._bootstrap import experiment_config
from retrieval.index import build_index
from retrieval.nodes import NodeRecord, load_nodes
from retrieval.embeddings import build_embedding
from retrieval.retriever import VectorRetriever, build_retriever
from retrieval.vector_store import VectorStore

SOURCE_REF_KEYS = {
    "node_id", "source_id", "source_name", "section",
    "page_print", "page_physical", "score",
}


class FakeEmbedder:
    """按文本查表返回确定性向量；未知文本返回零向量。"""

    def __init__(self, vectors: dict[str, list[float]], dim: int = 4):
        self.vectors = vectors
        self.dim = dim

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors.get(t, [0.0] * self.dim) for t in texts]


def make_node(node_id: str, text: str, **metadata) -> NodeRecord:
    return NodeRecord(node_id=node_id, text=text, metadata=dict(metadata))


def make_store() -> tuple[VectorStore, dict[str, list[float]]]:
    """三个互为正交向量的节点 + 一个与 Alpha 同向量的查询。"""
    vecs = {
        "alpha 的正文": [1.0, 0.0, 0.0, 0.0],
        "beta 的正文": [0.0, 1.0, 0.0, 0.0],
        "gamma 的正文": [0.0, 0.0, 1.0, 0.0],
        "查询 alpha": [1.0, 0.0, 0.0, 0.0],
    }
    # EphemeralClient 进程内共享存储：集合名必须唯一，避免测试互相污染
    store = VectorStore(
        embed_fn=FakeEmbedder(vecs), collection_name=f"test_{uuid.uuid4().hex}"
    )
    store.add_nodes([
        make_node("n_alpha", "alpha 的正文",
                  source_id="user_manual", source_name="ZRDDS用户手册.pdf",
                  section="3.4", page_print=42, page_physical=36),
        make_node("n_beta", "beta 的正文",
                  source_id="user_manual", source_name="ZRDDS用户手册.pdf",
                  section="4.1", page_print=50, page_physical=44),
        make_node("n_gamma", "gamma 的正文",
                  source_id="user_manual", source_name="ZRDDS用户手册.pdf",
                  section="5.2", page_print=60, page_physical=54),
    ])
    return store, vecs


# ---------------------------------------------------------------- nodes 加载


def test_load_nodes_reads_jsonl_records(tmp_path: Path):
    p = tmp_path / "nodes.jsonl"
    p.write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in [
        {"node_id": "a", "text": "内容A", "metadata": {"section": "1.1"}},
        {"node_id": "b", "text": "内容B", "metadata": {}},
    ]) + "\n", encoding="utf-8")

    nodes = load_nodes(p)

    assert len(nodes) == 2
    assert nodes[0].node_id == "a"
    assert nodes[0].text == "内容A"
    assert nodes[0].metadata == {"section": "1.1"}
    assert nodes[1].metadata == {}


def test_load_nodes_tolerates_missing_metadata(tmp_path: Path):
    p = tmp_path / "nodes.jsonl"
    p.write_text('{"node_id": "x", "text": "只有正文"}\n', encoding="utf-8")

    nodes = load_nodes(p)

    assert nodes[0].metadata == {}


def test_node_record_maps_page_field_variants():
    # A 的元数据里页码命名可能不同：统一 schema 用 page（印刷页），
    # 章节树用 printed_page/physical_page——都应收敛到同一字段。
    n = make_node("a", "t", page=42, physical_page=36)
    assert n.page_print == 42
    assert n.page_physical == 36

    n2 = make_node("b", "t", printed_page=10)
    assert n2.page_print == 10
    assert n2.page_physical is None


def test_node_record_source_name_falls_back_to_source_file():
    n = make_node("a", "t", source_file="ZRDDS用户手册.pdf")
    assert n.source_name == "ZRDDS用户手册.pdf"
    assert n.source_id == "unknown"


def test_node_record_maps_page_range_start_variants():
    # A 的章节树产物使用 printed_page_start / physical_page_start（区间起点）
    n = make_node("a", "t", printed_page_start=13, physical_page_start=6)
    assert n.page_print == 13
    assert n.page_physical == 6


def test_load_nodes_reports_bad_json_with_line_number(tmp_path: Path):
    p = tmp_path / "nodes.jsonl"
    p.write_text('{"node_id": "a", "text": "ok"}\n{broken json}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="第 2 行"):
        load_nodes(p)


def test_sample_nodes_fixture_is_loadable_and_complete():
    fixture = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sample_nodes.jsonl"

    nodes = load_nodes(fixture)

    assert len(nodes) == 10
    for n in nodes:
        assert n.node_id
        assert n.text.strip()
        assert n.source_name != "unknown"
        assert n.section
        assert n.page_print is not None


def test_load_nodes_falls_back_to_top_level_chunk_id(tmp_path: Path):
    # A 的 struct_v1 产物顶层键是 chunk_id（无 node_id）——曾导致 301 条
    # 节点 ID 全空、建索引抛 DuplicateIDError。此测试锁死回退行为。
    p = tmp_path / "struct.jsonl"
    p.write_text(
        json.dumps(
            {"chunk_id": "struct_v1_c00001", "text": "内容A",
             "metadata": {"printed_page_start": 13, "physical_page_start": 6}},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    nodes = load_nodes(p)

    assert nodes[0].node_id == "struct_v1_c00001"


def test_load_nodes_node_id_takes_precedence_over_chunk_id(tmp_path: Path):
    p = tmp_path / "both.jsonl"
    p.write_text(
        json.dumps({"node_id": "n_top", "chunk_id": "c_top", "text": "t"}) + "\n",
        encoding="utf-8",
    )

    nodes = load_nodes(p)

    assert nodes[0].node_id == "n_top"


def test_load_nodes_falls_back_to_metadata_chunk_id(tmp_path: Path):
    p = tmp_path / "meta.jsonl"
    p.write_text(
        json.dumps({"text": "t", "metadata": {"chunk_id": "c_in_meta"}}) + "\n",
        encoding="utf-8",
    )

    nodes = load_nodes(p)

    assert nodes[0].node_id == "c_in_meta"


def test_real_struct_v1_artifact_loads_with_unique_nonempty_ids():
    # 直接对 A 的入库产物做契约校验：夹具与本文件其它用例的 schema 是
    # 「理想契约」，只有真实数据能暴露命名偏差。
    artifact = Path(__file__).resolve().parents[2] / "data" / "processed" / "struct_v1.jsonl"
    if not artifact.exists():
        pytest.skip("struct_v1.jsonl 未生成（先运行 make ingest）")

    nodes = load_nodes(artifact)

    assert nodes, "真实产物不应为空"
    ids = [n.node_id for n in nodes]
    assert all(ids), "存在空 node_id：顶层 ID 命名与 load_nodes 契约脱节"
    assert len(set(ids)) == len(ids), "真实产物存在重复 node_id"
    for n in nodes:
        assert n.page_print is not None and n.page_physical is not None


def test_real_struct_v1_artifact_builds_and_queries_index():
    # 复现周五验收路径（make index 的核心步骤）：真实产物 → Chroma 写入。
    # 曾在此抛 DuplicateIDError（全空 ID）。假向量注入，不依赖真实模型。
    artifact = Path(__file__).resolve().parents[2] / "data" / "processed" / "struct_v1.jsonl"
    if not artifact.exists():
        pytest.skip("struct_v1.jsonl 未生成（先运行 make ingest）")

    def embed(texts: list[str]) -> list[list[float]]:
        return [
            [((len(t) * 3 + i) % 11) / 11 + 0.1, ((len(t) + 5 * i) % 7) / 7 + 0.1]
            for i, t in enumerate(texts)
        ]

    nodes = load_nodes(artifact)
    store = VectorStore(
        embed_fn=embed, collection_name=f"real_probe_{uuid.uuid4().hex}"
    )
    store.add_nodes(nodes)

    assert store._collection.count() == len(nodes)
    results = store.query("如何创建 DataWriter？", top_k=5)
    assert len(results) == 5
    assert all(r["node_id"] for r in results)


# ---------------------------------------------------------------- 模型名解析


def test_resolve_model_maps_short_name_to_hf_repo(tmp_path, monkeypatch):
    # 干净环境（无 models/ 本地目录）时短名必须解析为 HF 全 repo id；
    # 曾原样透传 "bge-m3" 导致 make index 联网 401 失败。
    from retrieval import embeddings

    monkeypatch.setattr(embeddings, "MODEL_DIR", tmp_path)
    assert embeddings._resolve_model("bge-m3") == "BAAI/bge-m3"
    assert embeddings._resolve_model("some/other-model") == "some/other-model"


def test_resolve_model_prefers_local_dir(tmp_path, monkeypatch):
    from retrieval import embeddings

    (tmp_path / "bge-m3").mkdir()
    monkeypatch.setattr(embeddings, "MODEL_DIR", tmp_path)
    assert embeddings._resolve_model("bge-m3") == str(tmp_path / "bge-m3")


# ---------------------------------------------------------------- 向量库


def test_store_query_returns_results_sorted_by_score():
    store, _ = make_store()

    results = store.query("查询 alpha", top_k=3)

    assert [r["node_id"] for r in results] == ["n_alpha", "n_beta", "n_gamma"]
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["score"] > results[1]["score"]


def test_store_query_respects_top_k():
    store, _ = make_store()

    results = store.query("查询 alpha", top_k=2)

    assert len(results) == 2


def test_store_query_filters_by_metadata():
    store, vecs = make_store()
    store.add_nodes([
        make_node("n_v23", "旧版本正文", version="2.3"),
        make_node("n_v24", "新版本正文", version="2.4"),
    ])

    results = store.query("随便问", top_k=10, filters={"version": "2.4"})

    assert [r["node_id"] for r in results] == ["n_v24"]


def test_store_query_filter_matching_nothing_returns_empty():
    store, _ = make_store()
    store.add_nodes([make_node("n_v23", "旧版本正文", version="2.3")])

    results = store.query("查询 alpha", top_k=10, filters={"version": "9.9"})

    assert results == []


def test_store_query_on_empty_store_returns_empty_list():
    store = VectorStore(
        embed_fn=FakeEmbedder({}), collection_name=f"test_{uuid.uuid4().hex}"
    )

    assert store.query("问题", top_k=5) == []


def test_store_skips_blank_text_nodes():
    store, _ = make_store()
    store.add_nodes([make_node("n_blank", "   \n  ")])

    results = store.query("查询 alpha", top_k=10)

    assert all(r["node_id"] != "n_blank" for r in results)


def test_store_warns_only_when_store_ends_up_empty():
    import warnings

    store, _ = make_store()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        store.add_nodes([make_node("n_blank", "   ")])
    assert not [w for w in caught if issubclass(w.category, UserWarning)]

    empty = VectorStore(
        embed_fn=FakeEmbedder({}), collection_name=f"test_{uuid.uuid4().hex}"
    )
    with pytest.warns(UserWarning, match="空白"):
        empty.add_nodes([make_node("n_blank", "   ")])


def test_store_drops_non_primitive_metadata_values():
    """Chroma 只接受 str/int/float/bool 元数据；嵌套结构应被剥离而非崩溃。"""
    store = VectorStore(
        embed_fn=FakeEmbedder({"t": [1.0, 0.0, 0.0, 0.0]}),
        collection_name=f"test_{uuid.uuid4().hex}",
    )
    store.add_nodes([make_node("n", "t", nested={"a": 1}, keep="yes")])

    results = store.query("t", top_k=1)

    assert results[0]["metadata"] == {"keep": "yes"}


def test_store_rejects_unsupported_metric():
    with pytest.raises(ValueError, match="cosine"):
        VectorStore(embed_fn=FakeEmbedder({}), metric="l2")


# ---------------------------------------------------------------- Retriever 协议


def test_retriever_returns_source_ref_contract():
    store, _ = make_store()
    retriever = VectorRetriever(store)

    results = asyncio.run(retriever.retrieve("查询 alpha", top_k=3))

    assert len(results) == 3
    for r in results:
        assert set(r.keys()) == SOURCE_REF_KEYS
    assert results[0]["node_id"] == "n_alpha"
    assert results[0]["source_id"] == "user_manual"
    assert results[0]["source_name"] == "ZRDDS用户手册.pdf"
    assert results[0]["section"] == "3.4"
    assert results[0]["page_print"] == 42
    assert results[0]["page_physical"] == 36
    assert isinstance(results[0]["score"], float)


def test_retriever_honors_top_k_argument():
    store, _ = make_store()
    retriever = VectorRetriever(store)

    results = asyncio.run(retriever.retrieve("查询 alpha", top_k=1))

    assert len(results) == 1


def test_retriever_applies_filters_from_construction():
    store, _ = make_store()
    store.add_nodes([
        make_node("n_v23", "旧版本正文", version="2.3"),
        make_node("n_v24", "新版本正文", version="2.4"),
    ])
    retriever = VectorRetriever(store, filters={"version": "2.4"})

    results = asyncio.run(retriever.retrieve("查询", top_k=10))

    assert all(r["node_id"] != "n_v23" for r in results)


def test_retriever_missing_page_fields_become_none():
    store, _ = make_store()
    store.add_nodes([make_node("n_nopage", "无页码正文")])
    retriever = VectorRetriever(store)

    results = asyncio.run(retriever.retrieve("查询 alpha", top_k=10))

    hit = next(r for r in results if r["node_id"] == "n_nopage")
    assert hit["page_print"] is None
    assert hit["page_physical"] is None


# ---------------------------------------------------------------- 组装工厂


def _write_config(
    tmp_path: Path,
    embedding_provider: str = "local",
    api_key_env: str | None = None,
    index_backend: str = "chroma",
    retrieval_mode: str = "vector",
) -> Path:
    embed_block = f"""embedding:
  provider: {embedding_provider}
  model: bge-m3
"""
    if api_key_env:
        embed_block += f"  api_key_env: {api_key_env}\n"
    p = tmp_path / "baseline_v1.yaml"
    p.write_text(
        f"""
schema_version: 1
experiment:
  name: baseline_v1
  stage: baseline
sources:
  - id: user_manual
    type: pdf
    path: data/raw/manuals/ZRDDS用户手册.pdf
chunking:
  method: struct
  version: v1
{embed_block}index:
  backend: {index_backend}
retrieval:
  mode: {retrieval_mode}
  top_k: 5
""".strip() + "\n",
        encoding="utf-8",
    )
    return p


def test_resolve_model_prefers_local_model_dir(tmp_path, monkeypatch):
    from retrieval import embeddings

    monkeypatch.setattr(embeddings, "MODEL_DIR", tmp_path)
    (tmp_path / "bge-m3").mkdir()

    assert embeddings._resolve_model("bge-m3") == str(tmp_path / "bge-m3")
    assert embeddings._resolve_model("不存在模型") == "不存在模型"


def test_build_embedding_api_provider_not_implemented_yet(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(
        _write_config(tmp_path, embedding_provider="api", api_key_env="EMBED_API_KEY")
    )

    with pytest.raises(NotImplementedError, match="local"):
        build_embedding(cfg)


def test_build_embedding_local_is_lazy_and_callable(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    embed_fn = build_embedding(cfg)

    # 构造阶段不加载模型（模型下载/加载推迟到首次调用）
    assert callable(embed_fn)


def test_build_retriever_raises_clear_error_when_index_missing(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    with pytest.raises(FileNotFoundError, match="build_index"):
        build_retriever(cfg, embed_fn=FakeEmbedder({}))


def test_build_index_writes_index_dir_and_is_queryable(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    nodes_file = experiment_config.nodes_path(cfg)
    nodes_file.parent.mkdir(parents=True, exist_ok=True)
    nodes_file.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in [
            {"node_id": "n1", "text": "t1", "metadata": {"source_id": "user_manual",
             "source_name": "ZRDDS用户手册.pdf", "section": "1.1"}},
            {"node_id": "n2", "text": "t2", "metadata": {"source_id": "user_manual",
             "source_name": "ZRDDS用户手册.pdf", "section": "2.2"}},
        ]) + "\n",
        encoding="utf-8",
    )
    vecs = {"t1": [1.0, 0.0, 0.0, 0.0], "t2": [0.0, 1.0, 0.0, 0.0],
            "问 t1": [1.0, 0.0, 0.0, 0.0]}
    fake = FakeEmbedder(vecs)

    index_path = build_index(cfg, embed_fn=fake)

    assert index_path.exists()
    retriever = build_retriever(cfg, embed_fn=fake)
    results = asyncio.run(retriever.retrieve("问 t1", top_k=5))
    assert results[0]["node_id"] == "n1"


def test_build_index_rejects_unsupported_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path, index_backend="faiss"))
    nodes_file = experiment_config.nodes_path(cfg)
    nodes_file.parent.mkdir(parents=True, exist_ok=True)
    nodes_file.write_text(
        json.dumps({"node_id": "n1", "text": "t1", "metadata": {}}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(NotImplementedError, match="chroma"):
        build_index(cfg, embed_fn=FakeEmbedder({}))


def test_build_retriever_rejects_unsupported_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path, retrieval_mode="bm25"))
    index_path = experiment_config.index_dir(cfg)
    index_path.mkdir(parents=True, exist_ok=True)

    with pytest.raises(NotImplementedError, match="vector"):
        build_retriever(cfg, embed_fn=FakeEmbedder({}))


def test_sanitize_collection_name_replaces_invalid_chars():
    from retrieval.vector_store import sanitize_collection_name

    assert sanitize_collection_name("struct_BAAI/bge-m3_ab12cd34") == "struct_BAAI_bge-m3_ab12cd34"


def test_build_index_rebuild_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    nodes_file = experiment_config.nodes_path(cfg)
    nodes_file.parent.mkdir(parents=True, exist_ok=True)
    nodes_file.write_text(
        json.dumps({"node_id": "n1", "text": "t1", "metadata": {}}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    fake = FakeEmbedder({"t1": [1.0, 0.0, 0.0, 0.0], "问 t1": [1.0, 0.0, 0.0, 0.0]})

    build_index(cfg, embed_fn=fake)
    build_index(cfg, embed_fn=fake)  # 同配置重复重建：覆盖而非追加

    retriever = build_retriever(cfg, embed_fn=fake)
    results = asyncio.run(retriever.retrieve("问 t1", top_k=5))
    assert len(results) == 1


def test_build_index_raises_clear_error_when_nodes_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    with pytest.raises(FileNotFoundError, match="ingest"):
        build_index(cfg, embed_fn=FakeEmbedder({}))


def test_cli_build_and_query_roundtrip(tmp_path, monkeypatch, capsys):
    import retrieval.cli as cli

    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    nodes_file = experiment_config.nodes_path(cfg)
    nodes_file.parent.mkdir(parents=True, exist_ok=True)
    nodes_file.write_text(
        json.dumps({"node_id": "n1", "text": "t1", "metadata": {
            "source_id": "user_manual", "source_name": "ZRDDS用户手册.pdf",
            "section": "1.1", "page_print": 13, "page_physical": 6}},
            ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    vecs = {"t1": [1.0, 0.0, 0.0, 0.0], "问 t1": [1.0, 0.0, 0.0, 0.0]}
    fake = FakeEmbedder(vecs)
    cfg_path = str(tmp_path / "baseline_v1.yaml")

    assert cli.main(["build", "--config", cfg_path], embed_fn=fake) == 0
    out = capsys.readouterr().out
    assert "索引已就绪" in out

    assert (
        cli.main(
            ["query", "--config", cfg_path, "--question", "问 t1", "--top-k", "3"],
            embed_fn=fake,
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "n1" in out
    assert "ZRDDS用户手册.pdf" in out


def test_cli_query_rejects_top_k_below_one(tmp_path, monkeypatch):
    import retrieval.cli as cli

    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg_path = str(_write_config(tmp_path))

    with pytest.raises(SystemExit):
        cli.main(
            ["query", "--config", cfg_path, "--question", "q", "--top-k", "0"],
            embed_fn=FakeEmbedder({}),
        )


def test_build_retriever_loads_persisted_index(tmp_path, monkeypatch):
    import experiment_config
    monkeypatch.setattr(experiment_config, "REPO_ROOT", tmp_path)
    cfg = experiment_config.load(_write_config(tmp_path))

    vecs = {"t": [1.0, 0.0, 0.0, 0.0], "查询": [1.0, 0.0, 0.0, 0.0]}
    fake = FakeEmbedder(vecs)
    store = VectorStore(
        embed_fn=fake,
        persist_path=str(experiment_config.index_dir(cfg)),
        collection_name=experiment_config.index_dirname(cfg),
    )
    store.add_nodes([make_node("n_persisted", "t",
                               source_id="user_manual",
                               source_name="ZRDDS用户手册.pdf", section="1.1")])

    retriever = build_retriever(cfg, embed_fn=fake)

    results = asyncio.run(retriever.retrieve("查询", top_k=5))
    assert results[0]["node_id"] == "n_persisted"
