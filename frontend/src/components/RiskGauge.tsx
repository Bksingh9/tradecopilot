import { cn } from "@/lib/cn";

export function RiskGauge({ usedPct, label = "Daily loss limit used" }: { usedPct: number; label?: string }) {
  const used = Math.max(0, Math.min(100, usedPct));
  const tone =
    used >= 100 ? "bg-bad"
    : used >= 75 ? "bg-warn"
    : "bg-good";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="kpi-label">{label}</span>
        <span className="text-sm font-mono">{used.toFixed(1)}%</span>
      </div>
      <div className="h-2.5 bg-ink-700 rounded-full overflow-hidden">
        <div
          className={cn("h-full transition-all", tone)}
          style={{ width: `${used}%` }}
        />
      </div>
    </div>
  );
}
