import { useState } from "react";
import { AlertCircle, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import type { ToolCallRecord } from "@/lib/types";
import { formatTime } from "@/lib/format";

const TOOL_LABELS: Record<string, string> = {
  "order_tool.get_order": "Order retrieved",
  get_order: "Order retrieved",
  "risk_tool.get_rto_risk": "RTO risk calculated",
  get_rto_risk: "RTO risk calculated",
  "revenue_tool.calculate_revenue_at_risk": "Revenue at risk calculated",
  calculate_revenue_at_risk: "Revenue at risk calculated",
  "recovery_tool.evaluate_recovery": "Recovery policy evaluated",
  evaluate_recovery: "Recovery policy evaluated",
  "policy_tool.check_recovery_policy": "Policy validated",
  check_recovery_policy: "Policy validated",
  "execution_tool.execute_recovery": "Recovery executed",
  execute_recovery: "Recovery executed",
  "merchant_tool.get_revenue_summary": "Revenue summary loaded",
  get_revenue_summary: "Revenue summary loaded",
  "merchant_tool.get_priority_recovery_orders": "Priority orders loaded",
  get_priority_recovery_orders: "Priority orders loaded",
  "merchant_tool.get_recovery_opportunity_summary": "Recovery opportunity loaded",
  get_recovery_opportunity_summary: "Recovery opportunity loaded",
  "merchant_tool.get_recovery_action_distribution": "Action distribution loaded",
  get_recovery_action_distribution: "Action distribution loaded",
  "agent.chat": "Agent analysis complete",
  "agent.approve": "Approval recorded",
  "agent.merchant_summary": "Merchant summary retrieved",
  "agent.priority_recovery": "Priority orders retrieved",
  "agent.recovery_opportunity": "Recovery opportunity retrieved",
  "agent.action_distribution": "Action distribution retrieved",
  "agent.tool_loop": "Tool loop complete",
  "agent.failure": "Agent encountered an error",
  create_audit_event: "Audit event created",
};

type Call = ToolCallRecord | Record<string, unknown>;

function toolName(call: Call): string | null {
  return "tool_name" in call && typeof call.tool_name === "string" ? call.tool_name : null;
}

function callError(call: Call): string | null {
  return "error" in call && call.error ? String(call.error) : null;
}

function callTimestamp(call: Call): string | null {
  return "timestamp" in call && typeof call.timestamp === "string" ? call.timestamp : null;
}

export function ToolTrace({ toolCalls }: { toolCalls: Call[] }) {
  const [open, setOpen] = useState(false);
  const named = toolCalls.filter((c) => toolName(c) !== null);
  if (named.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        How the agent reached this decision
        <span className="num rounded bg-muted px-1.5 text-[10px]">{named.length} tools</span>
      </button>

      {open && (
        <ol className="mt-2 space-y-2 rounded-lg border border-border bg-canvas p-3.5">
          <p className="label-xs">Tool execution trace</p>
          {named.map((call, i) => {
            const name = toolName(call)!;
            const err = callError(call);
            const ts = callTimestamp(call);
            return (
              <li key={i} className="flex items-start gap-2.5">
                {err ? (
                  <AlertCircle size={13} className="mt-px shrink-0 text-negative" />
                ) : (
                  <CheckCircle2 size={13} className="mt-px shrink-0 text-positive" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium">{TOOL_LABELS[name] ?? name}</p>
                  <p className="num text-[10px] text-subtle-foreground">{name}</p>
                  {err && <p className="mt-0.5 text-[11px] text-negative">{err}</p>}
                </div>
                {ts && (
                  <span className="num text-[10px] text-subtle-foreground">{formatTime(ts)}</span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
