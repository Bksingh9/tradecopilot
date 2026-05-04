from __future__ import annotations


def test_health_core_ok(client):
    r = client.get("/health/core")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["db"] == "ok"


def test_health_ai_redis_unreachable(client, monkeypatch):
    # Force a bogus redis URL so the connection fails
    from app.config import settings
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")

    r = client.get("/health/ai")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"redis_unreachable", "worker_stale"}
    assert body["redis_ok"] is False or body["worker_fresh"] is False
