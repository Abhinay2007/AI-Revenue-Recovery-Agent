import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import type { PriorityOrder } from "@/lib/types";
import { formatINR } from "@/lib/format";
import { usePriorityOrders, useRecoveryOpportunity } from "@/hooks/useRecovery";
import { AppShell } from "@/components/layout/AppShell";
import { MetricCard } from "@/components/shared/MetricCard";
// import { ErrorState } from "@/components/shared/States";
import { PriorityOrdersTable } from "@/components/recovery/PriorityOrdersTable";
import { OrderDrawer } from "@/components/recovery/OrderDrawer";

export const Route = createFileRoute("/recovery")({
  head: () => ({
    meta: [
      { title: "Recovery Queue — AI Revenue Recovery Agent" },
      {
        name: "description",
        content:
          "Work the recovery queue: review at-risk COD orders, recommended actions, and expected net recovery.",
      },
      { property: "og:title", content: "Recovery Queue" },
      {
        property: "og:description",
        content: "Review at-risk COD orders and recommended recovery actions.",
      },
    ],
  }),
  component: RecoveryPage,
});

function RecoveryPage() {
  const priority = usePriorityOrders();
  const opportunity = useRecoveryOpportunity();
  const [selected, setSelected] = useState<PriorityOrder | null>(null);

  const orders = priority.data?.orders ?? [];
  const o = opportunity.data;

  return (
    <AppShell
      title="Recovery Queue"
      subtitle="Orders where an intervention has positive expected value"
    >
      {/* {priority.isError && (
        <ErrorState
          title="Could not load the recovery queue"
          message={
            priority.error instanceof Error
              ? priority.error.message
              : "The recovery service did not return ranked orders."
          }
          onRetry={() => void priority.refetch()}
        />
      )} */}

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricCard
          label="Revenue at risk in queue"
          value={o ? formatINR(o.total_revenue_at_risk) : "—"}
          sub={o ? `${o.orders_evaluated} orders evaluated` : undefined}
          tone="risk"
          loading={opportunity.isLoading}
          unavailable={!opportunity.isLoading && !o}
        />
        <MetricCard
          label="Expected net recovery"
          value={o ? formatINR(o.expected_net_recovery) : "—"}
          tone="recovery"
          loading={opportunity.isLoading}
          unavailable={!opportunity.isLoading && !o}
        />
        <MetricCard
          label="Orders in queue"
          value={String(orders.length)}
          sub={
            priority.data
              ? `Min RTO ${Math.round(priority.data.minimum_rto_probability * 100)}% · min value ${formatINR(priority.data.minimum_order_value)}`
              : undefined
          }
          loading={priority.isLoading}
        />
      </section>

      <section className="panel overflow-hidden">
        <PriorityOrdersTable
          orders={orders}
          loading={priority.isLoading}
          onSelect={setSelected}
          selectedOrderId={selected?.order_id}
        />
      </section>

      {o?.assumption_source && (
        <p className="text-[11px] text-subtle-foreground">
          Recovery assumptions: {o.assumption_source}
        </p>
      )}

      {selected && <OrderDrawer order={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
