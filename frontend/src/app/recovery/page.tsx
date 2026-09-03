"use client";

import { useEffect, useState } from "react";
import PriorityOrdersTable from "@/components/recovery/PriorityOrdersTable";
import OrderDrawer from "@/components/recovery/OrderDrawer";
import ErrorState from "@/components/shared/ErrorState";
import { agentChat } from "@/lib/api/agent";
import type { PriorityOrder, PriorityOrdersResult } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { RefreshCw, Filter } from "lucide-react";

export default function RecoveryQueuePage() {
  const [priorityData, setPriorityData] = useState<PriorityOrdersResult | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<PriorityOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sessionId } = useAppStore();

  const loadOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await agentChat({
        message: "Which orders should I prioritize for recovery?",
        session_id: sessionId,
      });
      if (res.status === "FAILED") throw new Error(res.summary);
      if (res.priority_orders) {
        setPriorityData(res.priority_orders);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load priority queue";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOrders();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Priority Recovery Queue</h1>
          <p className="text-xs text-gray-500 mt-1">
            COD orders ranked by predicted revenue at risk &bull; Click any order for breakdown
          </p>
        </div>
        <button
          onClick={loadOrders}
          disabled={loading}
          className="p-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          title="Refresh queue"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {error ? (
        <ErrorState
          title="Failed to load orders"
          message={error}
          onRetry={loadOrders}
        />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <PriorityOrdersTable
            orders={priorityData?.orders ?? []}
            loading={loading}
            onSelect={(order) => setSelectedOrder(order)}
            selectedOrderId={selectedOrder?.order_id}
          />
        </div>
      )}

      {selectedOrder && (
        <OrderDrawer
          order={selectedOrder}
          onClose={() => setSelectedOrder(null)}
        />
      )}
    </div>
  );
}
