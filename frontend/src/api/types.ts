/** TS types mirroring the backend Pydantic / SQLModel surface. Kept loose where
 * the backend returns nested JSON so the UI can iterate.
 */

export type AutonomyMode = "advisory" | "semi_auto" | "full_auto";

export interface User {
  id: number;
  tenant_id: number;
  email: string;
  role: "user" | "admin";
  autonomy_mode: AutonomyMode;
  paper_qualified_at: string | null;
  consent_full_auto: boolean;
}

export interface AuthRes {
  access_token: string;
  token_type: string;
}

export interface RiskRule {
  user_id: number;
  tenant_id: number;
  max_risk_per_trade_pct: number;
  daily_loss_limit_pct: number;
  max_open_positions: number;
  restricted_symbols: string[];
  paper_only: boolean;
  starting_equity: number;
  updated_at?: string;
}

export interface Quote {
  symbol: string;
  exchange?: string | null;
  ltp: number;
  bid?: number | null;
  ask?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  prev_close?: number | null;
  volume?: number | null;
  currency: string;
  timestamp: string;
  source: string;
}

export interface DashboardRes {
  realized_pnl_today: number;
  unrealized_pnl?: number;
  open_positions_count: number;
  daily_loss_limit_value: number;
  risk_used_pct: number;
  watchlist: Quote[];
  kill_switch_active: boolean;
  kill_switch_reason?: string | null;
  autonomy_mode: AutonomyMode;
  capital_deployed?: number;
  starting_equity?: number;
}

export interface Trade {
  id: number;
  user_id: number;
  tenant_id: number;
  broker: string;
  symbol: string;
  exchange?: string | null;
  side: "BUY" | "SELL";
  qty: number;
  entry_price: number;
  exit_price?: number | null;
  stop_price?: number | null;
  target_price?: number | null;
  realized_pnl?: number | null;
  r_multiple?: number | null;
  strategy?: string | null;
  status: "OPEN" | "CLOSED" | "CANCELLED";
  paper: boolean;
  opened_at: string;
  closed_at?: string | null;
}

export interface JournalEntry {
  id: number;
  user_id: number;
  tenant_id: number;
  trade_id?: number | null;
  setup?: string | null;
  emotion_tag?: string | null;
  screenshot_url?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface Summary {
  trade_count: number;
  closed_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  avg_r: number;
  best_trade: number;
  worst_trade: number;
}

export interface SummaryRes {
  summary: Summary;
  by_symbol: Record<string, Summary>;
  by_strategy: Record<string, Summary>;
  by_hour: Record<string, Summary>;
  r_distribution: Record<string, number>;
  streaks: { longest_win: number; longest_loss: number; current: number };
  best_hour: number | null;
  worst_hour: number | null;
}

export interface TuningSuggestion {
  id: number;
  user_id: number;
  tenant_id: number;
  strategy: string;
  current_params: Record<string, unknown>;
  suggested_params: Record<string, unknown>;
  rationale: string;
  status: "pending" | "accepted" | "rejected" | "expired";
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  tenant_id: number;
  user_id?: number | null;
  actor: string;
  action: string;
  subject_type?: string | null;
  subject_id?: string | null;
  payload: Record<string, unknown>;
  at: string;
}

export interface KillSwitch {
  id: number;
  tenant_id: number;
  scope: "user" | "tenant";
  user_id?: number | null;
  reason: string;
  set_by: string;
  active: boolean;
  cleared_at?: string | null;
  created_at: string;
}

export interface AIReport {
  id: number;
  user_id: number;
  tenant_id: number;
  kind: string;
  period_start?: string | null;
  period_end?: string | null;
  content: string;
  created_at: string;
}

export interface BacktestRun {
  id: number;
  user_id: number;
  tenant_id: number;
  strategy: string;
  config_json: Record<string, unknown>;
  metrics_json: Record<string, unknown>;
  status: "queued" | "running" | "done" | "failed";
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface AutonomyRes {
  autonomy_mode: AutonomyMode;
  paper_qualified_at: string | null;
  consent_full_auto: boolean;
  eligible_for_full_auto: boolean;
}

export interface MeRes {
  id: number;
  tenant_id: number;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  autonomy_mode: AutonomyMode;
  paper_qualified_at?: string | null;
  consent_full_auto: boolean;
  created_at?: string | null;
}

export interface PredictionResult {
  symbol: string;
  timeframe: string;
  prob_up: number;
  prob_down: number;
  expected_return: number;
  risk_score: number;
  model_version: string;
  generated_at: string;
  notes: string[];
}

export interface DecisionContext {
  symbol: string;
  timeframe: string;
  prediction: PredictionResult;
  similar_windows: Array<{
    subject_id: string;
    score: number;
    period?: string;
    regime?: string;
    return_n?: number | null;
    journal_excerpts?: string[];
  }>;
  current_features: Record<string, number>;
  risk_snapshot: Record<string, unknown>;
  autonomy: AutonomyMode;
  user_behavior_profile?: {
    tendencies?: Record<string, unknown>;
    top_emotions?: Array<{ tag: string; count: number }>;
    streaks?: { longest_win: number; longest_loss: number; current: number };
    sample_size?: number;
  };
}

export interface DecisionOutcome {
  context: DecisionContext;
  proposal?: {
    candidate: { symbol: string; side: "BUY" | "SELL"; qty: number; entry: number; stop: number; strategy: string; rationale: string };
    ml_confidence: number;
    rationale: string;
  } | null;
  decision?: {
    candidate: { symbol: string; side: "BUY" | "SELL"; qty: number; entry: number };
    action: "approve" | "scale_down" | "reject";
    final_qty: number;
    reason: string;
  } | null;
  execution?: {
    candidate: { symbol: string; side: "BUY" | "SELL" };
    decision: { action: string };
    status: "placed" | "proposed" | "skipped" | "blocked";
    broker_order_id?: string | null;
    error?: string | null;
  } | null;
  error?: string | null;
}

export interface AdminPerformanceOverview {
  trade_count: number;
  closed_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  median_pnl: number;
  by_strategy: Record<string, { count: number; total_pnl: number; win_rate: number }>;
  tenants_with_activity: number;
  users_with_activity: number;
}

export interface CreatePartnerRes {
  partner_id: number;
  api_key: string;
}

export interface CycleReport {
  user_id: number;
  tenant_id: number;
  mode: AutonomyMode;
  started_at: string;
  finished_at?: string | null;
  stages: Array<{
    stage: "analyst" | "strategy" | "risk" | "execution" | "coach";
    ok: boolean;
    summary: string;
    payload?: Record<string, unknown>;
  }>;
  results: Array<{
    candidate: { symbol: string; side: "BUY" | "SELL"; qty: number; entry: number; stop: number; strategy: string };
    decision: { action: "approve" | "scale_down" | "reject"; final_qty: number; reason: string };
    status: "placed" | "proposed" | "skipped" | "blocked";
    broker_order_id?: string | null;
    error?: string | null;
    at: string;
  }>;
}
