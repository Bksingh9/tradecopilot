import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "danger";

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = "secondary", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  const cls =
    variant === "primary" ? "btn-primary"
    : variant === "danger" ? "btn-danger"
    : "btn-secondary";
  return (
    <button
      ref={ref}
      className={cn(cls, className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
});
