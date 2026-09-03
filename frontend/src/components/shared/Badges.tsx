import { cn, riskBg } from "@/lib/format";

export function RiskBadge({ level, className }: { level: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-px text-[10px] font-semibold tracking-[0.07em]",
        riskBg(level),
        className,
      )}
    >
      {level?.toUpperCase()}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  SIMULATED_SUCCESS: "bg-positive-soft text-positive border-positive/20",
  EXECUTED_ACTION: "bg-positive-soft text-positive border-positive/20",
  APPROVED: "bg-positive-soft text-positive border-positive/20",
  RECOMMENDED: "bg-primary-soft text-primary border-primary/20",
  ANALYSIS: "bg-primary-soft text-primary border-primary/20",
  RECOMMENDATION: "bg-primary-soft text-primary border-primary/20",
  ALLOWED: "bg-positive-soft text-positive border-positive/20",
  PENDING: "bg-warning-soft text-warning border-warning/25",
  REVIEW: "bg-warning-soft text-warning border-warning/25",
  DEGRADED: "bg-warning-soft text-warning border-warning/25",
  OPERATIONAL: "bg-positive-soft text-positive border-positive/20",
  BLOCKED: "bg-negative-soft text-negative border-negative/20",
  REJECTED: "bg-negative-soft text-negative border-negative/20",
  FAILED: "bg-negative-soft text-negative border-negative/20",
  ERROR: "bg-negative-soft text-negative border-negative/20",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const key = status?.toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-px text-[10px] font-semibold tracking-[0.06em]",
        STATUS_STYLES[key] ?? "bg-muted text-muted-foreground border-border",
        className,
      )}
    >
      {key?.replace(/_/g, " ")}
    </span>
  );
}

export function ActionTag({ label, className }: { label: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded border border-primary/20 bg-primary-soft px-2 py-px text-[11px] font-medium text-primary",
        className,
      )}
    >
      {label}
    </span>
  );
}

export function TestModeBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border border-warning/30 bg-warning-soft px-2 py-1 text-[10px] font-semibold tracking-[0.08em] text-warning",
        className,
      )}
      title="Recovery execution is simulated"
    >
      <span className="size-1.5 rounded-full bg-warning" />
      TEST MODE
    </span>
  );
}
