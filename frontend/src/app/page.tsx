"use client";

import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, ShieldCheck, ArrowRight, RefreshCw } from "lucide-react";
import MetricCard from "@/components/dashboard/MetricCard";
import RiskDistributionBar from "@/components/dashboard/RiskDistributionBar";
import ActionDistributionChart from "@/components/dashboard/ActionDistributionChart";
import PriorityOrdersTable from "@/components/recovery/PriorityOrdersTable";
import OrderDrawer from "@/components/recovery/OrderDrawer";
import ErrorState from "@/components/shared/ErrorState";
import { agentChat } from "@/lib/api/agent";
import { formatINR, greetingTime, today } from "@/lib/format";
import type { MerchantSummary, PriorityOrder, PriorityOrdersResult, RecoveryOpportunity, ActionDistribution } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import Link from "next/link";

export default function OverviewPage() {
  const [summary, setSummary] = useState<MerchantSummary | null>(null);
  const [opportunity, setOpportunity] = useState<RecoveryOpportunity | null>(null);
  const [distribution, setDistribution] = useState<ActionDistribution | null>(null);
  const [priorityData, setPriorityData] = useState<PriorityOrdersResult | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<PriorityOrder | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sessionId } = useAppStore();

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const sumRes = await agentChat({ message: "What revenue is at risk?", session_id: sessionId });
      const oppRes = await agentChat({ message: "Show recovery opportunity summary", session_id: sessionId });
      const distRes = await agentChat({ message: "Show recovery action distribution", session_id: sessionId });
      const prioRes = await agentChat({ message: "Which orders should I prioritize for recovery?", session_id: sessionId });

      const failed = [sumRes, oppRes, distRes, prioRes].find((response) => response.status === "FAILED");
      if (failed) throw new Error(failed.summary);

      if (sumRes.merchant_summary) setSummary(sumRes.merchant_summary);
      if (oppRes.recovery_opportunity) setOpportunity(oppRes.recovery_opportunity);
      if (distRes.action_distribution) setDistribution(distRes.action_distribution);
      if (prioRes.priority_orders) setPriorityData(prioRes.priority_orders);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <ErrorState
          title="Backend unavailable"
          message="We couldn't reach the Revenue Recovery service. Check that the API is running."
          onRetry={loadData}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {greetingTime()}, Demo Store
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Revenue recovery overview &bull; {today()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            TEST MODE
          </span>
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
            title="Refresh data"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Primary Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Revenue at Risk"
          value={summary ? formatINR(summary.predicted_revenue_at_risk) : "₹—"}
          sub={summary ? `${summary.scored_cod_orders} COD orders scored` : undefined}
          loading={loading}
          highlight
        />
        <MetricCard
          label="COD RTO Rate"
          value={summary ? `${(summary.rto_rate * 100).toFixed(1)}%` : "—%"}
          sub={summary ? `${summary.rto_orders} RTO out of ${summary.cod_orders} COD` : undefined}
          loading={loading}
        />
        <MetricCard
          label="Recoverable Opportunity"
          value={opportunity ? formatINR(opportunity.expected_net_recovery) : "₹—"}
          sub={opportunity ? `${opportunity.orders_with_positive_expected_recovery} orders actionable` : undefined}
          loading={loading}
        />
        <MetricCard
          label="Recovered Revenue"
          value={opportunity ? formatINR(opportunity.expected_gross_recovery) : "₹—"}
          sub="SIMULATED"
          badge="SIMULATED"
          loading={loading}
        />
      </div>

      {/* Risk Distribution & Action Distribution Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-gray-900">RTO Risk Distribution</h2>
              <p className="text-xs text-gray-500">Orders grouped by predicted RTO risk score</p>
            </div>
          </div>
          <RiskDistributionBar
            priorityOrders={priorityData?.orders}
            loading={loading}
          />
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-gray-900">Action Recommendation Distribution</h2>
              <p className="text-xs text-gray-500">Breakdown of recovery engine recommendations</p>
            </div>
          </div>
          <ActionDistributionChart
            data={distribution ?? undefined}
            loading={loading}
          />
        </div>
      </div>

      {/* Priority Queue Section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="p-5 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-gray-900">Priority Recovery Queue</h2>
            <p className="text-xs text-gray-500">Highest value orders recommended for recovery</p>
          </div>
          <Link
            href="/recovery"
            className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
          >
            View recovery queue <ArrowRight size={12} />
          </Link>
        </div>

        <PriorityOrdersTable
          orders={priorityData?.orders ?? []}
          loading={loading}
          onSelect={(order) => setSelectedOrder(order)}
          selectedOrderId={selectedOrder?.order_id}
        />
      </div>

      {/* Drawer for Order Inspection */}
      {selectedOrder && (
        <OrderDrawer
          order={selectedOrder}
          onClose={() => setSelectedOrder(null)}
        />
      )}
    </div>
  );
}
