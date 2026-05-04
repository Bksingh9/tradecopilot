/**
 * Embeddable widget. Drop this on any HTML page:
 *
 *   <div id="tradecopilot-widget"
 *        data-base-url="https://api.tradecopilot.app"
 *        data-user-token="tc_..."></div>
 *   <script src="/dist/widget.iife.js"></script>
 *   <script>TradeCopilotWidget.mount();</script>
 *
 * The widget loads the user's P&L summary, risk gauges, and latest AI comments.
 * No React, no framework dependency — just vanilla TS compiled to a single IIFE.
 */
import { TradeCopilotSDK, type DashboardSummary, type AIComment } from "./sdk";

export interface MountOptions {
  selector?: string;
  baseUrl?: string;
  userToken?: string;
  refreshSeconds?: number;
}

const DEFAULT_SELECTOR = "#tradecopilot-widget";

export async function mount(opts: MountOptions = {}): Promise<void> {
  const root = document.querySelector(opts.selector ?? DEFAULT_SELECTOR) as HTMLElement | null;
  if (!root) return;

  const baseUrl = opts.baseUrl ?? root.dataset.baseUrl ?? "";
  const userToken = opts.userToken ?? root.dataset.userToken ?? "";
  const refresh = opts.refreshSeconds ?? 30;

  if (!baseUrl || !userToken) {
    root.innerHTML = errorBox("Missing baseUrl / userToken");
    return;
  }

  // SDK uses partnerKey only for partner endpoints; here we pass dummy values
  // because the widget calls user-scoped endpoints with X-API-Token.
  const sdk = new TradeCopilotSDK({
    baseUrl,
    partnerId: 0,
    partnerKey: "n/a",
  });

  root.innerHTML = shell();
  await render(sdk, root, userToken);
  setInterval(() => render(sdk, root, userToken).catch(() => {}), refresh * 1000);
}

async function render(sdk: TradeCopilotSDK, root: HTMLElement, userToken: string): Promise<void> {
  try {
    const [dash, comments] = await Promise.all([
      sdk.getDashboard(userToken),
      sdk.getLatestAIComments(userToken, 3),
    ]);
    root.querySelector("[data-slot='kpi']")!.innerHTML = kpiBlock(dash);
    root.querySelector("[data-slot='risk']")!.innerHTML = riskBlock(dash);
    root.querySelector("[data-slot='ai']")!.innerHTML = aiBlock(comments);
  } catch (e) {
    root.innerHTML = errorBox(`Failed to load: ${(e as Error).message}`);
  }
}

function shell(): string {
  return `
    <style>
      .tcw{font-family:system-ui,-apple-system,sans-serif;border:1px solid #ddd;border-radius:12px;padding:16px;max-width:480px;color:#1a1a1a;background:#fff}
      .tcw h3{margin:0 0 8px;font-size:14px;letter-spacing:.04em;color:#666;text-transform:uppercase}
      .tcw .kpi{display:flex;gap:16px;margin-bottom:12px}
      .tcw .kpi .num{font-size:24px;font-weight:600}
      .tcw .gauge{background:#eee;border-radius:8px;height:8px;overflow:hidden;margin:6px 0 10px}
      .tcw .gauge>span{display:block;height:100%;background:#0a7;}
      .tcw .gauge.warn>span{background:#d83;}
      .tcw .gauge.bad>span{background:#c33;}
      .tcw .ai{font-size:13px;color:#333;border-top:1px solid #eee;padding-top:10px}
      .tcw .ai pre{white-space:pre-wrap;font-family:inherit;margin:8px 0}
      .tcw .disc{font-size:11px;color:#888;border-top:1px solid #eee;margin-top:10px;padding-top:8px}
    </style>
    <div class="tcw">
      <div data-slot="kpi"></div>
      <div data-slot="risk"></div>
      <div data-slot="ai"></div>
      <div class="disc">Educational use only. Not financial advice.</div>
    </div>`;
}

function kpiBlock(d: DashboardSummary): string {
  const pnlColor = d.realized_pnl_today >= 0 ? "#0a7" : "#c33";
  return `
    <h3>Today</h3>
    <div class="kpi">
      <div><div class="num" style="color:${pnlColor}">${fmt(d.realized_pnl_today)}</div><div>realized P&amp;L</div></div>
      <div><div class="num">${d.open_positions_count}</div><div>open positions</div></div>
    </div>`;
}

function riskBlock(d: DashboardSummary): string {
  const used = clamp(d.risk_used_pct, 0, 100);
  const cls = used >= 100 ? "bad" : used >= 75 ? "warn" : "";
  const ks = d.kill_switch_active
    ? `<div style="color:#c33;margin:6px 0 10px;font-weight:600;">Kill switch active${d.kill_switch_reason ? `: ${escapeHtml(d.kill_switch_reason)}` : ""}</div>`
    : "";
  return `
    <h3>Risk</h3>
    ${ks}
    <div>Daily loss limit used: ${used.toFixed(1)}%</div>
    <div class="gauge ${cls}"><span style="width:${used}%"></span></div>`;
}

function aiBlock(comments: AIComment[]): string {
  if (!comments.length) return `<div class="ai"><h3>AI coach</h3><div>No comments yet.</div></div>`;
  return `
    <div class="ai">
      <h3>Latest AI coach</h3>
      ${comments.map((c) => `<pre>${escapeHtml(truncate(c.content, 400))}</pre>`).join("")}
    </div>`;
}

function errorBox(msg: string): string {
  return `<div style="font-family:system-ui;color:#a00;padding:12px;border:1px solid #f3c1c1;border-radius:8px;">${escapeHtml(msg)}</div>`;
}

function fmt(n: number): string {
  return (n >= 0 ? "+" : "") + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n) + "…";
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Auto-mount in a browser if the element is already on the page.
if (typeof document !== "undefined" && document.querySelector(DEFAULT_SELECTOR)) {
  mount().catch(() => {});
}

export default { mount };
