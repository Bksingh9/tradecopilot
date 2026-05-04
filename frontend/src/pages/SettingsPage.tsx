import { useEffect, useState } from "react";

import {
  useAutonomy,
  useFlattenNow,
  useQualifyPaper,
  useRisk,
  useRunCycle,
  useSetAutonomy,
  useUpdateRisk,
} from "@/api/queries";
import type { AutonomyMode, CycleReport } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input, Select } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtDate } from "@/lib/format";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <header><h1 className="text-xl font-semibold">Settings</h1></header>
      <AutonomySection />
      <RiskSection />
      <AgentSection />
    </div>
  );
}

function AutonomySection() {
  const { data, isLoading } = useAutonomy();
  const set = useSetAutonomy();
  const qualify = useQualifyPaper();
  const [mode, setMode] = useState<AutonomyMode>("advisory");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setMode(data.autonomy_mode);
      setConsent(data.consent_full_auto);
    }
  }, [data]);

  if (isLoading || !data) {
    return (
      <Card title="Autonomy">
        <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>
      </Card>
    );
  }

  async function save() {
    setError(null);
    try {
      await set.mutateAsync({ autonomy_mode: mode, consent_full_auto: consent });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card
      title="Autonomy"
      subtitle="Advisory proposes orders only. Semi-auto and full-auto place orders for you within risk caps."
      actions={<Badge tone={data.autonomy_mode === "full_auto" ? "warn" : "muted"}>
        current: {data.autonomy_mode.replace("_", "-")}
      </Badge>}
    >
      <div className="grid md:grid-cols-3 gap-3">
        <Select
          label="Mode"
          value={mode}
          onChange={(e) => setMode(e.target.value as AutonomyMode)}
          options={[
            { value: "advisory", label: "advisory" },
            { value: "semi_auto", label: "semi-auto" },
            { value: "full_auto", label: "full-auto (requires qualification)" },
          ]}
        />
        <div>
          <span className="label block mb-1">Paper qualification</span>
          <div className="flex items-center gap-2">
            {data.paper_qualified_at ? (
              <Badge tone="good">qualified · {fmtDate(data.paper_qualified_at)}</Badge>
            ) : (
              <Badge tone="muted">not qualified</Badge>
            )}
            {!data.paper_qualified_at && (
              <Button onClick={() => qualify.mutate()} loading={qualify.isPending}>
                Mark qualified
              </Button>
            )}
          </div>
        </div>
        <label className="flex items-center gap-2 mt-6">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-sm">Explicit consent for full-auto execution</span>
        </label>
      </div>
      {error && <div className="text-bad text-xs mt-3">{error}</div>}
      <div className="mt-4 flex justify-end">
        <Button variant="primary" loading={set.isPending} onClick={save}>Save</Button>
      </div>
    </Card>
  );
}

