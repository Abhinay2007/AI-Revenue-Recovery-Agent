import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import type { PriorityOrder } from "@/lib/types";
import { formatINR, formatPercent } from "@/lib/format";
import {
  useActionDistribution,
  useMerchantSummary,
  usePriorityOrders,
  useRecoveryOpportunity,
} from "@/hooks/useRecovery";
import { AppShell } from "@/components/layout/AppShell";
import { MetricCard } from "@/components/shared/MetricCard";
// import { ErrorState } from "@/components/shared/States";
import { RiskDistribution } from "@/components/dashboard/RiskDistribution";
import { ActionDistributionChart } from "@/components/dashboard/ActionDistributionChart";
import { PriorityOrdersTable } from "@/components/recovery/PriorityOrdersTable";
import { OrderDrawer } from "@/components/recovery/OrderDrawer";

export const Route = createFileRoute("/overview")({
  head: () => ({
    meta: [
      { title: "Revenue Recovery Overview — AI Revenue Recovery Agent" },
      {
        name: "description",
        content:
          "Live view of COD revenue at risk, RTO exposure, and expected recovery across your order book.",
      },
      { property: "og:title", content: "Revenue Recovery Overview" },
      {
        property: "og:description",
        content: "COD revenue at risk, RTO exposure, and expected recovery in one console.",
      },
    ],
  }),
  component: OverviewPage,
});

function OverviewPage() {
  const summary = useMerchantSummary();
  const opportunity = useRecoveryOpportunity();
  const distribution = useActionDistribution();
  const priority = usePriorityOrders();
  const [selected, setSelected] = useState<PriorityOrder | null>(null);

  const orders = priority.data?.orders ?? [];
  const s = summary.data;
  const o = opportunity.data;

  return (
    <AppShell
      title="Revenue Recovery Overview"
      subtitle={s ? `Merchant ${s.merchant_id} · ${s.total_orders} orders analysed` : undefined}
    >
      {/* {summary.isError && (
        <ErrorState
          title="Live recovery data unavailable"
          message={
            summary.error instanceof Error
              ? summary.error.message
              : "The backend did not return merchant analytics."
          }
          onRetry={() => void summary.refetch()}
        />
      )} */}

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-2">
        {/* <MetricCard
          label="Predicted revenue at risk"
          value={s ? formatINR(s.predicted_revenue_at_risk) : "—"}
          sub={s ? `${s.scored_cod_orders} scored COD orders` : undefined}
          tone="risk"
          loading={summary.isLoading}
          unavailable={!summary.isLoading && !s}
        /> */}
        <MetricCard
          label="Expected net recovery"
          value={o ? formatINR(o.expected_net_recovery) : "—"}
          sub={o ? `${o.orders_with_positive_expected_recovery} recoverable orders` : undefined}
          tone="recovery"
          loading={opportunity.isLoading}
          unavailable={!opportunity.isLoading && !o}
        />
        {/* <MetricCard
          label="Historical RTO rate"
          value={s ? formatPercent(s.rto_rate, 2) : "—"}
          sub={s ? `${s.rto_orders} returned of ${s.total_orders}` : undefined}
          tone="warning"
          loading={summary.isLoading}
          unavailable={!summary.isLoading && !s}
        /> */}
        <MetricCard
          label="Intervention cost"
          value={o ? formatINR(o.expected_intervention_cost) : "—"}
          sub={o ? `Gross recovery ${formatINR(o.expected_gross_recovery)}` : undefined}
          loading={opportunity.isLoading}
          unavailable={!opportunity.isLoading && !o}
        />
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="text-sm font-semibold">RTO risk distribution</h2>
          <p className="mt-0.5 mb-4 text-xs text-muted-foreground">
            Across orders ranked by the recovery engine.
          </p>
          <RiskDistribution orders={orders} loading={priority.isLoading} />
        </div>
        <div className="panel p-4">
          <h2 className="text-sm font-semibold">Recommended action mix</h2>
          <p className="mt-0.5 mb-4 text-xs text-muted-foreground">
            Policy-permitted actions selected by expected net recovery.
          </p>
          <ActionDistributionChart data={distribution.data} loading={distribution.isLoading} />
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold">Top recovery opportunities</h2>
            <p className="text-xs text-muted-foreground">
              {priority.data?.ranking_metric
                ? `Ranked by ${priority.data.ranking_metric}`
                : "Ranked by the recovery engine"}
            </p>
          </div>
          <Link
            to="/recovery"
            className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
          >
            Recovery queue <ArrowRight size={13} />
          </Link>
        </div>
        <PriorityOrdersTable
          orders={orders.slice(0, 8)}
          loading={priority.isLoading}
          onSelect={setSelected}
          selectedOrderId={selected?.order_id}
          showControls={false}
        />
      </section>

      {s?.ranking_note && <p className="text-[11px] text-subtle-foreground">{s.ranking_note}</p>}

      {selected && <OrderDrawer order={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
