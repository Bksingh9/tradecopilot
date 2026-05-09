import { useState } from "react";
import {
  useDashboard,
  usePlaceOrder,
  useSummary,
  useWatchlist,
  useWatchlistAdd,
  useWatchlistRemove,
} from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { KillSwitchBanner } from "@/components/KillSwitchBanner";
import { RiskGauge } from "@/components/RiskGauge";
import { Spinner } from "@/components/Spinner";
import { fmtMoney, fmtPct, fmtSignedMoney, pnlClass } from "@/lib/format";

export function DashboardPage() {
  const { data, isLoading } = useDashboard();
  const { data: summary } = useSummary();

  if (isLoading || !data) {
    return <div className="flex items-center gap-2 text-muted"><Spinner /> loading dashboard…</div>;
  }

  const unrealized = data.unrealized_pnl ?? 0;
  const totalPnl = (data.realized_pnl_today ?? 0) + unrealized;

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <Badge tone={data.autonomy_mode === "full_auto" ? "warn" : "muted"}>
          autonomy: {data.autonomy_mode.replace("_", "-")}
        </Badge>
      </header>

      <KillSwitchBanner />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card title="Realized P&L (today)">
          <div className={`kpi font-mono ${pnlClass(data.realized_pnl_today)}`}>
            {fmtSignedMoney(data.realized_pnl_today)}
          </div>
          <div className="kpi-label mt-1">closed trades today</div>
        </Card>
        <Card title="Unrealized P&L">
          <div className={`kpi font-mono ${pnlClass(unrealized)}`}>
            {fmtSignedMoney(unrealized)}
          </div>
          <div className="kpi-label mt-1">mark-to-market on open positions</div>
        </Card>
        <Card title="Open positions">
          <div className="kpi font-mono">{data.open_positions_count}</div>
          <div className="kpi-label mt-1">
            ₹{(data.capital_deployed ?? 0).toLocaleString("en-IN")} deployed
          </div>
        </Card>
        <Card title="Risk used">
          <RiskGauge usedPct={data.risk_used_pct} />
          <div className="kpi-label mt-2">
            limit ≈ {fmtMoney(data.daily_loss_limit_value)} daily loss
          </div>
        </Card>
      </div>

      <PlaceOrderCard disabled={data.kill_switch_active} />

      {summary && (
        <Card title="Trailing performance" subtitle="across all trades on record">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <Stat label="Trades" value={String(summary.summary.trade_count)} />
            <Stat label="Win rate" value={fmtPct(summary.summary.win_rate * 100)} />
            <Stat label="Total P&L" value={fmtSignedMoney(summary.summary.total_pnl)}
                  className={pnlClass(summary.summary.total_pnl)} />
            <Stat label="Avg R" value={summary.summary.avg_r.toFixed(2)} />
            <Stat label="Today total" value={fmtSignedMoney(totalPnl)}
                  className={pnlClass(totalPnl)} />
          </div>
          <div className="mt-4 text-xs text-muted">
            Best hour: {summary.best_hour ?? "—"} · Worst hour: {summary.worst_hour ?? "—"} ·
            Streak (current): {summary.streaks.current}
          </div>
        </Card>
      )}

      <WatchlistCard watchlistQuotes={data.watchlist} />
    </div>
  );
}

function Stat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="kpi-label">{label}</div>
      <div className={`kpi font-mono ${className ?? ""}`}>{value}</div>
    </div>
  );
}

