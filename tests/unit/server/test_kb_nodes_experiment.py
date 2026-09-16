"""F1/F3/F4 后端三件（2026-09-15 前端实测问题，review §4.1）的 D 侧落地：

  F1 知识库状态数据源 = /healthz 附 kb 统计 + experiments 白名单
  F3 节点原文        = GET /nodes/{node_id}（回查通道按需出网；SSE wire 仍 7 字段）
  F4 通路切换        = /query 可选 experiment（白名单校验 + registry 懒组装缓存）

mock 用例不依赖真实产物；live 用例以假管线替换 build_pipeline，不触碰
bge-m3 / 索引 / LLM。
"""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from server.core.pipeline import Pipeline, PipelineRegistry, load_nodes_artifacts
from server.core.settings import Settings
from server.main import create_app


def _mock_settings(tmp_path) -> Settings:
    return Settings(rag_mode="mock", log_dir=str(tmp_path), cors_origins="*")


def _live_settings(tmp_path) -> Settings:
    return Settings(rag_mode="live", log_dir=str(tmp_path), cors_origins="*")


class _FakeRetriever:
    """可计数、可 close 的假检索器（registry 逐出测试记录 close 调用）。"""

    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    async def retrieve(self, question: str, top_k: int) -> list[dict]:
        self.calls += 1
        return [{
            "node_id": "n1", "source_id": "user_manual", "source_name": "手册.pdf",
            "section": "9.1", "page_print": 54, "page_physical": 60, "score": 0.9,
            "text": "fake chunk text",
        }]

    def close(self) -> None:
        self.closed = True


class _FakeAnswer:
    async def stream(self, question: str, chunks: list[dict]):
        yield "ok"


_FAKE_KB = {
    "experiment": "struct_v1",
    "retrieval_mode": "vector",
    "index_dirname": "struct_bge-m3_deadbeef",
    "node_total": 1,
    "top_k": 5,
    "sources": [{"id": "user_manual", "version": "2.0", "chunks": 1}],
}

_FAKE_DETAILS = {
    "n1": {
        "source_id": "user_manual", "version": "2.0",
        "page_print": 54, "page_physical": 60,
        "section_path": ["9", "9.1"], "text": "节点原文内容", "source_url": None,
    }
}


def _fake_build(builds: list):
    def _build(mode: str, experiment_config: str | None = None) -> Pipeline:
        builds.append(experiment_config)
        return Pipeline(_FakeRetriever(), _FakeAnswer(), {},
                        node_details=dict(_FAKE_DETAILS), kb_stats=dict(_FAKE_KB))
    return _build


# ---------------------------------------------------------------- loader

class TestLoadNodesArtifacts:
    def _write(self, tmp_path, rows) -> object:
        nodes = tmp_path / "nodes.jsonl"
        nodes.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else r
                      for r in rows),
            encoding="utf-8")
        return nodes

    def test_one_pass_yields_urls_details_and_source_stats(self, tmp_path):
        # 字段名以 A 的 metadata 契约为准（printed/physical_page_start|end）；
        # HTML 行的页字段是字面量字符串 "None"（产物真实形态）。
        nodes = self._write(tmp_path, [
            {"chunk_id": "a1", "text": "手册正文", "source_url": None,
             "metadata": {"source_id": "user_manual", "version": "2.0", "source_type": "pdf",
                          "source_file": "ZRDDS用户手册.pdf", "title": "9.1 概述",
                          "printed_page_start": 54, "printed_page_end": 55,
                          "physical_page_start": 60, "physical_page_end": 61,
                          "section_path": ["9", "9.1"]}},
            {"chunk_id": "h1", "text": "HTML 正文", "source_url": "https://x/h.html",
             "metadata": {"source_id": "zrdds_dev_guide", "version": "2.4", "source_type": "html",
                          "source_file": "group___x.html", "title": "DDS_Writer",
                          "printed_page_start": "None", "printed_page_end": "None",
                          "physical_page_start": "None", "physical_page_end": "None",
                          "section_path": ["group__x", "DDS_Writer"]}},
            "坏行不是 json{{{",
            {"metadata": {"source_id": "user_manual"}},  # 无 chunk_id，跳过
        ])
        urls, details, stats = load_nodes_artifacts(nodes)
        assert urls == {"a1": None, "h1": "https://x/h.html"}
        assert details["a1"]["text"] == "手册正文"
        # 真实字段名 → 详情表（修复前读 page_print 恒为空）
        assert details["a1"]["page_print"] == 54 and details["a1"]["page_print_end"] == 55
        assert details["a1"]["page_physical"] == 60 and details["a1"]["page_physical_end"] == 61
        assert details["a1"]["source_type"] == "pdf"
        assert details["a1"]["source_file"] == "ZRDDS用户手册.pdf"
        # HTML：字符串 "None" 归一为 None，并带来源格式信息
        assert details["h1"]["page_print"] is None and details["h1"]["page_physical"] is None
        assert details["h1"]["source_type"] == "html"
        assert details["h1"]["source_file"] == "group___x.html"
        assert details["h1"]["source_url"] == "https://x/h.html"
        assert stats == [
            {"id": "user_manual", "version": "2.0", "chunks": 1},
            {"id": "zrdds_dev_guide", "version": "2.4", "chunks": 1},
        ]

    def test_missing_file_yields_empty_artifacts(self, tmp_path):
        urls, details, stats = load_nodes_artifacts(tmp_path / "nope.jsonl")
        assert urls == {} and details == {} and stats == []


