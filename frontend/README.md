# TradeCopilot Frontend

> Educational and decision-support tool only. Not financial advice.

React + Vite + TypeScript + Tailwind operator console for the TradeCopilot Agent backend.

## What's here

- **Dashboard** — today's realized P&L, risk-used gauge, open positions, watchlist quotes, autonomy badge, kill-switch banner.
- **Trades & Journal** — filterable trades list with R-multiple, journal composer.
- **Tuning** — pending AI parameter suggestions with current vs. proposed side-by-side; explicit accept/reject (AI never auto-applies).
- **AI coach** — generate weekly reports, browse history.
- **Backtest** — queue walk-forward runs, see metrics + per-regime bar chart (recharts).
- **Audit** — searchable timeline of every consequential action (kill switch, tuning, agent stages, orders).
- **Settings** — autonomy mode + paper-qualification + consent, risk rules, agent cycle runner, flatten-now.

## Tech

- React 18, Vite 5, TypeScript 5
- TanStack Query 5 for server state
- React Router 6
- Tailwind CSS 3 (custom dark theme)
- Recharts 2 for backtest charts

## Setup

```bash
cd frontend
npm install
cp .env.example .env       # optional — defaults work via Vite proxy
npm run dev                # → http://localhost:5173
```

The Vite dev server proxies `/api/*`, `/health/*`, and `/disclaimer` to `http://localhost:8000`, so the backend can stay on its own port without CORS gymnastics.

For a production build:

```bash
npm run build
npm run preview            # serves dist/ on http://localhost:4173
```

## Auth flow

1. `POST /api/auth/signup` (or `/login`) → JWT.
2. JWT stored in `localStorage` (`tc_jwt`).
3. `Authorization: Bearer <token>` injected on every request by `src/api/client.ts`.
4. Multi-tab logout is detected via the `storage` event.

## Compliance language

Every page mounts the `<Disclaimer>` footer; the kill-switch banner is rendered prominently when active; backtest results carry the "Past performance is not indicative of future results" line. Marketing copy avoids "guaranteed", "sure-shot", "always accurate" — see the backend README for the full style guide.

## File map

```
frontend/
├── package.json
├── vite.config.ts                proxies /api → backend
├── tsconfig{,.node}.json
├── tailwind.config.js
├── index.html
├── .env.example
└── src/
    ├── main.tsx                  QueryClientProvider + AuthProvider
    ├── App.tsx                   Router + routes + ProtectedRoute
    ├── index.css                 Tailwind + design tokens
    ├── api/
    │   ├── client.ts             fetch wrapper, auth header injection
    │   ├── types.ts              TS mirrors of backend Pydantic models
    │   └── queries.ts            TanStack Query hooks for every endpoint
    ├── auth/
    │   ├── AuthContext.tsx
    │   └── ProtectedRoute.tsx
    ├── components/
    │   ├── Layout.tsx            sidebar nav + autonomy badge + health badge
    │   ├── Disclaimer.tsx
    │   ├── KillSwitchBanner.tsx
    │   ├── RiskGauge.tsx
    │   ├── Card.tsx, Button.tsx, Input.tsx, Badge.tsx, Empty.tsx, Spinner.tsx
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── SignupPage.tsx
    │   ├── DashboardPage.tsx
    │   ├── TradesPage.tsx        trades + journal composer
    │   ├── TuningPage.tsx
    │   ├── CoachPage.tsx
    │   ├── BacktestPage.tsx      walk-forward runs + recharts regime breakout
    │   ├── AuditPage.tsx
    │   └── SettingsPage.tsx      autonomy + risk + agent cycle controls
    └── lib/
        ├── format.ts             money / pct / dates / pnl color helpers
        └── cn.ts
```
