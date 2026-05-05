import { expect, test } from "@playwright/test";

/**
 * Navigation smoke — every protected page renders without a runtime error.
 * Uses one session, walks the sidebar.
 */

const uniqueEmail = `e2e-nav-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
const password = "qatest12345";

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/signup");
  await page.getByLabel(/email/i).fill(uniqueEmail);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/$/, { timeout: 75_000 });
  await page.close();
  await ctx.close();
});

const pages = [
  { path: "/", heading: /dashboard/i },
  { path: "/decisions", heading: /decisions/i },
  { path: "/trades", heading: /trades & journal/i },
  { path: "/tuning", heading: /strategy tuning/i },
  { path: "/coach", heading: /ai coach/i },
  { path: "/backtest", heading: /backtest/i },
  { path: "/audit", heading: /audit/i },
  { path: "/settings", heading: /settings/i },
];

test.describe("authed navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(uniqueEmail);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/$/, { timeout: 75_000 });
  });

  for (const p of pages) {
    test(`page ${p.path} renders without error`, async ({ page }) => {
      await page.goto(p.path);
      await expect(page.getByRole("heading", { name: p.heading })).toBeVisible({ timeout: 20_000 });
      // Disclaimer footer must mount on every protected page.
      await expect(page.getByText(/educational and decision-support tool only/i)).toBeVisible();
      // No uncaught error visible (loose check).
      await expect(page.locator("text=Application error")).toHaveCount(0);
    });
  }
});
