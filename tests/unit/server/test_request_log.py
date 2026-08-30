"""三级日志设施骨架（server/core/request_log.py）测试。

覆盖：
  1. JsonlLog 追加与自动建目录；
  2. PersistentSourcesStore 持久化、重启恢复、容量窗口、坏行容忍；
  3. TestClient 端到端：请求级日志落盘 + /sources 跨"服务重启"可回查。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from server.core.request_log import JsonlLog, PersistentSourcesStore
from server.core.settings import Settings
from server.main import create_app


class TestJsonlLog:
    def test_append_creates_parent_and_writes_json(self, tmp_path):
        log = JsonlLog(tmp_path / "sub" / "requests.jsonl")
        log.append({"request_id": "abc", "status": 200})
        lines = (tmp_path / "sub" / "requests.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["request_id"] == "abc"
        assert rec["status"] == 200
        assert "ts" in rec


class TestPersistentSourcesStore:
    def test_put_get_roundtrip(self, tmp_path):
        store = PersistentSourcesStore(tmp_path / "s.jsonl", capacity=10)
        store.put("rid1", {"question": "q", "sources": []})
        assert store.get("rid1") == {"question": "q", "sources": []}
        assert store.get("nope") is None

    def test_survives_restart_by_hydrating_from_file(self, tmp_path):
        path = tmp_path / "s.jsonl"
        PersistentSourcesStore(path, capacity=10).put("rid1", {"v": 1})
        reborn = PersistentSourcesStore(path, capacity=10)
        assert reborn.get("rid1") == {"v": 1}

    def test_capacity_keeps_most_recent_window(self, tmp_path):
        path = tmp_path / "s.jsonl"
        store = PersistentSourcesStore(path, capacity=2)
        for i in range(5):
            store.put(f"rid{i}", {"i": i})
        assert store.get("rid0") is None  # 最旧者被淘汰
        assert store.get("rid4") == {"i": 4}
        reborn = PersistentSourcesStore(path, capacity=2)
        assert reborn.get("rid4") == {"i": 4}
        assert reborn.get("rid3") == {"i": 3}  # 重启后窗口=文件末尾最近 2 条
        assert reborn.get("rid2") is None

    def test_corrupt_lines_are_skipped(self, tmp_path):
        path = tmp_path / "s.jsonl"
        PersistentSourcesStore(path, capacity=10).put("rid1", {"v": 1})
        with path.open("a", encoding="utf-8") as f:
            f.write("{bad json\n")
        reborn = PersistentSourcesStore(path, capacity=10)
        assert reborn.get("rid1") == {"v": 1}


def _mock_settings(tmp_path) -> Settings:
    return Settings(rag_mode="mock", log_dir=str(tmp_path), cors_origins="*")


class TestServerWiring:
    def test_request_log_and_sources_persistence(self, tmp_path):
        cfg = _mock_settings(tmp_path)
        client = TestClient(create_app(cfg))

        resp = client.post("/query", json={"question": "简化接口怎么用？"})
        assert resp.status_code == 200
        resp.text  # 读完流，确保 done 事件后的落盘执行
        rid = resp.headers["X-Request-ID"]

        got = client.get(f"/sources/{rid}")
        assert got.status_code == 200
        assert got.json()["question"] == "简化接口怎么用？"

        # 请求级日志：每条请求一行，含方法/路径/状态/耗时
        req_lines = (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()
        recs = [json.loads(x) for x in req_lines]
        mine = [r for r in recs if r.get("request_id") == rid]
        assert mine and mine[0]["path"] == "/query" and mine[0]["status"] == 200
        assert mine[0]["duration_ms"] >= 0

        # "服务重启"（新 app 实例、同一日志目录）后引用仍可回查
        reborn_client = TestClient(create_app(cfg))
        got2 = reborn_client.get(f"/sources/{rid}")
        assert got2.status_code == 200
        assert got2.json()["question"] == "简化接口怎么用？"

    def test_sources_404_message_kept(self, tmp_path):
        client = TestClient(create_app(_mock_settings(tmp_path)))
        resp = client.get("/sources/does-not-exist")
        assert resp.status_code == 404
        assert "未找到" in resp.json()["error"]
