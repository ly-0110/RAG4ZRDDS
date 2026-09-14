"""W1 处置（方案 B）：`/sources/{rid}` 回查记录附带 source_url，SSE wire 不变。

背景见 docs/week4-delivery-review.md §2.3：`source_url` 在 Node 产物里存在，但
SourceRef 七字段投影把它丢了，前端拿不到 HTML 原文 URL。扩 wire 字段需 B/C/E 会签，
在此之前由 D 在回查通路补齐。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from server.core.pipeline import Pipeline, _load_source_urls
from server.core.settings import Settings
from server.main import create_app


def _mock_settings(tmp_path) -> Settings:
    return Settings(rag_mode="mock", log_dir=str(tmp_path), cors_origins="*")


class TestNodeUrlIndex:
    def test_reads_chunk_id_to_url_and_tolerates_gaps(self, tmp_path):
        nodes = tmp_path / "nodes.jsonl"
        rows = [
            {"chunk_id": "html_a", "source_url": "https://docs.example/a.html",
             "metadata": {"source_id": "zrdds_dev_guide"}},
            {"chunk_id": "pdf_b", "source_url": None,
             "metadata": {"source_id": "user_manual"}},
            {"metadata": {"chunk_id": "html_c", "source_url": "https://docs.example/c.html"}},
            "坏行不是 json{{{",
            {"metadata": {"source_id": "user_manual"}},          # 无 id，跳过
        ]
        nodes.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                   if isinstance(r, dict) else r for r in rows),
                         encoding="utf-8")
        urls = _load_source_urls(nodes)
        assert urls["html_a"] == "https://docs.example/a.html"
        assert urls["pdf_b"] is None                      # PDF 块保留键、值为 null
        assert urls["html_c"] == "https://docs.example/c.html"   # metadata.chunk_id 回退
        assert len(urls) == 3

    def test_missing_file_gives_empty_map(self, tmp_path):
        assert _load_source_urls(tmp_path / "nope.jsonl") == {}

    def test_pipeline_default_map_is_empty(self):
        class _R:
            pass

        assert Pipeline(_R(), _R()).source_urls == {}      # 不传也不能报错


class TestBackfillOnlyOnLookup:
    def _rid_and_nodes(self, client: TestClient) -> tuple[str, list[str]]:
        resp = client.post("/query", json={"question": "简化接口怎么用？"})
        assert resp.status_code == 200
        resp.text
        rid = resp.headers["X-Request-ID"]
        nodes = [s["node_id"] for s in client.get(f"/sources/{rid}").json()["sources"]]
        return rid, nodes

    def test_lookup_carries_url_and_sse_does_not(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        _, nodes = self._rid_and_nodes(client)            # 先拿到 mock 的确定性 node_id
        url = "https://docs.zrtechnology.com/cdoc/html/group___c_publication.html"
        client.app.state.pipeline.source_urls = {nodes[0]: url}

        resp = client.post("/query", json={"question": "简化接口怎么用？"})
        body = resp.text
        assert resp.status_code == 200
        rid = resp.headers["X-Request-ID"]

        # ① wire：SSE 帧里不得出现 source_url（前端契约未会签扩字段）
        assert "source_url" not in body

        # ② 回查：第一条带 URL，其余为 null（形状稳定，前端可无条件读键）
        sources = client.get(f"/sources/{rid}").json()["sources"]
        assert sources[0]["source_url"] == url
        assert all("source_url" in s for s in sources)
        assert sources[1]["source_url"] is None

    def test_persisted_jsonl_contains_url(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        _, nodes = self._rid_and_nodes(client)
        client.app.state.pipeline.source_urls = {nodes[1]: "https://example/one.html"}
        resp = client.post("/query", json={"question": "简化接口怎么用？"})
        rid = resp.headers["X-Request-ID"]

        lines = (tmp_path / "sources.jsonl").read_text(encoding="utf-8").splitlines()
        mine = [json.loads(x) for x in lines if x.strip()][-1]
        assert mine["request_id"] == rid
        assert mine["record"]["sources"][1]["source_url"] == "https://example/one.html"

    def test_unknown_nodes_get_null_url(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        resp = client.post("/query", json={"question": "简化接口怎么用？"})
        rid = resp.headers["X-Request-ID"]
        sources = client.get(f"/sources/{rid}").json()["sources"]
        assert all(s["source_url"] is None for s in sources)   # 未装载 URL 表也不报错
