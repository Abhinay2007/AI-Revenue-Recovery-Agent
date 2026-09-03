import { ShieldAlert } from "lucide-react";
import type { PendingApprovalItem } from "@/lib/types";
import { formatAction, formatINR, formatPercent, formatTime } from "@/lib/format";
import { RiskBadge, StatusBadge } from "@/components/shared/Badges";

export function ApprovalCard({
  item,
  onReview,
  onReject,
  rejecting,
}: {
  item: PendingApprovalItem;
  onReview: () => void;
  onReject: () => void;
  rejecting?: boolean | undefined;
}) {
  return (
    <article className="panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="num text-[13px] font-semibold">{item.order_id}</span>
            {item.risk_level && <RiskBadge level={item.risk_level} />}
            <StatusBadge status="PENDING" />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatAction(item.recommended_action)} · requested {formatTime(item.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onReject}
            disabled={rejecting}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
          >
            Reject
          </button>
          <button
            onClick={onReview}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <ShieldAlert size={13} />
            Review &amp; approve
          </button>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 sm:grid-cols-4">
        <Field
          label="RTO probability"
          value={item.rto_probability != null ? formatPercent(item.rto_probability, 2) : "—"}
        />
        <Field
          label="Revenue at risk"
          value={
            item.expected_revenue_at_risk != null ? formatINR(item.expected_revenue_at_risk) : "—"
          }
          tone="risk"
        />
        <Field
          label="Expected net recovery"
          value={item.expected_net_recovery != null ? formatINR(item.expected_net_recovery) : "—"}
          tone="recovery"
        />
        <Field
          label="Policy"
          value={item.policy_allowed == null ? "—" : item.policy_allowed ? "Allowed" : "Blocked"}
          tone={item.policy_allowed === false ? "risk" : undefined}
        />
      </dl>
    </article>
  );
}

function Field({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "risk" | "recovery" | undefined;
}) {
  return (
    <div>
      <dt className="label-xs">{label}</dt>
      <dd
        className={`num mt-1 text-[13px] font-semibold ${
          tone === "risk" ? "text-negative" : tone === "recovery" ? "text-positive" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
