"""POST /feedback 反馈落库测试。

一律 mock 管线 + tmp_path 日志目录：只验契约与落盘，不依赖检索/生成实现。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from server.core.settings import Settings
from server.main import create_app


def _mock_settings(tmp_path) -> Settings:
    return Settings(rag_mode="mock", log_dir=str(tmp_path), cors_origins="*")


def _answered_rid(client: TestClient) -> tuple[str, list[str]]:
    """走一次 /query 拿到真实落盘的 request_id 与其引用 node_id 列表。"""
    resp = client.post("/query", json={"question": "简化接口怎么用？"})
    assert resp.status_code == 200
    resp.text                                        # 读完流，确保 done 后落盘执行
    rid = resp.headers["X-Request-ID"]
    record = client.get(f"/sources/{rid}").json()
    return rid, [s["node_id"] for s in record["sources"]]


def _feedback_lines(tmp_path) -> list[dict]:
    path = tmp_path / "feedback.jsonl"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


class TestFeedbackHappyPath:
    def test_upvote_records_one_line_with_attribution(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        rid, nodes = _answered_rid(client)

        resp = client.post("/feedback", json={"request_id": rid, "rating": "up"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "recorded" and body["request_id"] == rid
        assert body["rating"] == "up" and body["feedback_id"]

        rows = _feedback_lines(tmp_path)
        assert len(rows) == 1
        row = rows[0]
        assert row["request_id"] == rid and row["rating"] == "up"
        assert row["question"] == "简化接口怎么用？"          # 可归因到具体问题
        assert row["answer_present"] is True
        assert row["cited_nodes"] == len(nodes)
        assert row["ts"]
        assert "answer" not in row, "答案正文已在 sources.jsonl，反馈记录不得重复落盘"

    def test_comment_and_valid_node_ids_are_persisted(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        rid, nodes = _answered_rid(client)

        resp = client.post("/feedback", json={
            "request_id": rid, "rating": "down",
            "comment": "第 2 条引用与问题无关", "node_ids": nodes[:1]})
        assert resp.status_code == 201, resp.text
        row = _feedback_lines(tmp_path)[-1]
        assert row["rating"] == "down" and row["comment"] == "第 2 条引用与问题无关"
        assert row["node_ids"] == nodes[:1]

    def test_request_level_log_covers_feedback_call(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        rid, _ = _answered_rid(client)
        assert client.post("/feedback", json={"request_id": rid, "rating": "down"}).status_code == 201

        reqs = [json.loads(x) for x in
                (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
        posts = [r for r in reqs if r["path"] == "/feedback"]
        assert posts and posts[-1]["status"] == 201 and posts[-1]["method"] == "POST"


class TestFeedbackRejectsUnattributable:
    def test_unknown_request_id_rejected_404(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        resp = client.post("/feedback", json={"request_id": "deadbeef12ab", "rating": "up"})
        assert resp.status_code == 404
        assert "无法归因" in resp.json()["error"]
        assert _feedback_lines(tmp_path) == [], "被拒的反馈不得留下孤儿记录"

    def test_node_ids_outside_the_answer_rejected_400(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        rid, _ = _answered_rid(client)
        resp = client.post("/feedback", json={
            "request_id": rid, "rating": "down", "node_ids": ["not_in_this_answer"]})
        assert resp.status_code == 400
        err = resp.json()["error"]
        assert "not_in_this_answer" in err and "不属于该次引用" in err
        assert _feedback_lines(tmp_path) == []

    def test_rating_enum_enforced(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        rid, _ = _answered_rid(client)
        resp = client.post("/feedback", json={"request_id": rid, "rating": "meh"})
        assert resp.status_code == 422
        assert "不合法" in resp.json()["error"]
        assert _feedback_lines(tmp_path) == []

    def test_missing_request_id_rejected(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        resp = client.post("/feedback", json={"rating": "up"})
        assert resp.status_code == 422
