"""Partner API end-to-end: admin creates partner → partner creates user → push trade → fetch report."""
from __future__ import annotations

from tests.conftest import make_admin


def test_partner_e2e(client, engine):
    admin_h = make_admin(engine)

    # Admin needs to know the tenant_id; admin-api lists users — first one is admin itself.
    r = client.get("/api/admin/users", headers=admin_h)
    assert r.status_code == 200
    admin = next(u for u in r.json() if u["role"] == "admin")
    tenant_id = admin["tenant_id"]

    # Provision partner
    r = client.post(
        "/api/partner/admin/partners",
        json={"tenant_id": tenant_id, "name": "Acme", "scopes": ["users", "trades"]},
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    partner_id = r.json()["partner_id"]
    api_key = r.json()["api_key"]

    pk_h = {"X-Partner-Key": api_key}

    # Create a user under the tenant
    r = client.post(
        f"/api/partner/{partner_id}/users",
        json={"email": "alice@partner.io", "password": "password123"},
        headers=pk_h,
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["user_id"]

    # Push a closed trade
    r = client.post(
        f"/api/partner/{partner_id}/trades",
        json={
            "user_id": user_id,
            "symbol": "RELIANCE",
            "side": "BUY",
            "qty": 10,
            "entry_price": 2500,
            "exit_price": 2580,
            "realized_pnl": 800,
            "r_multiple": 1.6,
            "strategy": "momentum",
            "status": "CLOSED",
        },
        headers=pk_h,
    )
    assert r.status_code == 200, r.text

    # Fetch weekly report (FakeCoach)
    r = client.get(f"/api/partner/{partner_id}/reports/{user_id}/weekly", headers=pk_h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Educational use only" in body["content"]


def test_partner_key_cannot_cross_tenants(client, engine):
    admin_h = make_admin(engine)

    # Create two tenants by admin-creating two partners with different tenant_ids.
    # Easier: we already have tenant_id=1 (admin's). Create another via signup.
    r = client.post("/api/auth/signup", json={"email": "u2@example.com", "password": "password123"})
    assert r.status_code == 200
    # the new user will live in tenant_id=2 (or whatever sequence allocates)
    r2 = client.get("/api/admin/users", headers=admin_h)
    other_tenant = next(u["tenant_id"] for u in r2.json() if u["email"] == "u2@example.com")

    # admin creates partner in *other* tenant
    r = client.post(
        "/api/partner/admin/partners",
        json={"tenant_id": other_tenant, "name": "Other", "scopes": []},
        headers=admin_h,
    )
    partner_id = r.json()["partner_id"]
    api_key = r.json()["api_key"]

    # Try to call with WRONG partner_id in path
    r = client.post(
        f"/api/partner/{partner_id + 999}/users",
        json={"email": "x@x.io", "password": "password123"},
        headers={"X-Partner-Key": api_key},
    )
    assert r.status_code == 403
