import { useState } from "react";
import { AlertCircle, Loader2, ShieldAlert } from "lucide-react";
import type { PendingApprovalItem } from "@/lib/types";
import { agentApprove } from "@/lib/api/agent";
import { formatAction, formatINR } from "@/lib/format";
import { useAppStore } from "@/lib/store";

export function ApprovalDialog({
  item,
  onClose,
  onSuccess,
}: {
  item: PendingApprovalItem;
  onClose: () => void;
  onSuccess: (status: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { addAuditEntry, removePendingApproval } = useAppStore();

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await agentApprove({
        pending_action_id: item.pending_action_id,
        approved: true,
        approved_action: item.recommended_action,
        session_id: item.session_id,
      });

      if (res.status === "FAILED" || !res.execution_status) {
        throw new Error(res.summary);
      }

      if (res.audit_id) {
        addAuditEntry({
          audit_id: res.audit_id,
          timestamp: new Date().toISOString(),
          session_id: res.session_id,
          order_id: item.order_id,
          tool: "agent.approve",
          action: item.recommended_action,
          status: res.execution_status?.status ?? "SIMULATED_SUCCESS",
          summary: `Approved ${formatAction(item.recommended_action)} for ${item.order_id}`,
          tool_calls: res.tool_calls,
        });
      }

      removePendingApproval(item.pending_action_id);
      onSuccess(res.execution_status?.status ?? "SIMULATED_SUCCESS");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/25 p-4 backdrop-blur-[2px]">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="approve-title"
        className="w-full max-w-md rounded-xl border border-border bg-surface p-5 shadow-[var(--shadow-overlay)]"
      >
        <div className="flex items-center gap-2 text-warning">
          <ShieldAlert size={18} />
          <h3 id="approve-title" className="text-[15px] font-semibold text-foreground">
            Approve Recovery
          </h3>
        </div>

        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          This executes the recovery attempt for order{" "}
          <span className="num text-foreground">{item.order_id}</span>. No customer is contacted and
          no payment is captured.
        </p>

        <dl className="mt-4 divide-y divide-border overflow-hidden rounded-lg border border-border">
          <Row label="Action" value={formatAction(item.recommended_action)} />
          <Row
            label="Expected net recovery"
            value={item.expected_net_recovery != null ? formatINR(item.expected_net_recovery) : "—"}
            tone="recovery"
          />
          <Row
            label="Intervention cost"
            value={
              item.expected_intervention_cost != null
                ? formatINR(item.expected_intervention_cost)
                : "—"
            }
          />
          <Row label="Execution mode" value="Policy-approved" tone="warn" />
        </dl>

        {error && (
          <p className="mt-3 flex items-start gap-2 rounded-lg border border-negative/25 bg-negative-soft px-3 py-2 text-xs text-negative">
            <AlertCircle size={14} className="mt-px shrink-0" />
            {error}
          </p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-md px-3 py-2 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={handleApprove}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading && <Loader2 size={13} className="animate-spin" />}
            Approve Recovery
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "recovery" | "warn" | undefined;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={`text-xs font-semibold ${
          tone === "recovery" ? "num text-positive" : tone === "warn" ? "text-warning" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
