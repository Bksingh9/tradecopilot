import { defineConfig, devices } from "@playwright/test";

/**
 * Point at any environment via two env vars:
 *   WEB_BASE_URL  default https://tradecopilot-web.onrender.com
 *   API_BASE_URL  default https://tradecopilot-api.onrender.com
 *
 * Local dev:
 *   WEB_BASE_URL=http://localhost:5173 API_BASE_URL=http://localhost:8000 npm test
 */
const WEB_BASE_URL = process.env.WEB_BASE_URL ?? "https://tradecopilot-web.onrender.com";
const API_BASE_URL = process.env.API_BASE_URL ?? "https://tradecopilot-api.onrender.com";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,                  // keep auth/state ordering predictable
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"], ["html", { open: "never" }]],
  timeout: 90_000,                       // free-tier cold start ≤ 60s; bake in margin
  expect: { timeout: 15_000 },

  use: {
    baseURL: WEB_BASE_URL,
    extraHTTPHeaders: { "x-e2e": "1" },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ignoreHTTPSErrors: true,
  },

  projects: [
    {
      name: "api-smoke",
      testMatch: /.*\/api\.spec\.ts$/,
      use: {
        baseURL: API_BASE_URL,
      },
    },
    {
      name: "ui-smoke",
      testMatch: /.*\/(smoke|navigation)\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
