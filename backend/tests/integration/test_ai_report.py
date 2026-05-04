from __future__ import annotations

from datetime import datetime, timedelta


def test_fake_coach_weekly_report(client):
    # signup
    r = client.post("/api/auth/signup", json={"email": "ai@example.com", "password": "password123"})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # generate report (uses FakeCoach by default)
    r = client.post("/api/ai/weekly-report", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Snapshot" in body["content"]
    assert "Educational use only" in body["content"]
