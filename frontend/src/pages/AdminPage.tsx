import { useState } from "react";
import { Navigate } from "react-router-dom";

import {
  useAdminAudit,
  useAdminCreatePartner,
  useAdminPerformance,
  useAdminTenantKillSwitch,
  useAdminUsers,
  useMe,
} from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Input } from "@/components/Input";
import { Spinner } from "@/components/Spinner";
import { cn } from "@/lib/cn";
import { fmtDate, fmtPct, fmtSignedMoney, fmtTimeAgo, pnlClass } from "@/lib/format";

type Tab = "overview" | "users" | "audit" | "kill" | "partners";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "users", label: "Users" },
  { id: "audit", label: "Audit" },
  { id: "kill", label: "Kill switch" },
  { id: "partners", label: "Partners" },
];

export function AdminPage() {
  const me = useMe();
  const [tab, setTab] = useState<Tab>("overview");

  if (me.isLoading) return <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>;
  if (!me.data || me.data.role !== "admin") return <Navigate to="/" replace />;

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Admin</h1>
        <Badge tone="warn">{me.data.email}</Badge>
      </header>

      <div className="border-b border-line flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-3 py-2 text-sm border-b-2 -mb-px",
              tab === t.id
                ? "border-accent text-slate-100"
                : "border-transparent text-slate-300 hover:text-slate-100",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "users" && <UsersTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "kill" && <KillSwitchTab />}
      {tab === "partners" && <PartnersTab />}
    </div>
  );
}

