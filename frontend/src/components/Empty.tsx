import type { ReactNode } from "react";

export function Empty({ title, hint, action }: { title: string; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="text-center py-10 px-4 text-sm">
      <div className="text-slate-200 font-medium">{title}</div>
      {hint && <div className="text-muted mt-1">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
