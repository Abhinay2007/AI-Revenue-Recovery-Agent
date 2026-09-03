import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { BadgeCheck, CheckCircle2 } from "lucide-react";
import type { PendingApprovalItem } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/shared/States";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";
import { ApprovalDialog } from "@/components/approvals/ApprovalDialog";

export const Route = createFileRoute("/approvals")({
  head: () => ({
    meta: [
      { title: "Approval Center — AI Revenue Recovery Agent" },
      {
        name: "description",
        content: "Human-in-the-loop approval for every recovery action the agent proposes.",
      },
      { property: "og:title", content: "Approval Center" },
      {
        property: "og:description",
        content: "Human-in-the-loop approval for agent-proposed recovery actions.",
      },
    ],
  }),
  component: ApprovalsPage,
});

function ApprovalsPage() {
  const pending = useAppStore((s) => s.pendingApprovals);
  const removePendingApproval = useAppStore((s) => s.removePendingApproval);
  const [active, setActive] = useState<PendingApprovalItem | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  const handleReject = (item: PendingApprovalItem) => {
    removePendingApproval(item.pending_action_id);
    setConfirmation(`Rejected recovery for ${item.order_id}.`);
  };

  return (
    <AppShell
      title="Approval Center"
      subtitle="No recovery action executes without an explicit human approval"
    >
      {confirmation && (
        <div className="flex items-center gap-2 rounded-lg border border-positive/25 bg-positive-soft px-3.5 py-2.5">
          <CheckCircle2 size={14} className="text-positive" />
          <p className="text-xs text-positive">{confirmation}</p>
        </div>
      )}

      {pending.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={BadgeCheck}
            title="No approvals waiting"
            description="When the agent proposes a recovery action it will appear here for review. Requests are tracked for this session."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((item) => (
            <ApprovalCard
              key={item.pending_action_id}
              item={item}
              onReview={() => setActive(item)}
              onReject={() => handleReject(item)}
            />
          ))}
        </div>
      )}

      <p className="text-[11px] text-subtle-foreground">
        Approved actions are executed by the recovery service and written to the audit log.
      </p>

      {active && (
        <ApprovalDialog
          item={active}
          onClose={() => setActive(null)}
          onSuccess={(status) => {
            setConfirmation(
              `Recovery for ${active.order_id} approved — execution status ${status}.`,
            );
            setActive(null);
          }}
        />
      )}
    </AppShell>
  );
}
