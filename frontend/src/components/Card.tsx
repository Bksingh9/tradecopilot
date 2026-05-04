import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  pad?: boolean;
}

export function Card({ title, subtitle, actions, children, className, pad = true }: CardProps) {
  return (
    <section className={cn("card", !pad && "p-0", className)}>
      {(title || subtitle || actions) && (
        <header className={cn("flex items-start justify-between gap-3", pad ? "mb-3" : "p-4 border-b border-line")}>
          <div>
            {title && <h2 className="text-base font-semibold text-slate-100">{title}</h2>}
            {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={!pad ? "p-4" : ""}>{children}</div>
    </section>
  );
}