# ---------------------------------------------------------------- F1 /healthz

class TestHealthzKb:
    def test_mock_kb_is_null_but_experiments_listed(self, tmp_path):
        body = TestClient(create_app(_mock_settings(tmp_path))).get("/healthz").json()
        assert body["status"] == "ok" and body["mode"] == "mock"
        assert body["kb"] is None
        assert isinstance(body["experiments"], list) and "struct_v1" in body["experiments"]

    def test_live_reports_kb_stats(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        client = TestClient(create_app(_live_settings(tmp_path)))
        body = client.get("/healthz").json()
        assert body["mode"] == "live"
        assert body["kb"]["node_total"] == 1
        assert body["kb"]["index_dirname"] == "struct_bge-m3_deadbeef"
        assert body["kb"]["top_k"] == 5
        assert body["kb"]["sources"][0] == {"id": "user_manual", "version": "2.0", "chunks": 1}


# ---------------------------------------------------------------- F3 /nodes

class TestNodesEndpoint:
    def test_live_returns_node_detail(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        client = TestClient(create_app(_live_settings(tmp_path)))
        r = client.get("/nodes/n1")
        assert r.status_code == 200
        body = r.json()
        assert body["node_id"] == "n1"
        assert body["text"] == "节点原文内容"
        assert body["section_path"] == ["9", "9.1"]
        assert body["page_print"] == 54 and body["page_physical"] == 60

    def test_unknown_id_404_names_experiment(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        client = TestClient(create_app(_live_settings(tmp_path)))
        r = client.get("/nodes/nope")
        assert r.status_code == 404
        assert "nope" in r.json()["error"]

    def test_mock_404_explains_mode(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        r = client.get("/nodes/whatever")
        assert r.status_code == 404
        assert "mock" in r.json()["error"]


# ---------------------------------------------------------------- F4 /query experiment

class TestQueryExperiment:
    def test_unknown_experiment_422_lists_available(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        client = TestClient(create_app(_live_settings(tmp_path)))
        r = client.post("/query", json={"question": "q", "experiment": "nope"})
        assert r.status_code == 422
        assert "nope" in r.json()["error"] and "struct_v1" in r.json()["error"]

    def test_known_experiment_builds_once_then_cache_hits(self, tmp_path, monkeypatch):
        builds: list = []
        monkeypatch.setattr("server.main.build_pipeline", _fake_build(builds))
        monkeypatch.setattr("server.core.pipeline.build_pipeline", _fake_build(builds))
        client = TestClient(create_app(_live_settings(tmp_path)))
        for _ in range(2):
            r = client.post("/query", json={"question": "q", "experiment": "semantic_v1"})
            assert r.status_code == 200
            assert "error" not in r.text
        # builds[0] = 启动装配（create_app），其后仅切换实验组装一次，第二次走缓存
        assert builds == ["configs/experiments/struct_v1.yaml",
                          "configs/experiments/semantic_v1.yaml"]
        # 响应确实来自该实验的假检索器（node_id n1）
        rid = r.headers["X-Request-ID"]
        sources = client.get(f"/sources/{rid}").json()["sources"]
        assert sources[0]["node_id"] == "n1"

    def test_mock_ignores_experiment(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        r = client.post("/query", json={"question": "q", "experiment": "whatever"})
        assert r.status_code == 200
        assert "event: done" in r.text


# ---------------------------------------------------------------- PipelineRegistry

class TestPipelineRegistry:
    def _pipe(self) -> Pipeline:
        return Pipeline(_FakeRetriever(), _FakeAnswer())

    def _make(self, max_size=3) -> tuple[PipelineRegistry, list[Pipeline]]:
        default = self._pipe()
        reg = PipelineRegistry("d", default, max_size=max_size)
        return reg, [default]

    def test_get_or_build_caches(self, monkeypatch):
        builds: list = []

        def _build(mode, experiment_config=None):
            builds.append(experiment_config)
            return self._pipe()

        monkeypatch.setattr("server.core.pipeline.build_pipeline", _build)
        reg, _ = self._make()
        p1 = asyncio.run(reg.get_or_build("a", "configs/experiments/a.yaml"))
        p2 = asyncio.run(reg.get_or_build("a", "configs/experiments/a.yaml"))
        assert p1 is p2 and builds == ["configs/experiments/a.yaml"]

    def test_concurrent_get_or_build_builds_once(self, monkeypatch):
        builds: list = []

        def _build(mode, experiment_config=None):
            builds.append(experiment_config)
            return self._pipe()

        monkeypatch.setattr("server.core.pipeline.build_pipeline", _build)
        reg, _ = self._make()
        async def go():
            return await asyncio.gather(*(reg.get_or_build("a", "a.yaml") for _ in range(3)))
        ps = asyncio.run(go())
        assert len({id(p) for p in ps}) == 1 and len(builds) == 1

    def test_lru_evicts_oldest_non_default_and_closes(self):
        reg, pipes = self._make(max_size=3)
        p1, p2, p3 = self._pipe(), self._pipe(), self._pipe()
        reg.put("p1", p1); reg.put("p2", p2)          # d, p1, p2
        reg.put("p3", p3)                               # 超 3 → 逐出最旧的非默认 p1
        assert "p1" not in reg and p1.retriever.closed is True
        assert "d" in reg and "p2" in reg and "p3" in reg
        assert reg.get("p2") is p2

    def test_default_pinned_when_over_capacity(self):
        reg, _ = self._make(max_size=1)
        reg.put("x", self._pipe())
        assert "d" in reg and "x" in reg  # 默认钉住：超容量也不逐出默认管线

    def test_get_refreshes_recency(self):
        reg, _ = self._make(max_size=3)
        p1, p2 = self._pipe(), self._pipe()
        reg.put("p1", p1); reg.put("p2", p2)
        assert reg.get("p1") is p1                        # p1 变为最近使用
        reg.put("p3", self._pipe())                      # 逐出对象应为 p2 而非 p1
        assert "p1" in reg and "p2" not in reg


# ------------------------------------------- F3 × F4：节点详情跨实验按需装载

class TestNodeDetailIndex:
    """2026-09-16 整合缺陷回归：F4 切到其它实验后，F3 的 /nodes 必须仍可查。

    变更前只有默认实验的详情表，切换实验后拿到的 node_id 一律 404
    （两个功能各自可用、合起来不可用——本机实测复现）。
    """

    def _index(self, monkeypatch, tables: dict[str, dict], calls: list):
        from server.core.pipeline import NodeDetailIndex

        def _load(key):
            calls.append(key)
            return tables.get(key)

        idx = NodeDetailIndex("struct_v1", dict(_FAKE_DETAILS),
                              ["struct_v1", "struct_multisrc_v1", "struct_bm25"])
        monkeypatch.setattr(idx, "_load", _load)
        return idx

    def test_hit_in_default_table_does_not_load_others(self, monkeypatch):
        calls: list = []
        idx = self._index(monkeypatch, {}, calls)
        assert idx.lookup("n1")[0] == "struct_v1"
        assert calls == []  # 默认表命中，不触发任何装载

    def test_lazily_loads_other_experiment_and_caches(self, monkeypatch):
        calls: list = []
        html_node = {"source_id": "zrdds_dev_guide", "text": "HTML 节点",
                     "page_print": None, "page_physical": None}
        idx = self._index(monkeypatch, {"struct_multisrc_v1": {"h1": html_node}}, calls)
        found = idx.lookup("h1")
        assert found is not None and found[0] == "struct_multisrc_v1"
        assert found[1]["text"] == "HTML 节点"
        assert calls == ["struct_multisrc_v1"]          # 首次装载
        assert idx.lookup("h1")[0] == "struct_multisrc_v1"
        assert calls == ["struct_multisrc_v1"]          # 第二次命中缓存不再装载

    def test_unknown_node_returns_none_and_marks_failures(self, monkeypatch):
        calls: list = []

        def _load(key):
            calls.append(key)
            raise FileNotFoundError(f"no artifact for {key}")

        from server.core.pipeline import NodeDetailIndex

        idx = NodeDetailIndex("struct_v1", dict(_FAKE_DETAILS), ["struct_v1", "semantic_v1"])
        monkeypatch.setattr(idx, "_load", _load)
        assert idx.lookup("nope") is None
        assert idx.lookup("nope") is None
        assert calls == ["semantic_v1"]  # 失败只尝试一次，不逐请求重试

    def test_table_cache_evicts_non_default(self, monkeypatch):
        from server.core.pipeline import NodeDetailIndex

        idx = NodeDetailIndex("struct_v1", {}, ["struct_v1", "a", "b", "c"], max_tables=2)
        monkeypatch.setattr(idx, "_load", lambda key: {f"{key}_n": {"text": key}})
        idx.lookup("a_n")
        idx.lookup("b_n")
        assert set(idx.loaded_experiments) == {"struct_v1", "b"}  # a 被逐出


class TestNodesEndpointAcrossExperiments:
    def test_node_from_other_experiment_is_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        app = create_app(_live_settings(tmp_path))
        idx = app.state.node_detail_index
        monkeypatch.setattr(idx, "_load",
                            lambda key: {"h1": {"source_id": "zrdds_dev_guide",
                                                "text": "跨实验节点原文"}}
                            if key == "struct_multisrc_v1" else None)
        client = TestClient(app)
        r = client.get("/nodes/h1")
        assert r.status_code == 200
        body = r.json()
        assert body["experiment"] == "struct_multisrc_v1"
        assert body["text"] == "跨实验节点原文"

    def test_default_experiment_node_still_reported_with_experiment(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        client = TestClient(create_app(_live_settings(tmp_path)))
        body = client.get("/nodes/n1").json()
        assert body["experiment"] == "struct_v1"
        assert body["text"] == "节点原文内容"


# ------------------------------------- v0.16：本地文档服务（打开 HTML 原文可用）

class TestLocalizeDocUrls:
    """产物里的 source_url 指向占位外部域名（不可达）→ 改写成本服务地址。"""

    def _roots(self, tmp_path):
        root = tmp_path / "cdoc_html"
        root.mkdir()
        (root / "group___x.html").write_text("<html>原文</html>", encoding="utf-8")
        return {"zrdds_dev_guide": root}

    def test_rewrites_only_existing_files(self, tmp_path):
        from server.core.pipeline import _localize_doc_urls

        urls = {
            "h1": "https://docs.zrtechnology.com/cdoc/html/group___x.html",
            "h2": "https://docs.zrtechnology.com/cdoc/html/missing.html",
        }
        details = {
            "h1": {"source_id": "zrdds_dev_guide", "source_file": "group___x.html",
                   "source_url": urls["h1"]},
            "h2": {"source_id": "zrdds_dev_guide", "source_file": "missing.html",
                   "source_url": urls["h2"]},
        }
        changed = _localize_doc_urls(urls, details, self._roots(tmp_path))
        assert changed == 1
        assert urls["h1"] == "/documents/zrdds_dev_guide/group___x.html"
        assert details["h1"]["source_url"] == "/documents/zrdds_dev_guide/group___x.html"
        # 文件不存在 → 保留原值，不把"打不开"换成"404"
        assert urls["h2"] == "https://docs.zrtechnology.com/cdoc/html/missing.html"

    def test_skips_unregistered_source_and_no_roots(self, tmp_path):
        from server.core.pipeline import _localize_doc_urls

        urls = {"p1": "https://x/y.pdf"}
        details = {"p1": {"source_id": "user_manual", "source_file": "y.pdf"}}
        assert _localize_doc_urls(urls, details, self._roots(tmp_path)) == 0
        assert urls["p1"] == "https://x/y.pdf"

    def test_falls_back_to_url_basename_without_source_file(self, tmp_path):
        from server.core.pipeline import _localize_doc_urls

        urls = {"h1": "https://docs.zrtechnology.com/cdoc/html/group___x.html"}
        details = {"h1": {"source_id": "zrdds_dev_guide"}}
        assert _localize_doc_urls(urls, details, self._roots(tmp_path)) == 1
        assert urls["h1"] == "/documents/zrdds_dev_guide/group___x.html"


class TestDocumentsEndpoint:
    def _client(self, tmp_path, monkeypatch, filename="group___x.html"):
        root = tmp_path / "cdoc_html"
        root.mkdir(exist_ok=True)
        (root / filename).write_text("<html>原文</html>", encoding="utf-8")
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        app = create_app(_live_settings(tmp_path))
        # 端点以 app.state.source_roots 为准（启动期从全部实验配置合并）
        app.state.source_roots = {"zrdds_dev_guide": root}
        return TestClient(app)

    def test_serves_registered_document(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        r = client.get("/documents/zrdds_dev_guide/group___x.html")
        assert r.status_code == 200
        assert "原文" in r.text

    def test_rejects_path_traversal(self, tmp_path, monkeypatch):
        """穿越尝试一律被拒（含分隔符的路径在路由层就不匹配 → 404；
        单段但含 .. 的由端点判定 → 400）。两种都是拒绝，且不返回任何内容。"""
        (tmp_path / "secret.txt").write_text("不该被读到", encoding="utf-8")
        client = self._client(tmp_path, monkeypatch)
        for bad in ["..%2Fsecret.txt", "%2Fetc%2Fpasswd", "..", "."]:
            r = client.get(f"/documents/zrdds_dev_guide/{bad}")
            assert r.status_code in (400, 404), (bad, r.status_code)
            assert "不该被读到" not in r.text

    def test_unknown_source_and_missing_file_are_404(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        assert client.get("/documents/nope/group___x.html").status_code == 404
        assert client.get("/documents/zrdds_dev_guide/missing.html").status_code == 404

    def test_no_registered_roots_explains(self, tmp_path, monkeypatch):
        """未登记目录时给可读说明（mock 也走同一白名单——链接可用性与模式无关）。"""
        monkeypatch.setattr("server.main.available_source_roots", lambda *a, **k: {})
        client = TestClient(create_app(_mock_settings(tmp_path)))
        r = client.get("/documents/zrdds_dev_guide/group___x.html")
        assert r.status_code == 404
        assert "本地文档目录" in r.json()["error"]


class TestExperimentModes:
    def test_real_configs_report_mode_per_experiment(self):
        from server.core.pipeline import experiment_modes

        modes = experiment_modes()
        assert modes.get("struct_v1") == "vector"
        assert modes.get("struct_bm25") == "bm25"
        assert modes.get("struct_hybrid") == "hybrid"
        assert modes.get("final_v1") == "vector"  # 多来源终跑

    def test_healthz_carries_modes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("server.main.build_pipeline", _fake_build([]))
        body = TestClient(create_app(_live_settings(tmp_path))).get("/healthz").json()
        assert body["experiment_modes"].get("struct_bm25") == "bm25"


class TestSourceRootsFromConfig:
    """sources 元素是 SourceCfg 对象（不是 dict）——只按 dict 取值会让本地化静默失效。"""

    def test_accepts_config_objects(self, tmp_path):
        from types import SimpleNamespace

        from server.core.pipeline import _resolve_source_roots

        html_root = tmp_path / "cdoc_html"
        html_root.mkdir()
        sources = [
            SimpleNamespace(id="zrdds_dev_guide", path=str(html_root)),
            SimpleNamespace(id="user_manual", path=str(tmp_path / "manual.pdf")),  # 文件，非目录
        ]
        roots = _resolve_source_roots(tmp_path, sources)
        assert roots == {"zrdds_dev_guide": html_root.resolve()}

    def test_accepts_dicts_too(self, tmp_path):
        from server.core.pipeline import _resolve_source_roots

        html_root = tmp_path / "docs"
        html_root.mkdir()
        assert _resolve_source_roots(tmp_path, [{"id": "d", "path": str(html_root)}]) == {
            "d": html_root.resolve()}

    def test_missing_or_unset_path_skipped(self, tmp_path):
        from types import SimpleNamespace

        from server.core.pipeline import _resolve_source_roots

        sources = [SimpleNamespace(id="a", path=None), SimpleNamespace(id=None, path="x"),
                   SimpleNamespace(id="gone", path=str(tmp_path / "nope"))]
        assert _resolve_source_roots(tmp_path, sources) == {}