function RiskSection() {
  const { data, isLoading } = useRisk();
  const update = useUpdateRisk();
  const [maxRisk, setMaxRisk] = useState(1.0);
  const [dailyLoss, setDailyLoss] = useState(3.0);
  const [maxOpen, setMaxOpen] = useState(5);
  const [equity, setEquity] = useState(100_000);
  const [paperOnly, setPaperOnly] = useState(true);
  const [restrictedText, setRestrictedText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setMaxRisk(data.max_risk_per_trade_pct);
      setDailyLoss(data.daily_loss_limit_pct);
      setMaxOpen(data.max_open_positions);
      setEquity(data.starting_equity);
      setPaperOnly(data.paper_only);
      setRestrictedText((data.restricted_symbols ?? []).join(", "));
    }
  }, [data]);

  if (isLoading || !data) {
    return <Card title="Risk rules"><div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div></Card>;
  }

  async function save() {
    setError(null);
    try {
      await update.mutateAsync({
        max_risk_per_trade_pct: maxRisk,
        daily_loss_limit_pct: dailyLoss,
        max_open_positions: maxOpen,
        starting_equity: equity,
        paper_only: paperOnly,
        restricted_symbols: restrictedText.split(/[,\s]+/).filter(Boolean).map((s) => s.toUpperCase()),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card
      title="Risk rules"
      subtitle="Env-driven hard caps still apply on top of these. AI cannot loosen them."
    >
      <div className="grid md:grid-cols-3 gap-3">
        <Input label="Max risk per trade (%)" type="number" step="0.1" min={0.1}
               value={maxRisk} onChange={(e) => setMaxRisk(Number(e.target.value))} />
        <Input label="Daily loss limit (%)" type="number" step="0.1" min={0.1}
               value={dailyLoss} onChange={(e) => setDailyLoss(Number(e.target.value))} />
        <Input label="Max open positions" type="number" min={1}
               value={maxOpen} onChange={(e) => setMaxOpen(Number(e.target.value))} />
        <Input label="Starting equity" type="number" min={0}
               value={equity} onChange={(e) => setEquity(Number(e.target.value))} />
        <label className="flex items-center gap-2 mt-6">
          <input type="checkbox" checked={paperOnly} onChange={(e) => setPaperOnly(e.target.checked)} className="h-4 w-4" />
          <span className="text-sm">Paper-only (block live orders)</span>
        </label>
        <Input label="Restricted symbols" placeholder="e.g. NIFTY, BANKNIFTY"
               value={restrictedText} onChange={(e) => setRestrictedText(e.target.value)}
               className="md:col-span-3" />
      </div>
      {error && <div className="text-bad text-xs mt-3">{error}</div>}
      <div className="mt-4 flex justify-end">
        <Button variant="primary" loading={update.isPending} onClick={save}>Save</Button>
      </div>
    </Card>
  );
}

function AgentSection() {
  const cycle = useRunCycle();
  const flatten = useFlattenNow();
  const [symbols, setSymbols] = useState("RELIANCE.NS, TCS.NS");
  const [report, setReport] = useState<CycleReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null);
    try {
      const r = await cycle.mutateAsync({
        symbols: symbols.split(/[,\s]+/).filter(Boolean),
      });
      setReport(r);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Agent controls" subtitle="Run a cycle (Analyst → Strategy → Risk → Execution) or flatten everything now.">
      <div className="grid md:grid-cols-3 gap-3 items-end">
        <Input label="Symbols (comma-separated)"
               value={symbols} onChange={(e) => setSymbols(e.target.value)}
               className="md:col-span-2" />
        <div className="flex gap-2 justify-end">
          <Button variant="primary" loading={cycle.isPending} onClick={run}>Run cycle</Button>
          <Button variant="danger" loading={flatten.isPending}
                  onClick={() => {
                    if (confirm("Flatten all open positions for closed exchanges?")) {
                      flatten.mutate();
                    }
                  }}>Flatten now</Button>
        </div>
      </div>

      {error && <div className="text-bad text-xs mt-3">{error}</div>}

      {report && (
        <div className="mt-4 border-t border-line pt-3">
          <div className="text-xs text-muted mb-2">
            Cycle for {fmtDate(report.started_at)} · mode {report.mode} · {report.results.length} result(s)
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Stage</th>
                <th>OK</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {report.stages.map((s, i) => (
                <tr key={i}>
                  <td className="text-xs">{s.stage}</td>
                  <td>{s.ok ? <Badge tone="good">ok</Badge> : <Badge tone="bad">no</Badge>}</td>
                  <td className="text-xs text-slate-300">{s.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {report.results.length > 0 && (
            <table className="table mt-3">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Decision</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {report.results.map((r, i) => (
                  <tr key={i}>
                    <td className="font-mono">{r.candidate.symbol}</td>
                    <td><Badge tone={r.candidate.side === "BUY" ? "good" : "bad"}>{r.candidate.side}</Badge></td>
                    <td><Badge tone={r.decision.action === "approve" ? "good"
                      : r.decision.action === "scale_down" ? "warn" : "bad"}>{r.decision.action}</Badge></td>
                    <td><Badge tone={r.status === "placed" ? "good"
                      : r.status === "proposed" ? "warn" : "muted"}>{r.status}</Badge></td>
                    <td className="text-xs text-muted">{r.decision.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Card>
  );
}
