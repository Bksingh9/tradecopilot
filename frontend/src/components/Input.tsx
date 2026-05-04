import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface FieldProps {
  label?: string;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement>, FieldProps {}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, className, ...rest },
  ref,
) {
  return (
    <label className={cn("block", className)}>
      {label && <span className="label block mb-1">{label}</span>}
      <input ref={ref} className={cn("input", !!error && "border-bad/60")} {...rest} />
      {hint && !error && <span className="block text-xs text-muted mt-1">{hint}</span>}
      {error && <span className="block text-xs text-bad mt-1">{error}</span>}
    </label>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, FieldProps {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, ...rest },
  ref,
) {
  return (
    <label className={cn("block", className)}>
      {label && <span className="label block mb-1">{label}</span>}
      <textarea ref={ref} className={cn("input min-h-[88px]", !!error && "border-bad/60")} {...rest} />
      {hint && !error && <span className="block text-xs text-muted mt-1">{hint}</span>}
      {error && <span className="block text-xs text-bad mt-1">{error}</span>}
    </label>
  );
});

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement>, FieldProps {
  options: Array<{ value: string; label: string }>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, hint, error, className, ...rest },
  ref,
) {
  return (
    <label className={cn("block", className)}>
      {label && <span className="label block mb-1">{label}</span>}
      <select ref={ref} className={cn("input", !!error && "border-bad/60")} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {hint && !error && <span className="block text-xs text-muted mt-1">{hint}</span>}
      {error && <span className="block text-xs text-bad mt-1">{error}</span>}
    </label>
  );
});
