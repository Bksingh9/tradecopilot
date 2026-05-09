import { useMemo, useState } from "react";

import { useAddJournalEntry, useClosePosition, useJournalEntries, useTrades } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input, Select, Textarea } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtDate, fmtMoney, fmtSignedMoney, pnlClass } from "@/lib/format";

export function TradesPage() {
  const [status, setStatus] = useState<string>("");
  const [symbol, setSymbol] = useState<string>("");
  const [strategy, setStrategy] = useState<string>("");

  const filters = useMemo(
    () => ({
      status: status || undefined,
      symbol: symbol || undefined,
      strategy: strategy || undefined,
    }),
    [status, symbol, strategy],
  );

  const { data: trades, isLoading } = useTrades(filters);
  const close = useClosePosition();

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trades & Journal</h1>
      </header>

      <Card title="Filters">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[
              { value: "", label: "All" },
              { value: "OPEN", label: "Open" },
              { value: "CLOSED", label: "Closed" },
              { value: "CANCELLED", label: "Cancelled" },
            ]}
          />
          <Input label="Symbol" placeholder="RELIANCE" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          <Input label="Strategy" placeholder="momentum" value={strategy} onChange={(e) => setStrategy(e.target.value)} />
        </div>
      </Card>

      <Card title="Trades" subtitle={trades ? `${trades.length} row(s)` : undefined}>
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>
        ) : !trades || trades.length === 0 ? (
          <Empty title="No trades yet" hint="Run a cycle from Settings, or push trades via the partner API." />
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Qty</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>P&L</th>
                  <th>R</th>
                  <th>Strategy</th>
                  <th>Status</th>
                  <th>Opened</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id}>
                    <td className="text-muted">{t.id}</td>
                    <td className="font-mono">{t.symbol}{t.exchange ? `.${t.exchange}` : ""}</td>
                    <td>
                      <Badge tone={t.side === "BUY" ? "good" : "bad"}>{t.side}</Badge>
                    </td>
                    <td className="font-mono">{t.qty}</td>
                    <td className="font-mono">{fmtMoney(t.entry_price, t.exchange === "US" ? "USD" : "INR")}</td>
                    <td className="font-mono">{fmtMoney(t.exit_price ?? null, t.exchange === "US" ? "USD" : "INR")}</td>
                    <td className={`font-mono ${pnlClass(t.realized_pnl ?? null)}`}>
                      {fmtSignedMoney(t.realized_pnl ?? null, t.exchange === "US" ? "USD" : "INR")}
                    </td>
                    <td className="font-mono">{t.r_multiple != null ? t.r_multiple.toFixed(2) : "—"}</td>
                    <td className="text-xs">{t.strategy ?? "—"}</td>
                    <td>
                      <Badge tone={t.status === "OPEN" ? "warn" : t.status === "CLOSED" ? "muted" : "muted"}>
                        {t.status}
                      </Badge>
                    </td>
                    <td className="text-xs text-muted">{fmtDate(t.opened_at)}</td>
                    <td>
                      {t.status === "OPEN" ? (
                        <button
                          onClick={() => close.mutate(t.id)}
                          disabled={close.isPending}
                          className="px-2 py-0.5 text-xs rounded bg-rose-600/80 hover:bg-rose-500 text-white transition disabled:opacity-50"
                        >
                          {close.isPending && close.variables === t.id ? "…" : "Close"}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <JournalSection />
    </div>
  );
}

function JournalSection() {
  const entries = useJournalEntries();
  const add = useAddJournalEntry();
  const [tradeId, setTradeId] = useState<string>("");
  const [setup, setSetup] = useState<string>("");
  const [emotion, setEmotion] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({
        trade_id: tradeId ? Number(tradeId) : null,
        setup: setup || null,
        emotion_tag: emotion || null,
        notes: notes || null,
      });
      setTradeId(""); setSetup(""); setEmotion(""); setNotes("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="New journal entry">
        <form onSubmit={onSubmit} className="space-y-3">
          <Input label="Trade ID (optional)" type="number" min={1}
                 value={tradeId} onChange={(e) => setTradeId(e.target.value)} />
          <Input label="Setup" placeholder="ORB long, VWAP reclaim..." value={setup}
                 onChange={(e) => setSetup(e.target.value)} />
          <Select
            label="Emotion"
            value={emotion}
            onChange={(e) => setEmotion(e.target.value)}
            options={[
              { value: "", label: "—" },
              { value: "calm", label: "calm" },
              { value: "fomo", label: "fomo" },
              { value: "revenge", label: "revenge" },
              { value: "fear", label: "fear" },
              { value: "greed", label: "greed" },
            ]}
          />
          <Textarea label="Notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
          {error && <div className="text-bad text-xs">{error}</div>}
          <Button variant="primary" type="submit" loading={add.isPending}>Save entry</Button>
        </form>
      </Card>
      <Card title="Recent entries" subtitle={entries.data ? `${entries.data.length} entries` : undefined}>
        {!entries.data ? (
          <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>
        ) : entries.data.length === 0 ? (
          <Empty title="No journal entries yet" hint="Tag your trades — patterns emerge fast." />
        ) : (
          <ul className="divide-y divide-line/60">
            {entries.data.map((e) => (
              <li key={e.id} className="py-3">
                <div className="text-xs text-muted">{fmtDate(e.created_at)} · trade #{e.trade_id ?? "—"}</div>
                <div className="text-sm mt-1">
                  {e.setup && <Badge className="mr-2">{e.setup}</Badge>}
                  {e.emotion_tag && <Badge tone="warn">{e.emotion_tag}</Badge>}
                </div>
                {e.notes && <div className="text-sm text-slate-300 mt-1 whitespace-pre-wrap">{e.notes}</div>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
