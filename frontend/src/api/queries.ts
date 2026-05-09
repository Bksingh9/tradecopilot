/** TanStack Query hooks for every backend surface used by the SPA. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  AdminPerformanceOverview,
  AIReport,
  AuditEvent,
  AuthRes,
  AutonomyMode,
  AutonomyRes,
  BacktestRun,
  CreatePartnerRes,
  CycleReport,
  DashboardRes,
  DecisionOutcome,
  JournalEntry,
  KillSwitch,
  MeRes,
  Quote,
  RiskRule,
  SummaryRes,
  Trade,
  TuningSuggestion,
} from "./types";

// ---- Auth -----------------------------------------------------------------
export function useSignup() {
  return useMutation({
    mutationFn: (vars: { email: string; password: string }) =>
      api.post<AuthRes>("/api/auth/signup", vars),
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: (vars: { email: string; password: string }) =>
      api.post<AuthRes>("/api/auth/login", vars),
  });
}

// ---- Dashboard -----------------------------------------------------------
export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardRes>("/api/trading/dashboard"),
    refetchInterval: 30_000,
  });
}

// ---- Quote ---------------------------------------------------------------
export function useQuote(symbol: string | null, exchangeHint?: string) {
  return useQuery({
    queryKey: ["quote", symbol, exchangeHint],
    queryFn: () =>
      api.get<Quote>("/api/trading/quote", { symbol: symbol!, exchange_hint: exchangeHint }),
    enabled: !!symbol,
  });
}

// ---- Risk ----------------------------------------------------------------
export function useRisk() {
  return useQuery({
    queryKey: ["risk"],
    queryFn: () => api.get<RiskRule>("/api/trading/risk"),
  });
}

export function useUpdateRisk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<RiskRule>) => api.put<RiskRule>("/api/trading/risk", patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// ---- Autonomy ------------------------------------------------------------
export function useAutonomy() {
  return useQuery({
    queryKey: ["autonomy"],
    queryFn: () => api.get<AutonomyRes>("/api/users/autonomy"),
  });
}

export function useSetAutonomy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { autonomy_mode: AutonomyMode; consent_full_auto?: boolean }) =>
      api.put<AutonomyRes>("/api/users/autonomy", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["autonomy"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useQualifyPaper() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AutonomyRes>("/api/users/qualify-paper"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autonomy"] }),
  });
}

// ---- Kill switch ---------------------------------------------------------
export function useTriggerKillSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      api.post<KillSwitch>("/api/trading/kill-switch", { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });
}

export function useClearKillSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<{ ok: boolean }>(`/api/trading/kill-switch/${id}/clear`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });
}

// ---- Trades + journal ----------------------------------------------------
export function useTrades(filters?: { status?: string; symbol?: string; strategy?: string }) {
  return useQuery({
    queryKey: ["trades", filters],
    queryFn: () => api.get<Trade[]>("/api/journal/trades", filters),
  });
}

// ---- Place / close orders ------------------------------------------------
export interface PlaceOrderReq {
  symbol: string;
  exchange?: string;
  side: "BUY" | "SELL";
  qty: number;
  order_type?: "MARKET" | "LIMIT";
  price?: number;
  product?: "CNC" | "MIS" | "NRML" | "DAY";
  strategy?: string;
  paper?: boolean;
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ broker, ...order }: PlaceOrderReq & { broker: string }) =>
      api.post<{
        broker: string;
        broker_order_id: string;
        status: string;
        avg_price: number | null;
      }>(`/api/trading/orders`, order, { broker, paper: order.paper ?? true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}

export function useClosePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tradeId: number) =>
      api.post<{
        id: number;
        symbol: string;
        exit_price: number;
        realized_pnl: number;
        status: string;
      }>(`/api/trading/positions/${tradeId}/close`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}

// ---- Watchlist -----------------------------------------------------------
export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.get<{ watchlist: string[] }>("/api/users/watchlist"),
  });
}

export function useWatchlistAdd() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      api.post<{ watchlist: string[] }>("/api/users/watchlist/add", { symbol }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useWatchlistRemove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      api.post<{ watchlist: string[] }>("/api/users/watchlist/remove", { symbol }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useJournalEntries() {
  return useQuery({
    queryKey: ["journal-entries"],
    queryFn: () => api.get<JournalEntry[]>("/api/journal/entries"),
  });
}

export function useAddJournalEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: Partial<JournalEntry>) =>
      api.post<JournalEntry>("/api/journal/entries", vars),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["journal-entries"] }),
  });
}

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: () => api.get<SummaryRes>("/api/journal/summary"),
  });
}

// ---- Tuning suggestions ---------------------------------------------------
export function useTuningSuggestions(status?: string) {
  return useQuery({
    queryKey: ["tuning", status],
    queryFn: () =>
      api.get<TuningSuggestion[]>("/api/trading/tuning", status ? { status } : undefined),
  });
}

export function useReviewTuning() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "accept" | "reject" }) =>
      api.post<TuningSuggestion>(`/api/trading/tuning/${id}/${action}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tuning"] }),
  });
}

export function useRequestTuning() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { strategy: string; current_params: Record<string, unknown> }) =>
      api.post<TuningSuggestion>("/api/ai/tuning/request", vars),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tuning"] }),
  });
}

// ---- AI coach -------------------------------------------------------------
export function useAIReports() {
  return useQuery({
    queryKey: ["ai-reports"],
    queryFn: () => api.get<AIReport[]>("/api/ai/reports", { limit: 20 }),
  });
}

export function useGenerateWeekly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (days: number) =>
      api.post<{ id: number; period_start: string; period_end: string; content: string }>(
        "/api/ai/weekly-report",
        undefined,
        { days },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-reports"] }),
  });
}

// ---- Audit ---------------------------------------------------------------
export function useMyAudit(limit = 100) {
  return useQuery({
    queryKey: ["audit-me", limit],
    queryFn: () => api.get<AuditEvent[]>("/api/audit/me", { limit }),
  });
}

// ---- Backtest ------------------------------------------------------------
export function useBacktestRuns() {
  return useQuery({
    queryKey: ["backtest-runs"],
    queryFn: () => api.get<BacktestRun[]>("/api/backtest", { limit: 50 }),
    refetchInterval: 5_000,
  });
}

export function useBacktestRun(id: number | null) {
  return useQuery({
    queryKey: ["backtest-run", id],
    queryFn: () => api.get<BacktestRun>(`/api/backtest/${id}`),
    enabled: id != null,
    refetchInterval: (q) => (q.state.data?.status === "done" || q.state.data?.status === "failed" ? false : 3_000),
  });
}

export function useRunBacktest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { strategy: string; config: Record<string, unknown> }) =>
      api.post<BacktestRun>(`/api/backtest/run`, vars.config, { strategy: vars.strategy }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backtest-runs"] }),
  });
}

// ---- Agents ---------------------------------------------------------------
export function useRunCycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { symbols: string[]; timeframe?: string; broker?: string; exchange_hint?: string }) =>
      api.post<CycleReport>("/api/agents/cycle/run", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["audit-me"] });
    },
  });
}

export function useFlattenNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<unknown[]>("/api/agents/flatten-now"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { symbols: string[]; timeframe?: string; broker?: string; exchange_hint?: string }) =>
      api.post<DecisionOutcome[]>("/api/agents/decide", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["audit-me"] });
    },
  });
}

// ---- Health ---------------------------------------------------------------
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => ({
      core: await api.get<{ ok: boolean; db: string }>("/health/core"),
      ai: await api.get<{ status: string; redis_ok: boolean; worker_fresh: boolean }>("/health/ai"),
    }),
    refetchInterval: 60_000,
  });
}

// ---- Me + Admin ----------------------------------------------------------
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeRes>("/api/auth/me"),
    staleTime: 60_000,
  });
}

export function useAdminUsers() {
  return useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<MeRes[]>("/api/admin/users"),
  });
}

export function useAdminPerformance() {
  return useQuery({
    queryKey: ["admin-performance"],
    queryFn: () => api.get<AdminPerformanceOverview>("/api/admin/performance/overview"),
  });
}

export function useAdminAudit(params: { user_id?: number; tenant_id?: number; action?: string; limit?: number }) {
  return useQuery({
    queryKey: ["admin-audit", params],
    queryFn: () =>
      api.get<AuditEvent[]>("/api/audit/admin", {
        user_id: params.user_id,
        tenant_id: params.tenant_id,
        action: params.action,
        limit: params.limit ?? 200,
      }),
  });
}

export function useAdminTenantKillSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { tenant_id: number; reason: string }) =>
      api.post<KillSwitch>("/api/admin/kill-switch", vars),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });
}

export function useAdminCreatePartner() {
  return useMutation({
    mutationFn: (vars: { tenant_id: number; name: string; scopes?: string[] }) =>
      api.post<CreatePartnerRes>("/api/partner/admin/partners", vars),
  });
}