// --- Place Order ----------------------------------------------------------
function PlaceOrderCard({ disabled }: { disabled: boolean }) {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [exchange, setExchange] = useState("NSE");
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [strategy, setStrategy] = useState("manual");
  const [broker, setBroker] = useState("zerodha");
  const place = usePlaceOrder();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol || qty < 1) return;
    place.mutate(
      {
        broker,
        symbol: symbol.trim().toUpperCase(),
        exchange,
        side,
        qty,
        order_type: "MARKET",
        product: "CNC",
        strategy,
        paper: true,
      },
      {
        onSuccess: () => {
          // simple visual reset of qty so user can place another quickly
          setQty(1);
        },
      },
    );
  };

  return (
    <Card title="Place a paper order" subtitle="Risk-managed, audited, no real money">
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-7 gap-3 items-end">
        <div className="md:col-span-2">
          <label className="kpi-label mb-1 block">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="RELIANCE"
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1 font-mono"
          />
        </div>
        <div>
          <label className="kpi-label mb-1 block">Exchange</label>
          <select
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1"
          >
            <option value="NSE">NSE</option>
            <option value="BSE">BSE</option>
            <option value="US">US</option>
          </select>
        </div>
        <div>
          <label className="kpi-label mb-1 block">Side</label>
          <select
            value={side}
            onChange={(e) => setSide(e.target.value as "BUY" | "SELL")}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1"
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div>
          <label className="kpi-label mb-1 block">Qty</label>
          <input
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(Math.max(1, Number(e.target.value)))}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1 font-mono"
          />
        </div>
        <div>
          <label className="kpi-label mb-1 block">Broker</label>
          <select
            value={broker}
            onChange={(e) => setBroker(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1"
          >
            <option value="zerodha">Zerodha</option>
            <option value="upstox">Upstox</option>
            <option value="alpaca">Alpaca</option>
          </select>
        </div>
        <div>
          <label className="kpi-label mb-1 block">Strategy tag</label>
          <input
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1"
          />
        </div>
        <div>
          <button
            type="submit"
            disabled={disabled || place.isPending}
            className={`w-full px-3 py-1.5 rounded font-medium transition
              ${disabled
                ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                : side === "BUY"
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                  : "bg-rose-600 hover:bg-rose-500 text-white"
              }`}
          >
            {place.isPending ? "Placing…" : `${side} ${qty} ${symbol || "—"}`}
          </button>
        </div>
      </form>
      {place.isSuccess && place.data && (
        <div className="mt-3 text-sm text-emerald-400">
          Filled @ ₹{place.data.avg_price ?? "—"} · {place.data.broker_order_id}
        </div>
      )}
      {place.isError && (
        <div className="mt-3 text-sm text-rose-400">
          {(place.error as Error)?.message ?? "Order failed"}
        </div>
      )}
      {disabled && (
        <div className="mt-3 text-xs text-amber-400">
          Kill switch is active — clear it from the banner above to enable trading.
        </div>
      )}
    </Card>
  );
}

// --- Watchlist with add/remove --------------------------------------------
function WatchlistCard({ watchlistQuotes }: { watchlistQuotes: Array<{ symbol: string; ltp: number; currency?: string; source?: string }> }) {
  const [newSym, setNewSym] = useState("");
  const wl = useWatchlist();
  const add = useWatchlistAdd();
  const remove = useWatchlistRemove();
  const symbols = wl.data?.watchlist ?? [];

  const onAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSym.trim()) return;
    add.mutate(newSym.trim().toUpperCase(), {
      onSuccess: () => setNewSym(""),
    });
  };

  return (
    <Card title="Watchlist" subtitle="Symbols you're tracking">
      <form onSubmit={onAdd} className="flex gap-2 mb-3">
        <input
          value={newSym}
          onChange={(e) => setNewSym(e.target.value)}
          placeholder="Add symbol (e.g. WIPRO.NS)"
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded px-2 py-1 font-mono"
        />
        <button
          type="submit"
          disabled={add.isPending}
          className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 transition"
        >
          {add.isPending ? "Adding…" : "Add"}
        </button>
      </form>

      {symbols.length === 0 && watchlistQuotes.length === 0 ? (
        <Empty title="No watchlist symbols" hint="Add a symbol above to start tracking." />
      ) : (
        <ul className="space-y-1">
          {symbols.map((sym) => {
            const q = watchlistQuotes.find((x) => x.symbol.toUpperCase() === sym.toUpperCase());
            return (
              <li key={sym} className="flex items-center justify-between text-sm py-1 border-b border-zinc-900 last:border-0">
                <span className="font-mono">{sym}</span>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-muted">
                    {q ? fmtMoney(q.ltp, q.currency) : "—"}
                  </span>
                  <button
                    onClick={() => remove.mutate(sym)}
                    disabled={remove.isPending}
                    className="text-xs text-rose-400 hover:text-rose-300"
                  >
                    remove
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
