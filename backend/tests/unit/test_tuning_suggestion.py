"""Critical safety property: AI-generated tuning suggestions are never auto-applied."""
from __future__ import annotations

from app.trading.models import StrategyTuningSuggestion


def test_suggestion_starts_pending_and_must_be_accepted_explicitly(client, engine):
    # signup
    r = client.post("/api/auth/signup", json={"email": "tu@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # request a tuning review (FakeCoach in tests)
    r = client.post(
        "/api/ai/tuning/request",
        json={"strategy": "momentum", "current_params": {"fast": 9, "slow": 21}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["status"] == "pending"

    # listing — still pending
    r = client.get("/api/trading/tuning?status=pending", headers=headers)
    assert r.status_code == 200
    assert any(row["id"] == sid for row in r.json())

    # accept it
    r = client.post(f"/api/trading/tuning/{sid}/accept", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # second accept must fail (already reviewed)
    r = client.post(f"/api/trading/tuning/{sid}/accept", headers=headers)
    assert r.status_code in (403, 409)
