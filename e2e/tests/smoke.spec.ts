import { expect, test } from "@playwright/test";

/**
 * UI smoke against the live frontend. Exercises:
 *   - login page loads + disclaimer mounted
 *   - signup creates account + lands on dashboard
 *   - dashboard zero-state KPIs visible
 *   - sign out returns to /login
 */

const uniqueEmail = `e2e-ui-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
const password = "qatest12345";

test.describe.configure({ mode: "serial" });

test("login page renders with disclaimer", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /TradeCopilot/i })).toBeVisible();
  await expect(page.getByText(/educational and decision-support/i)).toBeVisible();
  await expect(page.getByText(/not financial advice/i)).toBeVisible();
});

test("signup → dashboard end-to-end", async ({ page }) => {
  await page.goto("/signup");

  await page.getByLabel(/email/i).fill(uniqueEmail);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /create account/i }).click();

  // First request after a free-tier sleep can be 30–60s — bake in tolerance.
  await expect(page).toHaveURL(/\/$/, { timeout: 75_000 });

  // Dashboard chrome.
  await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 30_000 });

  // KPIs that the new account always renders.
  await expect(page.getByText(/today.s realized P/i)).toBeVisible();
  await expect(page.getByText(/risk used/i)).toBeVisible();
  await expect(page.getByText(/open positions/i)).toBeVisible();

  // Autonomy badge in sidebar.
  await expect(page.getByText(/autonomy/i)).toBeVisible();
});

test("sign out returns to /login", async ({ page }) => {
  // Re-use session by logging in through /login (signup flow already created the user).
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(uniqueEmail);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/$/, { timeout: 75_000 });

  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
});
