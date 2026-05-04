import { useMemo, useState } from "react";

import { useMyAudit } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { fmtDate, fmtTimeAgo } from "@/lib/format";

export function AuditPage() {
  const { data, isLoading } = useMyAudit(200);
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!q.trim()) return data;
    const needle = q.trim().toLowerCase();
    return data.filter((e) =>
      e.action.toLowerCase().includes(needle) ||
      e.actor.toLowerCase().includes(needle) ||
      (e.subject_type ?? "").toLowerCase().includes(needle) ||
      JSON.stringify(e.payload).toLowerCase().includes(needle),
    );
  }, [data, q]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Audit timeline</h1>
        <span className="text-xs text-muted">{filtered.length} event(s)</span>
      </header>

      <Card title="Filter">
        <Input placeholder="action / actor / payload contains…" value={q}
               onChange={(e) => setQ(e.target.value)} />
      </Card>

      <Card pad={false} title="Events">
        {isLoading ? (
          <div className="p-4 flex items-center gap-2 text-muted"><Spinner /> loading…</div>
        ) : filtered.length === 0 ? (
          <Empty title="No matching events" />
        ) : (
          <ul className="divide-y divide-line/60">
            {filtered.map((e) => (
              <li key={e.id} className="px-4 py-3 flex items-start gap-3">
                <Badge tone={tone(e.action)}>{e.actor}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm">
                    <span className="font-medium">{e.action}</span>
                    {e.subject_type && (
                      <span className="text-muted"> · {e.subject_type} {e.subject_id ?? ""}</span>
                    )}
                  </div>
                  {Object.keys(e.payload || {}).length > 0 && (
                    <pre className="text-xs font-mono text-muted mt-1 whitespace-pre-wrap">
                      {JSON.stringify(e.payload, null, 0)}
                    </pre>
                  )}
                </div>
                <div className="text-xs text-muted whitespace-nowrap" title={fmtDate(e.at)}>
                  {fmtTimeAgo(e.at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function tone(action: string): "good" | "bad" | "warn" | "muted" {
  if (action.startsWith("kill_switch")) return "bad";
  if (action === "tuning.accepted" || action === "agent.execution.placed") return "good";
  if (action.startsWith("agent.")) return "warn";
  return "muted";
}
