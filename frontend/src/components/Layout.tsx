import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAutonomy, useHealth, useMe } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/cn";
import { Badge } from "./Badge";
import { Disclaimer } from "./Disclaimer";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/decisions", label: "Decisions" },
  { to: "/trades", label: "Trades & Journal" },
  { to: "/tuning", label: "Tuning" },
  { to: "/coach", label: "AI Coach" },
  { to: "/backtest", label: "Backtest" },
  { to: "/audit", label: "Audit" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { setAuth } = useAuth();
  const nav = useNavigate();
  const { data: autonomy } = useAutonomy();
  const { data: health } = useHealth();
  const { data: me } = useMe();

  return (
    <div className="min-h-full grid grid-cols-[220px_1fr]">
      <aside className="bg-ink-800 border-r border-line p-4 flex flex-col">
        <div className="mb-6">
          <div className="font-semibold text-slate-100">TradeCopilot</div>
          <div className="text-[11px] text-muted">Agent · v0.3</div>
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn(
                  "px-3 py-2 rounded-md text-sm",
                  isActive
                    ? "bg-ink-700 text-slate-100"
                    : "text-slate-300 hover:bg-ink-700/60 hover:text-slate-100",
                )
              }
            >
              {n.label}
            </NavLink>
          ))}
          {me?.role === "admin" && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                cn(
                  "px-3 py-2 rounded-md text-sm border-t border-line/50 mt-2 pt-2",
                  isActive
                    ? "bg-ink-700 text-slate-100"
                    : "text-warn hover:bg-ink-700/60",
                )
              }
            >
              Admin
            </NavLink>
          )}
        </nav>
        <div className="mt-auto pt-4 space-y-2">
          {autonomy && (
            <div className="text-xs">
              <div className="kpi-label mb-1">Autonomy</div>
              <Badge tone={autonomy.autonomy_mode === "full_auto" ? "warn" : "muted"}>
                {autonomy.autonomy_mode.replace("_", "-")}
              </Badge>
            </div>
          )}
          {health && (
            <div className="text-[11px] text-muted">
              core <span className={health.core.ok ? "text-good" : "text-bad"}>
                {health.core.ok ? "ok" : "down"}
              </span>{" "}
              · ai{" "}
              <span
                className={
                  health.ai.status === "ok"
                    ? "text-good"
                    : health.ai.status === "worker_stale"
                    ? "text-warn"
                    : "text-bad"
                }
              >
                {health.ai.status}
              </span>
            </div>
          )}
          <button
            className="text-xs text-muted hover:text-slate-100"
            onClick={() => {
              setAuth(null);
              nav("/login", { replace: true });
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="p-6 max-w-[1400px] w-full mx-auto">
        <Outlet />
        <Disclaimer />
      </main>
    </div>
  );
}
