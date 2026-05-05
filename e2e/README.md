# TradeCopilot E2E (Playwright)

> Educational use only. Not financial advice.

End-to-end + API contract tests for the TradeCopilot deployment. Inspired by
the canonical [10 GitHub repos for software testers](https://dev.to/n_demia/10-github-repositories-for-software-testers-59ea)
list — Playwright is the right pick for a TS-first SPA + REST stack.

## What's covered

| Suite | File | Hits |
|---|---|---|
| API contract smoke (11 tests) | `tests/api.spec.ts`        | health, signup, login, /me, dashboard, RiskRule defaults, autonomy gate, predict baseline, audit, kill switch round-trip |
| UI smoke (3 tests)            | `tests/smoke.spec.ts`      | login page renders, signup → dashboard, sign out |
| Navigation smoke (8 tests)    | `tests/navigation.spec.ts` | Every protected page renders + disclaimer mounts |

## Run against the live deploy

```bash
cd e2e
npm install
npm run install-browsers
npm test                                 # both suites against https://tradecopilot-{web,api}.onrender.com
npm run test:api                         # API contract only — fastest signal
npm run test:smoke                       # UI smoke only
npm run test:headed                      # UI in visible Chrome
npm run report                           # open HTML report after a run
```

## Run against local Docker compose

```bash
WEB_BASE_URL=http://localhost:5173 API_BASE_URL=http://localhost:8000 npm test
```

## What it catches (and how the live deploy got here)

This suite was written *after* the `passlib + bcrypt 4.x` and `Render
static-site rewrite doesn't proxy POSTs` regressions both shipped to prod.
Both would have been caught instantly by `tests/api.spec.ts` (signup gives a
JWT) and `tests/smoke.spec.ts` (signup → dashboard) respectively.

## Compliance reminder

Tests use `e2e-…@example.com` accounts; they're real rows in the live DB.
Periodically clean them up via the admin console or `DELETE FROM users
WHERE email LIKE 'e2e-%'`. Never run these tests against a production tenant
that holds real broker credentials.
