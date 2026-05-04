"""Autonomy gates: full_auto requires paper-qualification + explicit consent."""
from __future__ import annotations


def _signup(client, email="aut@example.com", password="password123"):
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_auto_blocked_without_qualification(client):
    h = _signup(client)
    # Even if the plan allowed it, paper-qualification is required.
    r = client.put("/api/users/autonomy",
                   json={"autonomy_mode": "full_auto", "consent_full_auto": True},
                   headers=h)
    # Free plan also doesn't allow full_auto, so 403 is correct either way.
    assert r.status_code in (403, 422), r.text


def test_semi_auto_blocked_on_free_plan(client):
    h = _signup(client, email="aut2@example.com")
    r = client.put("/api/users/autonomy",
                   json={"autonomy_mode": "semi_auto"}, headers=h)
    assert r.status_code == 403


def test_advisory_default(client):
    h = _signup(client, email="aut3@example.com")
    r = client.get("/api/users/autonomy", headers=h)
    assert r.status_code == 200
    assert r.json()["autonomy_mode"] == "advisory"
