import { useDashboard, useSummary } from "@/api/queries";
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

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <Badge tone={data.autonomy_mode === "full_auto" ? "warn" : "muted"}>
          autonomy: {data.autonomy_mode.replace("_", "-")}
        </Badge>
      </header>

      <KillSwitchBanner />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="Today's realized P&L">
          <div className={`kpi font-mono ${pnlClass(data.realized_pnl_today)}`}>
            {fmtSignedMoney(data.realized_pnl_today)}
          </div>
          <div className="kpi-label mt-1">across all closed trades today</div>
        </Card>
        <Card title="Open positions">
          <div className="kpi font-mono">{data.open_positions_count}</div>
          <div className="kpi-label mt-1">currently in market</div>
        </Card>
        <Card title="Risk used">
          <RiskGauge usedPct={data.risk_used_pct} />
          <div className="kpi-label mt-2">
            limit ≈ {fmtMoney(data.daily_loss_limit_value)} (after env hard caps)
          </div>
        </Card>
      </div>

      {summary && (
        <Card title="Trailing performance" subtitle="across all trades on record">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Trades" value={String(summary.summary.trade_count)} />
            <Stat label="Win rate" value={fmtPct(summary.summary.win_rate * 100)} />
            <Stat label="Total P&L" value={fmtSignedMoney(summary.summary.total_pnl)}
                  className={pnlClass(summary.summary.total_pnl)} />
            <Stat label="Avg R" value={summary.summary.avg_r.toFixed(2)} />
          </div>
          <div className="mt-4 text-xs text-muted">
            Best hour: {summary.best_hour ?? "—"} · Worst hour: {summary.worst_hour ?? "—"} ·
            Streak (current): {summary.streaks.current}
          </div>
        </Card>
      )}

      <Card title="Watchlist">
        {data.watchlist.length === 0 ? (
          <Empty title="No watchlist symbols" hint="Add some on the Settings page." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>LTP</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {data.watchlist.map((q) => (
                <tr key={`${q.symbol}-${q.source}`}>
                  <td className="font-mono">{q.symbol}{q.exchange ? `.${q.exchange}` : ""}</td>
                  <td className="font-mono">{fmtMoney(q.ltp, q.currency)}</td>
                  <td className="font-mono">{fmtMoney(q.open ?? null, q.currency)}</td>
                  <td className="font-mono">{fmtMoney(q.high ?? null, q.currency)}</td>
                  <td className="font-mono">{fmtMoney(q.low ?? null, q.currency)}</td>
                  <td className="text-xs text-muted">{q.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
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
