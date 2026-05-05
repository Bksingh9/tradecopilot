import { expect, test } from "@playwright/test";

/**
 * API contract smoke. Mirrors the bash smoke we ran live, but pins the
 * expected response shapes so a regression on any of them fails CI.
 *
 * Reuses one freshly-signed-up user across the file.
 */

const uniqueEmail = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
const password = "qatest12345";
let token = "";

test.describe.configure({ mode: "serial" });

test("health/core returns ok + db ok", async ({ request }) => {
  const res = await request.get("/health/core");
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body).toMatchObject({ ok: true, db: "ok" });
});

test("disclaimer is mounted with educational language", async ({ request }) => {
  const res = await request.get("/disclaimer");
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.disclaimer).toMatch(/educational/i);
  expect(body.disclaimer).toMatch(/not financial advice/i);
});

test("signup returns a JWT", async ({ request }) => {
  const res = await request.post("/api/auth/signup", {
    data: { email: uniqueEmail, password },
  });
  expect(res.status(), await res.text()).toBe(200);
  const body = await res.json();
  expect(body.access_token).toMatch(/^[\w-]+\.[\w-]+\.[\w-]+$/);
  token = body.access_token;
});

test("login returns a fresh JWT", async ({ request }) => {
  const res = await request.post("/api/auth/login", {
    data: { email: uniqueEmail, password },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.access_token).toBeTruthy();
});

test("/me reflects the new user with default autonomy=advisory", async ({ request }) => {
  const res = await request.get("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.email).toBe(uniqueEmail);
  expect(body.role).toBe("user");
  expect(body.autonomy_mode).toBe("advisory");
  expect(body.consent_full_auto).toBe(false);
});

test("dashboard zero-state: no positions, no losses, kill switch inactive", async ({ request }) => {
  const res = await request.get("/api/trading/dashboard", { headers: { Authorization: `Bearer ${token}` } });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.realized_pnl_today).toBe(0);
  expect(body.open_positions_count).toBe(0);
  expect(body.kill_switch_active).toBe(false);
});

test("default RiskRule auto-created on first read", async ({ request }) => {
  const res = await request.get("/api/trading/risk", { headers: { Authorization: `Bearer ${token}` } });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.starting_equity).toBe(100000);
  expect(body.paper_only).toBe(true);
});

test("autonomy upgrade to full_auto blocked without paper qualification", async ({ request }) => {
  const res = await request.put("/api/users/autonomy", {
    headers: { Authorization: `Bearer ${token}` },
    data: { autonomy_mode: "full_auto", consent_full_auto: true },
  });
  // Free plan blocks, OR autonomy guard blocks. Either way: not 200.
  expect([403, 422]).toContain(res.status());
});

test("predict baseline path: no model trained yet ⇒ baseline result", async ({ request }) => {
  const res = await request.get("/api/predict/RELIANCE.NS?timeframe=1d&exchange_hint=NSE", {
    headers: { Authorization: `Bearer ${token}` },
    timeout: 60_000,
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.symbol).toBe("RELIANCE.NS");
  expect(body.model_version).toBe("baseline");
  expect(body.prob_up).toBeCloseTo(0.5, 5);
});

test("audit log responds (may be empty for a new user)", async ({ request }) => {
  const res = await request.get("/api/audit/me?limit=10", { headers: { Authorization: `Bearer ${token}` } });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(Array.isArray(body)).toBe(true);
});

test("kill switch round-trip: trigger → blocked → clear", async ({ request }) => {
  const set = await request.post("/api/trading/kill-switch", {
    headers: { Authorization: `Bearer ${token}` },
    data: { reason: "e2e-test" },
  });
  expect(set.status()).toBe(200);
  const ks = await set.json();

  const dash = await request.get("/api/trading/dashboard", { headers: { Authorization: `Bearer ${token}` } });
  const dbody = await dash.json();
  expect(dbody.kill_switch_active).toBe(true);

  const clear = await request.post(`/api/trading/kill-switch/${ks.id}/clear`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(clear.status()).toBe(200);
  expect((await clear.json()).ok).toBe(true);
});
