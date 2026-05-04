import { useAIReports, useGenerateWeekly } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Spinner } from "@/components/Spinner";
import { fmtDate } from "@/lib/format";

export function CoachPage() {
  const list = useAIReports();
  const generate = useGenerateWeekly();

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">AI coach</h1>
        <Button variant="primary" loading={generate.isPending} onClick={() => generate.mutate(7)}>
          Generate weekly report
        </Button>
      </header>

      {!list.data ? (
        <div className="flex items-center gap-2 text-muted"><Spinner /> loading reports…</div>
      ) : list.data.length === 0 ? (
        <Empty title="No AI reports yet" hint='Click "Generate weekly report" to create one.' />
      ) : (
        <ul className="space-y-4">
          {list.data.map((r) => (
            <Card key={r.id} title={
              <div className="flex items-center gap-2">
                <span>Report #{r.id}</span>
                <Badge tone="muted">{r.kind}</Badge>
              </div>
            } subtitle={`${fmtDate(r.period_start)} → ${fmtDate(r.period_end)} · created ${fmtDate(r.created_at)}`}>
              <article className="prose prose-invert max-w-none">
                <pre className="whitespace-pre-wrap text-sm font-sans bg-transparent p-0 m-0">{r.content}</pre>
              </article>
            </Card>
          ))}
        </ul>
      )}
    </div>
  );
}