// -- Overview ---------------------------------------------------------------
function OverviewTab() {
  const { data, isLoading } = useAdminPerformance();
  if (isLoading || !data) return <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>;
  return (
    <div className="space-y-4">
      <Card title="Anonymized performance overview" subtitle="No PII; aggregate counts and summary stats only.">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
          <Stat label="Trades" value={String(data.trade_count)} />
          <Stat label="Closed" value={String(data.closed_count)} />
          <Stat label="Win rate" value={fmtPct(data.win_rate * 100)} />
          <Stat label="Total P&L" value={fmtSignedMoney(data.total_pnl)} className={pnlClass(data.total_pnl)} />
          <Stat label="Avg P&L" value={fmtSignedMoney(data.avg_pnl)} />
          <Stat label="Median P&L" value={fmtSignedMoney(data.median_pnl)} />
          <Stat label="Tenants" value={String(data.tenants_with_activity)} />
          <Stat label="Users" value={String(data.users_with_activity)} />
        </div>
      </Card>

      <Card title="By strategy">
        {Object.keys(data.by_strategy).length === 0 ? (
          <Empty title="No strategy activity yet" />
        ) : (
          <table className="table">
            <thead>
              <tr><th>Strategy</th><th>Count</th><th>Win rate</th><th>Total P&L</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.by_strategy).map(([k, v]) => (
                <tr key={k}>
                  <td className="font-mono">{k}</td>
                  <td className="font-mono">{v.count}</td>
                  <td className="font-mono">{fmtPct(v.win_rate * 100)}</td>
                  <td className={`font-mono ${pnlClass(v.total_pnl)}`}>{fmtSignedMoney(v.total_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

// -- Users ------------------------------------------------------------------
function UsersTab() {
  const users = useAdminUsers();
  if (users.isLoading || !users.data) return <div className="flex items-center gap-2 text-muted"><Spinner /> loading…</div>;
  return (
    <Card title={`Users (${users.data.length})`}>
      <table className="table">
        <thead>
          <tr><th>#</th><th>Email</th><th>Tenant</th><th>Role</th><th>Autonomy</th><th>Active</th></tr>
        </thead>
        <tbody>
          {users.data.map((u) => (
            <tr key={u.id}>
              <td className="text-muted">{u.id}</td>
              <td>{u.email}</td>
              <td className="font-mono">{u.tenant_id}</td>
              <td><Badge tone={u.role === "admin" ? "warn" : "muted"}>{u.role}</Badge></td>
              <td><Badge tone={u.autonomy_mode === "full_auto" ? "warn" : "muted"}>{u.autonomy_mode}</Badge></td>
              <td>{u.is_active ? <Badge tone="good">yes</Badge> : <Badge tone="bad">no</Badge>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// -- Audit ------------------------------------------------------------------
function AuditTab() {
  const [userId, setUserId] = useState<string>("");
  const [action, setAction] = useState<string>("");
  const params = {
    user_id: userId ? Number(userId) : undefined,
    action: action || undefined,
    limit: 200,
  };
  const audit = useAdminAudit(params);

  return (
    <div className="space-y-4">
      <Card title="Filter">
        <div className="grid md:grid-cols-3 gap-3">
          <Input label="user_id" type="number" value={userId} onChange={(e) => setUserId(e.target.value)} />
          <Input label="action contains" value={action} onChange={(e) => setAction(e.target.value)} />
        </div>
      </Card>
      <Card pad={false} title="Events">
        {audit.isLoading || !audit.data ? (
          <div className="p-4 flex items-center gap-2 text-muted"><Spinner /> loading…</div>
        ) : audit.data.length === 0 ? (
          <Empty title="No events" />
        ) : (
          <ul className="divide-y divide-line/60">
            {audit.data.map((e) => (
              <li key={e.id} className="px-4 py-3 flex items-start gap-3">
                <Badge tone={e.action.startsWith("kill_switch") ? "bad" : e.action.startsWith("agent.") ? "warn" : "muted"}>
                  {e.actor}
                </Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm">
                    <span className="font-medium">{e.action}</span>
                    {e.subject_type && (
                      <span className="text-muted"> · {e.subject_type} {e.subject_id ?? ""}</span>
                    )}
                    <span className="text-muted"> · user {e.user_id ?? "—"} · tenant {e.tenant_id}</span>
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

// -- Kill switch ------------------------------------------------------------
function KillSwitchTab() {
  const trigger = useAdminTenantKillSwitch();
  const [tenantId, setTenantId] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<{ id: number; tenant_id: number } | null>(null);

  async function fire() {
    setError(null);
    try {
      const r = await trigger.mutateAsync({ tenant_id: Number(tenantId), reason });
      setLast({ id: r.id, tenant_id: r.tenant_id });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Tenant-wide kill switch"
          subtitle="Blocks every new order for every user in the tenant until cleared.">
      <div className="grid md:grid-cols-3 gap-3 items-end">
        <Input label="tenant_id" type="number" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
        <Input label="reason" value={reason} onChange={(e) => setReason(e.target.value)} className="md:col-span-2" />
      </div>
      {error && <div className="text-bad text-xs mt-2">{error}</div>}
      <div className="mt-4 flex justify-end">
        <Button variant="danger" loading={trigger.isPending}
                disabled={!tenantId || !reason}
                onClick={() => {
                  if (confirm(`Trigger tenant ${tenantId} kill switch? Reason: "${reason}"`)) fire();
                }}>
          Trigger
        </Button>
      </div>
      {last && (
        <div className="mt-3 text-xs text-muted">
          Last action: kill switch <span className="font-mono">#{last.id}</span> on tenant <span className="font-mono">{last.tenant_id}</span>.
          Clear via <span className="font-mono">POST /api/admin/kill-switch/{last.id}/clear</span>.
        </div>
      )}
    </Card>
  );
}

// -- Partners ---------------------------------------------------------------
function PartnersTab() {
  const create = useAdminCreatePartner();
  const [tenantId, setTenantId] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [scopes, setScopes] = useState<string>("users, trades");
  const [issued, setIssued] = useState<{ partner_id: number; api_key: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    setError(null);
    try {
      const r = await create.mutateAsync({
        tenant_id: Number(tenantId),
        name,
        scopes: scopes.split(/[,\s]+/).filter(Boolean),
      });
      setIssued(r);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Provision a partner" subtitle="Issues a one-shot API key. Save it now — it is not stored in plaintext.">
      <div className="grid md:grid-cols-3 gap-3">
        <Input label="tenant_id" type="number" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
        <Input label="Partner name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Scopes" value={scopes} onChange={(e) => setScopes(e.target.value)} />
      </div>
      {error && <div className="text-bad text-xs mt-2">{error}</div>}
      <div className="mt-4 flex justify-end">
        <Button variant="primary" loading={create.isPending} disabled={!tenantId || !name} onClick={go}>
          Issue API key
        </Button>
      </div>
      {issued && (
        <div className="mt-4 border border-warn/40 bg-warn/10 text-slate-100 rounded-md p-3 text-sm">
          <div className="font-medium mb-1">Partner #{issued.partner_id} — copy this key now:</div>
          <code className="block font-mono break-all bg-ink-900 border border-line rounded p-2">{issued.api_key}</code>
        </div>
      )}
    </Card>
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
