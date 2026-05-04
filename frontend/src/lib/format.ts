/** Format helpers for currency / percent / dates. */

export function fmtMoney(n: number | null | undefined, currency: string = "INR"): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const sym = currency === "INR" ? "₹" : currency === "USD" ? "$" : "";
  return `${sign}${sym}${abs.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function fmtSignedMoney(n: number | null | undefined, currency: string = "INR"): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sym = currency === "INR" ? "₹" : currency === "USD" ? "$" : "";
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  return `${sign}${sym}${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(digits)}%`;
}

export function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString();
}

export function fmtTimeAgo(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s).getTime();
  const now = Date.now();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function pnlClass(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-slate-300";
  return n > 0 ? "text-good" : "text-bad";
}
