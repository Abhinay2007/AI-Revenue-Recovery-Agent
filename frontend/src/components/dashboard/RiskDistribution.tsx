import type { PriorityOrder } from "@/lib/types";
import { Skeleton } from "@/components/shared/States";

const LEVELS = [
  { key: "HIGH", label: "High", bar: "bg-negative", text: "text-negative" },
  { key: "MEDIUM", label: "Medium", bar: "bg-warning", text: "text-warning" },
  { key: "LOW", label: "Low", bar: "bg-positive", text: "text-positive" },
] as const;

export function RiskDistribution({
  orders,
  loading,
}: {
  orders?: PriorityOrder[] | undefined;
  loading?: boolean | undefined;
}) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-8" />
        ))}
      </div>
    );
  }

  if (!orders || orders.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Risk distribution unavailable — no scored orders returned.
      </p>
    );
  }

  const total = orders.length;

  return (
    <div className="space-y-4">
      {LEVELS.map((level) => {
        const bucket = orders.filter((o) => o.risk_level === level.key);
        const share = bucket.length / total;
        const atRisk = bucket.reduce((sum, o) => sum + o.expected_revenue_at_risk, 0);
        return (
          <div key={level.key}>
            <div className="mb-1.5 flex items-baseline justify-between text-xs">
              <span className="font-medium">{level.label} RTO risk</span>
              <span className="num text-muted-foreground">
                {bucket.length} order{bucket.length === 1 ? "" : "s"} ·{" "}
                <span className={level.text}>{Math.round(share * 100)}%</span>
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${level.bar} transition-[width] duration-700 ease-out`}
                style={{ width: `${Math.max(share * 100, bucket.length ? 2 : 0)}%` }}
              />
            </div>
            <p className="num mt-1 text-[11px] text-subtle-foreground">
              ₹{atRisk.toLocaleString("en-IN", { maximumFractionDigits: 0 })} at risk
            </p>
          </div>
        );
      })}
      <p className="border-t border-border pt-3 text-[11px] text-subtle-foreground">
        Distribution across the {total} scored COD orders returned by the ranking tool.
      </p>
    </div>
  );
}
