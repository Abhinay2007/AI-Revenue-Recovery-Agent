import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import type { PriorityOrder } from "@/lib/types";
import { usePriorityOrders } from "@/hooks/useRecovery";
import { AppShell } from "@/components/layout/AppShell";
// import { ErrorState } from "@/components/shared/States";
import { PriorityOrdersTable } from "@/components/recovery/PriorityOrdersTable";
import { OrderDrawer } from "@/components/recovery/OrderDrawer";

export const Route = createFileRoute("/priority-orders")({
  head: () => ({
    meta: [
      { title: "Priority Orders — AI Revenue Recovery Agent" },
      {
        name: "description",
        content:
          "Every scored COD order ranked by expected revenue at risk, with RTO probability and recommended action.",
      },
      { property: "og:title", content: "Priority Orders" },
      {
        property: "og:description",
        content: "Scored COD orders ranked by expected revenue at risk.",
      },
    ],
  }),
  component: PriorityOrdersPage,
});

function PriorityOrdersPage() {
  const priority = usePriorityOrders();
  const [selected, setSelected] = useState<PriorityOrder | null>(null);
  const orders = priority.data?.orders ?? [];

  return (
    <AppShell
      title="Priority Orders"
      subtitle={
        priority.data
          ? `Ranked by ${priority.data.ranking_metric} · limit ${priority.data.limit}`
          : "Ranked by the recovery engine"
      }
    >
      {/* {priority.isError && (
        <ErrorState
          title="Could not load priority orders"
          message={
            priority.error instanceof Error
              ? priority.error.message
              : "The ranking tool returned no orders."
          }
          onRetry={() => void priority.refetch()}
        />
      )} */}

      <section className="panel overflow-hidden">
        <PriorityOrdersTable
          orders={orders}
          loading={priority.isLoading}
          onSelect={setSelected}
          selectedOrderId={selected?.order_id}
        />
      </section>

      {selected && <OrderDrawer order={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
