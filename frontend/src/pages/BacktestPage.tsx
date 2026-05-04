import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useBacktestRun, useBacktestRuns, useRunBacktest } from "@/api/queries";
import type { BacktestRun } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input, Select } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtDate, fmtPct, fmtSignedMoney } from "@/lib/format";

export function BacktestPage() {
  const runs = useBacktestRuns();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Backtest</h1>
      </header>

      <NewRunCard onCreated={(id) => setSelectedId(id)} />

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
        <Card pad={false} title="Runs" subtitle={runs.data ? `${runs.data.length}` : undefined}>
          {!runs.data ? (
            <div className="p-4 flex items-center gap-2 text-muted"><Spinner /> loading…</div>
          ) : runs.data.length === 0 ? (
            <Empty title="No runs yet" />
          ) : (
            <ul className="divide-y divide-line/60 max-h-[500px] overflow-auto">
              {runs.data.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setSelectedId(r.id)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-ink-700/60 ${
                      selectedId === r.id ? "bg-ink-700" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono">#{r.id} {r.strategy}</div>
                      <Badge tone={runStatusTone(r.status)}>{r.status}</Badge>
                    </div>
                    <div className="text-xs text-muted mt-0.5">{fmtDate(r.created_at)}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <RunDetail id={selectedId} />
      </div>
    </div>
  );
}

function runStatusTone(s: BacktestRun["status"]): "good" | "bad" | "warn" | "muted" {
  if (s === "done") return "good";
  if (s === "failed") return "bad";
  if (s === "running") return "warn";
  return "muted";
}

function NewRunCard({ onCreated }: { onCreated: (id: number) => void }) {
  const run = useRunBacktest();
  const [strategy, setStrategy] = useState("momentum");
  const [symbols, setSymbols] = useState("RELIANCE.NS");
  const [start, setStart] = useState(() => isoDaysAgo(365));
  const [end, setEnd] = useState(() => isoDaysAgo(0));
  const [folds, setFolds] = useState(4);
  const [paramsText, setParamsText] = useState('{"fast": [9, 12], "slow": [21, 26]}');
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let grid: Record<string, unknown> = {};
    try {
      grid = JSON.parse(paramsText);
    } catch {
      setError("param_grid must be valid JSON");
      return;
    }
    try {
      const res = await run.mutateAsync({
        strategy,
        config: {
          symbols: symbols.split(/[,\s]+/).filter(Boolean),
          timeframe: "1d",
          start: new Date(start).toISOString(),
          end: new Date(end).toISOString(),
          walk_forward_folds: folds,
          param_grid: grid,
        },
      });
      onCreated(res.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="New walk-forward run" subtitle="Reports only what was actually computed. No fabricated metrics.">
      <form onSubmit={onSubmit} className="grid md:grid-cols-3 gap-3">
        <Select
          label="Strategy"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          options={[
            { value: "momentum", label: "momentum" },
            { value: "mean_reversion", label: "mean_reversion" },
            { value: "orb", label: "orb" },
          ]}
        />
        <Input label="Symbols" placeholder="RELIANCE.NS, TCS.NS"
               value={symbols} onChange={(e) => setSymbols(e.target.value)} />
        <Input label="Folds" type="number" min={1} max={20}
               value={folds} onChange={(e) => setFolds(Number(e.target.value))} />
        <Input label="Start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input label="End" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <Input label="Param grid (JSON)" value={paramsText}
               onChange={(e) => setParamsText(e.target.value)} error={error} />
        <div className="md:col-span-3 flex justify-end">
          <Button variant="primary" type="submit" loading={run.isPending}>Queue run</Button>
        </div>
      </form>
    </Card>
  );
}

function isoDaysAgo(d: number): string {
  const t = new Date();
  t.setDate(t.getDate() - d);
  return t.toISOString().slice(0, 10);
}

function RunDetail({ id }: { id: number | null }) {
  const { data } = useBacktestRun(id);

  if (id == null) return (
    <Card title="Result"><Empty title="Pick a run" hint="Or queue a new one above." /></Card>
  );
  if (!data) return (
    <Card title="Result"><div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div></Card>
  );

  const m = (data.metrics_json?.metrics as Record<string, unknown>) ?? {};
  const byRegime = (m.by_regime as Record<string, Record<string, number>> | undefined) ?? {};
  const chartData = useChartData(byRegime);

  return (
    <Card title={`Run #${data.id} · ${data.strategy}`}
          subtitle={`${fmtDate(data.created_at)} → ${data.finished_at ? fmtDate(data.finished_at) : "running…"}`}
          actions={<Badge tone={runStatusTone(data.status)}>{data.status}</Badge>}>
      {data.status === "failed" && data.error && (
        <div className="text-bad text-sm mb-3 whitespace-pre-wrap">{data.error}</div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <Stat label="CAGR" value={fmtPct(num(m.cagr) * 100)} />
        <Stat label="Sharpe" value={num(m.sharpe).toFixed(2)} />
        <Stat label="Max DD" value={fmtPct(num(m.max_dd) * 100)} />
        <Stat label="Win rate" value={fmtPct(num(m.win_rate) * 100)} />
        <Stat label="Profit factor" value={num(m.profit_factor).toFixed(2)} />
        <Stat label="Trades" value={String(num(m.trade_count))} />
        <Stat label="Avg R" value={num(m.avg_r).toFixed(2)} />
        <Stat label="Total P&L" value={fmtSignedMoney(num(m.total_pnl))} />
      </div>

      {chartData.length > 0 && (
        <>
          <h3 className="text-sm font-medium text-slate-200 mt-2 mb-2">Per-regime trades & P&L</h3>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={chartData}>
                <CartesianGrid stroke="#243042" strokeDasharray="3 3" />
                <XAxis dataKey="regime" stroke="#7e8a9a" fontSize={12} />
                <YAxis yAxisId="left" stroke="#7e8a9a" fontSize={12} />
                <YAxis yAxisId="right" orientation="right" stroke="#7e8a9a" fontSize={12} />
                <Tooltip contentStyle={{ background: "#11151a", border: "1px solid #243042" }} />
                <Bar yAxisId="left" dataKey="trades" fill="#5fa8ff" />
                <Bar yAxisId="right" dataKey="pnl" fill="#22c55e" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {data.status === "done" && (
        <p className="text-[11px] text-muted mt-4">
          Past performance and backtest results are not indicative of future results.
        </p>
      )}
    </Card>
  );
}

function useChartData(byRegime: Record<string, Record<string, number>>) {
  return useMemo(
    () => Object.entries(byRegime).map(([regime, m]) => ({
      regime,
      trades: Number(m.trade_count ?? 0),
      pnl: Number(m.total_pnl ?? 0),
    })),
    [byRegime],
  );
}

function num(v: unknown): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="kpi-label">{label}</div>
      <div className="kpi font-mono">{value}</div>
    </div>
  );
}
