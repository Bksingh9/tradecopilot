import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Tone = "good" | "bad" | "warn" | "muted";

export function Badge({ tone = "muted", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  const toneClass =
    tone === "good" ? "badge-good"
    : tone === "bad" ? "badge-bad"
    : tone === "warn" ? "badge-warn"
    : "badge-muted";
  return <span className={cn("badge", toneClass, className)}>{children}</span>;
}
