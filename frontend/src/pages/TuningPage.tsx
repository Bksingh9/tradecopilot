import { useState } from "react";

import { useRequestTuning, useReviewTuning, useTuningSuggestions } from "@/api/queries";
import type { TuningSuggestion } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input, Select } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtDate } from "@/lib/format";

export function TuningPage() {
  const list = useTuningSuggestions();
  const review = useReviewTuning();

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Strategy tuning suggestions</h1>
      </header>

      <RequestSuggestionCard />

      <Card title="Pending & past suggestions">
        {!list.data ? (
          <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>
        ) : list.data.length === 0 ? (
          <Empty title="No tuning suggestions yet"
                 hint='AI-generated tweaks land here as "pending". You decide whether to accept.' />
        ) : (
          <ul className="space-y-3">
            {list.data.map((s) => (
              <SuggestionRow key={s.id} s={s} onAction={(action) => review.mutate({ id: s.id, action })} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function SuggestionRow({ s, onAction }: { s: TuningSuggestion; onAction: (a: "accept" | "reject") => void }) {
  const tone = s.status === "pending" ? "warn" : s.status === "accepted" ? "good" : "muted";
  return (
    <li className="border border-line rounded-lg p-3">
      <div className="flex items-center justify-between">
        <div>
          <Badge tone={tone}>{s.status}</Badge>
          <span className="ml-2 text-sm font-medium">{s.strategy}</span>
          <span className="ml-3 text-xs text-muted">{fmtDate(s.created_at)}</span>
        </div>
        {s.status === "pending" && (
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => onAction("accept")}>Accept</Button>
            <Button onClick={() => onAction("reject")}>Reject</Button>
          </div>
        )}
      </div>
      <div className="mt-3 grid md:grid-cols-2 gap-3">
        <ParamBlock title="Current" data={s.current_params} />
        <ParamBlock title="Suggested" data={s.suggested_params} highlight />
      </div>
      {s.rationale && (
        <div className="mt-3 text-sm text-slate-300 whitespace-pre-wrap">{s.rationale}</div>
      )}
    </li>
  );
}

function ParamBlock({ title, data, highlight }: { title: string; data: Record<string, unknown>; highlight?: boolean }) {
  return (
    <div className={`rounded-md p-2 border ${highlight ? "border-accent/40 bg-accent/5" : "border-line"}`}>
      <div className="kpi-label mb-1">{title}</div>
      <pre className="text-xs font-mono whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

function RequestSuggestionCard() {
  const req = useRequestTuning();
  const [strategy, setStrategy] = useState("momentum");
  const [paramsText, setParamsText] = useState('{"fast": 9, "slow": 21}');
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(paramsText);
    } catch {
      setError("current_params must be valid JSON");
      return;
    }
    try {
      await req.mutateAsync({ strategy, current_params: parsed });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Request a new tuning review"
          subtitle="The AI proposes parameter tweaks only; you must explicitly accept them.">
      <form onSubmit={onSubmit} className="grid md:grid-cols-3 gap-3 items-end">
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
        <Input
          label="Current params (JSON)"
          value={paramsText}
          onChange={(e) => setParamsText(e.target.value)}
          className="md:col-span-2"
          error={error}
        />
        <div className="md:col-span-3 flex justify-end">
          <Button variant="primary" type="submit" loading={req.isPending}>Request review</Button>
        </div>
      </form>
    </Card>
  );
}
