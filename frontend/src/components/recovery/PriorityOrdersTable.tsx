import { useMemo, useState } from "react";
import { ArrowUpRight, ChevronDown, ChevronUp, Search } from "lucide-react";
import type { PriorityOrder, RiskLevel } from "@/lib/types";
import { cn, formatAction, formatINR, formatPercent } from "@/lib/format";
import { ActionTag, RiskBadge } from "@/components/shared/Badges";
import { EmptyState } from "@/components/shared/States";

type SortKey = "expected_revenue_at_risk" | "amount" | "rto_probability" | "expected_net_recovery";

const COLUMNS: Array<{ key: SortKey | null; label: string; align?: "right" }> = [
  { key: null, label: "Order" },
  { key: "amount", label: "Amount", align: "right" },
  { key: "rto_probability", label: "RTO Risk", align: "right" },
  { key: "expected_revenue_at_risk", label: "Revenue at Risk", align: "right" },
  { key: null, label: "Recommended Action" },
  { key: "expected_net_recovery", label: "Expected Recovery", align: "right" },
  { key: null, label: "Status" },
];

export function PriorityOrdersTable({
  orders,
  loading,
  onSelect,
  selectedOrderId,
  showControls = true,
}: {
  orders: PriorityOrder[];
  loading?: boolean | undefined;
  onSelect: (order: PriorityOrder) => void;
  selectedOrderId?: string | undefined;
  showControls?: boolean | undefined;
}) {
  const [query, setQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "ALL">("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("expected_revenue_at_risk");
  const [desc, setDesc] = useState(true);

  const rows = useMemo(() => {
    const filtered = orders.filter((o) => {
      const matchesQuery = o.order_id.toLowerCase().includes(query.trim().toLowerCase());
      const matchesRisk = riskFilter === "ALL" || o.risk_level === riskFilter;
      return matchesQuery && matchesRisk;
    });
    return filtered.sort((a, b) => (desc ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey]));
  }, [orders, query, riskFilter, sortKey, desc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setDesc((d) => !d);
    else {
      setSortKey(key);
      setDesc(true);
    }
  };

  if (loading) {
    return (
      <div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-6 border-b border-border px-4 py-4">
            {[140, 80, 70, 100, 110, 90, 60].map((w, j) => (
              <div key={j} className="skeleton h-3.5" style={{ width: w }} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      {showControls && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
          <div className="relative min-w-[200px] flex-1">
            <Search
              size={13}
              className="absolute top-1/2 left-2.5 -translate-y-1/2 text-subtle-foreground"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search order ID"
              aria-label="Search orders by ID"
              className="num w-full rounded-md border border-border bg-canvas py-1.5 pr-3 pl-8 text-xs outline-none placeholder:font-sans focus:border-primary/40"
            />
          </div>
          <div className="flex items-center gap-1" role="group" aria-label="Filter by risk level">
            {(["ALL", "HIGH", "MEDIUM", "LOW"] as const).map((level) => (
              <button
                key={level}
                onClick={() => setRiskFilter(level)}
                aria-pressed={riskFilter === level}
                className={cn(
                  "rounded-md border px-2.5 py-1.5 text-[11px] font-semibold tracking-[0.04em] transition-colors",
                  riskFilter === level
                    ? "border-foreground bg-foreground text-primary-foreground"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
      )}

      {rows.length === 0 ? (
        <EmptyState
          title="No high-priority opportunities"
          description="There are currently no orders matching this view that require immediate attention."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] border-collapse">
            <thead>
              <tr className="bg-muted/60">
                {COLUMNS.map((col) => (
                  <th
                    key={col.label}
                    scope="col"
                    className={cn(
                      "px-4 py-2.5 text-[11px] font-semibold tracking-[0.05em] text-muted-foreground uppercase",
                      col.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    {col.key ? (
                      <button
                        onClick={() => toggleSort(col.key!)}
                        className="inline-flex items-center gap-1 hover:text-foreground"
                      >
                        {col.label}
                        {sortKey === col.key &&
                          (desc ? <ChevronDown size={11} /> : <ChevronUp size={11} />)}
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((order) => {
                const selected = order.order_id === selectedOrderId;
                return (
                  <tr
                    key={order.order_id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open ${order.order_id}`}
                    onClick={() => onSelect(order)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelect(order);
                      }
                    }}
                    className={cn(
                      "cursor-pointer border-b border-border transition-colors",
                      selected ? "bg-primary-soft/60" : "hover:bg-muted/50",
                    )}
                  >
                    <td className="px-4 py-3">
                      <p className="num text-xs font-medium">{order.order_id}</p>
                      <p className="text-[11px] text-subtle-foreground">
                        {order.payment_method?.toUpperCase() ?? "COD"}
                      </p>
                    </td>
                    <td className="num px-4 py-3 text-right text-[13px] font-medium">
                      {formatINR(order.amount)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="num text-[13px]">
                          {formatPercent(order.rto_probability, 2)}
                        </span>
                        <RiskBadge level={order.risk_level} />
                      </div>
                    </td>
                    <td className="num px-4 py-3 text-right text-[13px] font-semibold text-negative">
                      {formatINR(order.expected_revenue_at_risk)}
                    </td>
                    <td className="px-4 py-3">
                      <ActionTag label={formatAction(order.recommended_action)} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <p className="num text-[13px] font-semibold text-positive">
                        {formatINR(order.expected_net_recovery)}
                      </p>
                      <p className="num text-[11px] text-subtle-foreground">
                        net · cost {formatINR(order.expected_intervention_cost)}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                        Review <ArrowUpRight size={12} />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
