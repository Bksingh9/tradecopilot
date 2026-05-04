# @tradecopilot/plugin

Embeddable widget + JS/TS SDK for partners building on top of TradeCopilot.

> Educational and decision-support tool only. Not financial advice.

## Install

```bash
npm install @tradecopilot/plugin
# or build locally:
npm install
npm run build
```

## SDK usage (Node / browser)

```ts
import TradeCopilotSDK from "@tradecopilot/plugin";

const sdk = new TradeCopilotSDK({
  baseUrl: "https://api.tradecopilot.app",
  partnerId: 17,
  partnerKey: process.env.TC_PARTNER_KEY!,
});

// Provision a user under your tenant
await sdk.createUser("alice@partner.io", "long-random-pw");

// Push a closed trade for journaling/analytics
await sdk.pushTrade({
  user_id: 42,
  symbol: "RELIANCE",
  side: "BUY",
  qty: 10,
  entry_price: 2500,
  exit_price: 2580,
  realized_pnl: 800,
  r_multiple: 1.6,
  strategy: "momentum",
  status: "CLOSED",
});

// Get the most recent weekly AI coach report
const report = await sdk.getWeeklyReport(42);
console.log(report.content);
```

## Embeddable widget

Drop one tag on any page (no React/jQuery required):

```html
<div id="tradecopilot-widget"
     data-base-url="https://api.tradecopilot.app"
     data-user-token="tc_..."></div>
<script src="https://cdn.example.com/tradecopilot/widget.iife.js"></script>
<script>TradeCopilotWidget.mount();</script>
```

The widget loads:

- realized P&L today
- open positions count
- daily-loss-limit gauge + kill-switch banner
- last 3 AI coach comments

It refreshes every 30s by default. Pass `{refreshSeconds: 60}` to `mount()` to slow it down.

## Tokens

- `partnerKey` (X-Partner-Key) lets you call **partner-scoped** endpoints
  (`/api/partner/{partner_id}/*`). Issued by an admin via
  `POST /api/partner/admin/partners`.
- `userToken` (X-API-Token) is a per-user long-lived token they create themselves
  via `POST /api/auth/api-tokens`. The widget needs this to read user-level
  dashboards.

## Dev

```bash
npm install
npm run build
# open index.html with a static server, e.g. `npx serve .`
```
