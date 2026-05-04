import { cn } from "@/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block w-4 h-4 border-2 border-line border-t-accent rounded-full animate-spin",
        className,
      )}
      aria-label="loading"
    />
  );
}
