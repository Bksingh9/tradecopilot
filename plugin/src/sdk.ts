/**
 * TradeCopilot Partner SDK.
 *
 * Wraps the partner-scoped REST endpoints. Authentication uses a single
 * `X-Partner-Key` header issued by an admin via /api/partner/admin/partners.
 */

export interface SDKOptions {
  baseUrl: string;       // e.g. "https://api.tradecopilot.app"
  partnerId: number;
  partnerKey: string;    // X-Partner-Key
  fetchImpl?: typeof fetch;
}

export interface DashboardSummary {
  realized_pnl_today: number;
  open_positions_count: number;
  daily_loss_limit_value: number;
  risk_used_pct: number;
  kill_switch_active: boolean;
  kill_switch_reason?: string | null;
}

export interface WeeklyReport {
  user_id: number;
  period_start: string;
  period_end: string;
  content: string;
}

export interface RiskGauges {
  risk_used_pct: number;
  daily_loss_limit_value: number;
  open_positions_count: number;
  kill_switch_active: boolean;
}

export interface AIComment {
  trade_id: number | null;
  content: string;
  created_at: string;
}

export class TradeCopilotSDK {
  private readonly opts: SDKOptions;
  private readonly fetch: typeof fetch;

  constructor(opts: SDKOptions) {
    this.opts = opts;
    this.fetch = opts.fetchImpl ?? fetch.bind(globalThis);
  }

  private url(path: string): string {
    return `${this.opts.baseUrl.replace(/\/$/, "")}${path}`;
  }

  private async req<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await this.fetch(this.url(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Partner-Key": this.opts.partnerKey,
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`TradeCopilotSDK ${path} failed (${res.status}): ${text.slice(0, 300)}`);
    }
    return (await res.json()) as T;
  }

  /** Create a user under the partner's tenant. */
  createUser(email: string, password: string): Promise<{ user_id: number; email: string; tenant_id: number }> {
    return this.req(`/api/partner/${this.opts.partnerId}/users`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  /** Push a single trade record into journaling/analytics. */
  pushTrade(trade: Record<string, unknown>): Promise<unknown> {
    return this.req(`/api/partner/${this.opts.partnerId}/trades`, {
      method: "POST",
      body: JSON.stringify(trade),
    });
  }

  /** Generate / fetch a weekly AI coach report for one user under this partner. */
  getWeeklyReport(userId: number): Promise<WeeklyReport> {
    return this.req<WeeklyReport>(
      `/api/partner/${this.opts.partnerId}/reports/${userId}/weekly`
    );
  }

  // The following methods rely on a user-scoped JWT or API token issued
  // through the regular auth flow; the partner key cannot impersonate a user
  // for these. They are exposed for *self-hosted* widget pages where the
  // end user is signed in.
  async getDashboard(userToken: string): Promise<DashboardSummary> {
    const res = await this.fetch(this.url("/api/trading/dashboard"), {
      headers: { "X-API-Token": userToken },
    });
    if (!res.ok) throw new Error(`dashboard failed (${res.status})`);
    return (await res.json()) as DashboardSummary;
  }

  async getRiskGauges(userToken: string): Promise<RiskGauges> {
    const d = await this.getDashboard(userToken);
    return {
      risk_used_pct: d.risk_used_pct,
      daily_loss_limit_value: d.daily_loss_limit_value,
      open_positions_count: d.open_positions_count,
      kill_switch_active: d.kill_switch_active,
    };
  }

  async getLatestAIComments(userToken: string, limit: number = 5): Promise<AIComment[]> {
    const res = await this.fetch(this.url(`/api/ai/reports?limit=${limit}`), {
      headers: { "X-API-Token": userToken },
    });
    if (!res.ok) throw new Error(`reports failed (${res.status})`);
    const rows = (await res.json()) as Array<{ id: number; kind: string; content: string; created_at: string }>;
    return rows.map((r) => ({
      trade_id: null,
      content: r.content,
      created_at: r.created_at,
    }));
  }
}

export default TradeCopilotSDK;
