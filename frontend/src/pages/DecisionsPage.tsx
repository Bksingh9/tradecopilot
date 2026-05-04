import { useState } from "react";

import { useDecide } from "@/api/queries";
import type { DecisionOutcome } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtMoney, fmtPct } from "@/lib/format";

export function DecisionsPage() {
  const decide = useDecide();
  const [symbols, setSymbols] = useState("RELIANCE.NS, TCS.NS");
  const [timeframe, setTimeframe] = useState("1d");
  const [error, setError] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<DecisionOutcome[]>([]);

  async function run() {
    setError(null);
    try {
      const res = await decide.mutateAsync({
        symbols: symbols.split(/[,\s]+/).filter(Boolean),
        timeframe,
      });
      setOutcomes(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Decisions</h1>
        <span className="text-xs text-muted">ML + RAG-aware cycle</span>
      </header>

      <Card title="Run a decision cycle" subtitle="Analyst → Strategy → Risk → Execution, biased by ML p_up.">
        <div className="grid md:grid-cols-3 gap-3 items-end">
          <Input label="Symbols" value={symbols} onChange={(e) => setSymbols(e.target.value)} className="md:col-span-2" />
          <Input label="Timeframe" value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
        </div>
        {error && <div className="text-bad text-xs mt-3">{error}</div>}
        <div className="mt-4 flex justify-end">
          <Button variant="primary" loading={decide.isPending} onClick={run}>Decide</Button>
        </div>
      </Card>

      {decide.isPending && (
        <div className="flex items-center gap-2 text-muted"><Spinner /> running cycle…</div>
      )}

      {outcomes.length === 0 && !decide.isPending ? (
        <Empty title="No decisions yet" hint="Trigger a cycle to see ML scores, retrieved similar regimes, and per-stage actions." />
      ) : (
        <ul className="space-y-4">
          {outcomes.map((o, i) => (
            <OutcomeCard key={i} o={o} />
          ))}
        </ul>
      )}
    </div>
  );
}

function OutcomeCard({ o }: { o: DecisionOutcome }) {
  const ctx = o.context;
  const p = ctx.prediction;
  const tendencies = (ctx.user_behavior_profile?.tendencies ?? {}) as Record<string, unknown>;
  const flags = Object.entries(tendencies).filter(([k, v]) => k.endsWith("_flag") && v === true);
  return (
    <Card
      title={
        <div className="flex items-center gap-2">
          <span className="font-mono">{ctx.symbol}</span>
          <Badge tone="muted">{ctx.timeframe}</Badge>
          <Badge tone={ctx.autonomy === "full_auto" ? "warn" : "muted"}>
            {ctx.autonomy.replace("_", "-")}
          </Badge>
        </div>
      }
      actions={
        <Badge tone="muted">model: {p.model_version}</Badge>
      }
    >
      <div className="grid md:grid-cols-4 gap-4 mb-4">
        <Stat label="P(up)" value={fmtPct(p.prob_up * 100)} />
        <Stat label="Risk score" value={p.risk_score.toFixed(2)} />
        <Stat label="Expected return" value={fmtPct(p.expected_return * 100, 2)} />
        <Stat label="ML confidence" value={fmtPct(Math.abs(p.prob_up - 0.5) * 200)} />
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <div>
          <div className="kpi-label mb-1">Similar historical windows</div>
          {ctx.similar_windows.length === 0 ? (
            <div className="text-xs text-muted">No matches yet — seed embeddings via <code>app/scripts/seed_embeddings.py</code>.</div>
          ) : (
            <ul className="text-sm">
              {ctx.similar_windows.slice(0, 3).map((s, i) => (
                <li key={i} className="flex items-center justify-between border-b border-line/60 py-1.5">
                  <div>
                    <span className="font-mono">{s.subject_id}</span>
                    {s.regime && <Badge tone="muted" className="ml-2">{s.regime}</Badge>}
                  </div>
                  <span className="text-xs text-muted">sim {(s.score * 100).toFixed(1)}%</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className="kpi-label mb-1">Behavior flags</div>
          {flags.length === 0 ? (
            <div className="text-xs text-muted">None tripped — keep doing what you're doing.</div>
          ) : (
            <ul className="space-y-1.5">
              {flags.map(([k]) => (
                <li key={k}><Badge tone="warn">{k.replace(/_flag$/, "").replace(/_/g, " ")}</Badge></li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {o.proposal && o.decision && o.execution && (
        <div className="border-t border-line pt-3">
          <table className="table">
            <thead>
              <tr>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Decision</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><Badge tone={o.proposal.candidate.side === "BUY" ? "good" : "bad"}>{o.proposal.candidate.side}</Badge></td>
                <td className="font-mono">{o.decision.final_qty}</td>
                <td className="font-mono">{fmtMoney(o.proposal.candidate.entry, ctx.symbol.endsWith(".NS") ? "INR" : "USD")}</td>
                <td>
                  <Badge tone={o.decision.action === "approve" ? "good" : o.decision.action === "scale_down" ? "warn" : "bad"}>
                    {o.decision.action}
                  </Badge>
                </td>
                <td>
                  <Badge tone={o.execution.status === "placed" ? "good" : o.execution.status === "proposed" ? "warn" : "muted"}>
                    {o.execution.status}
                  </Badge>
                </td>
                <td className="text-xs text-muted">{o.decision.reason}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="kpi-label">{label}</div>
      <div className="kpi font-mono">{value}</div>
    </div>
  );
}
