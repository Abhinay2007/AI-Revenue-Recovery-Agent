import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { CheckCircle2, Loader2, MessageSquare, ShieldCheck, X, XCircle } from "lucide-react";
import type { AgentResponse, PriorityOrder } from "@/lib/types";
import { agentChat } from "@/lib/api/agent";
import { formatAction, formatINR, formatPercent } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { ActionTag, RiskBadge } from "@/components/shared/Badges";
import { Skeleton } from "@/components/shared/States";
import { ToolTrace } from "@/components/agent/ToolTrace";

export function OrderDrawer({ order, onClose }: { order: PriorityOrder; onClose: () => void }) {
  const [analysis, setAnalysis] = useState<AgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);

  const { addPendingApproval, addAuditEntry, sessionId } = useAppStore();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setRequested(false);

    agentChat({ message: `Analyze ${order.order_id}`, session_id: sessionId })
      .then((res) => {
        if (cancelled) return;
        setAnalysis(res);
        if (res.audit_id) {
          addAuditEntry({
            audit_id: res.audit_id,
            timestamp: new Date().toISOString(),
            session_id: res.session_id,
            order_id: res.order_id,
            tool: "agent.chat",
            summary: `Order ${order.order_id} analyzed — ${res.recommendation?.recommended_action ?? "N/A"}`,
            tool_calls: res.tool_calls,
          });
        }
      })
      .catch(() => {
        if (!cancelled)
          setError(
            "Unable to investigate this order. Please check that the backend is running and try again.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.order_id]);

  const handleRequestRecovery = async () => {
    if (!analysis?.recommendation) return;
    setRequesting(true);
    setError(null);
    try {
      const res = await agentChat({
        message: `Recover ${order.order_id}`,
        session_id: sessionId,
      });
      if (res.approval_required && res.pending_action_id) {
        addPendingApproval({
          pending_action_id: res.pending_action_id,
          order_id: order.order_id,
          recommended_action: res.recommendation?.recommended_action ?? order.recommended_action,
          session_id: res.session_id,
          expected_net_recovery: res.recommendation?.expected_net_recovery,
          expected_intervention_cost: res.recommendation?.expected_intervention_cost,
          expected_recovered_revenue: res.recommendation?.expected_recovered_revenue,
          expected_revenue_at_risk: order.expected_revenue_at_risk,
          rto_probability: order.rto_probability,
          risk_level: order.risk_level,
          policy_allowed: res.policy_status?.allowed,
          created_at: new Date().toISOString(),
        });
        if (res.audit_id) {
          addAuditEntry({
            audit_id: res.audit_id,
            timestamp: new Date().toISOString(),
            session_id: res.session_id,
            order_id: order.order_id,
            tool: "agent.request_execution",
            summary: `Recovery requested for ${order.order_id} — awaiting approval`,
            tool_calls: res.tool_calls,
          });
        }
        setRequested(true);
      } else {
        setError(res.summary || "The recovery service did not return an approval request.");
      }
    } catch {
      setError("Unable to request recovery for this order. Please try again.");
    } finally {
      setRequesting(false);
    }
  };

  const rec = analysis?.recommendation;
  const risk = analysis?.risk;
  const rtoProbability = risk?.rto_probability ?? order.rto_probability;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-foreground/15 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Order ${order.order_id}`}
        className="drawer-in fixed inset-y-0 right-0 z-50 flex w-full max-w-[470px] flex-col border-l border-border bg-surface shadow-[var(--shadow-overlay)]"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div>
            <p className="label-xs">Order</p>
            <p className="num mt-1 text-[13px] font-semibold">{order.order_id}</p>
            <div className="mt-2 flex items-center gap-2">
              <span className="num text-xl font-semibold">{formatINR(order.amount)}</span>
              <RiskBadge level={risk?.risk_level ?? order.risk_level} />
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close order details"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted"
          >
            <X size={16} />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <section>
            <p className="label-xs mb-2">Risk</p>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="RTO probability" value={formatPercent(rtoProbability, 2)} tone="risk" />
              <Stat
                label="Revenue at risk"
                value={formatINR(order.expected_revenue_at_risk)}
                tone="risk"
              />
            </div>
            {risk?.reasons && risk.reasons.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {risk.reasons.slice(0, 4).map((reason, i) => (
                  <li key={i} className="flex gap-2 text-[12px] text-muted-foreground">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-border-strong" />
                    <span>
                      {reason.description ?? reason.feature ?? "Signal"}
                      {reason.impact ? ` · ${reason.impact}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <p className="label-xs mb-2">Recommendation</p>
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : // ) : error && !rec ? (
            //   <ErrorState
            //     title="Analysis unavailable"
            //     message={error}
            //     onRetry={() => setAnalysis(null)}
            //   />
            rec ? (
              <div className="space-y-3">
                <ActionTag label={formatAction(rec.recommended_action)} />
                <dl className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                  <Row label="Order value" value={formatINR(rec.order_amount)} />
                  <Row
                    label="Revenue at risk"
                    value={formatINR(rec.expected_revenue_at_risk)}
                    tone="risk"
                  />
                  <Row
                    label="Expected recovered revenue"
                    value={formatINR(rec.expected_recovered_revenue)}
                    tone="recovery"
                  />
                  <Row
                    label="Intervention cost"
                    value={formatINR(rec.expected_intervention_cost)}
                  />
                  <Row
                    label="Expected net recovery"
                    value={formatINR(rec.expected_net_recovery)}
                    tone="recovery"
                    strong
                  />
                </dl>

                {rec.reason && (
                  <div className="rounded-lg border border-border bg-canvas p-3.5">
                    <p className="label-xs mb-1.5">Why this action</p>
                    <p className="text-[12px] leading-relaxed text-muted-foreground">
                      {rec.reason}
                    </p>
                    {rec.reason_codes?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {rec.reason_codes.map((code) => (
                          <span
                            key={code}
                            className="num rounded bg-primary-soft px-1.5 py-px text-[10px] text-primary"
                          >
                            {code}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {analysis?.policy_status && (
                  <p className="flex items-center gap-1.5 text-[12px]">
                    {analysis.policy_status.allowed ? (
                      <>
                        <ShieldCheck size={13} className="text-positive" />
                        <span className="text-muted-foreground">
                          Policy {analysis.policy_status.policy_version}: allowed
                        </span>
                      </>
                    ) : (
                      <>
                        <XCircle size={13} className="text-negative" />
                        <span className="text-muted-foreground">
                          Policy blocked: {analysis.policy_status.violations.join(", ")}
                        </span>
                      </>
                    )}
                  </p>
                )}

                {rec.candidate_actions?.length > 0 && (
                  <div>
                    <p className="label-xs mb-1.5">Evaluated alternatives</p>
                    <ul className="space-y-1">
                      {rec.candidate_actions.map((c) => (
                        <li
                          key={c.action}
                          className="flex items-center justify-between rounded-md border border-border px-2.5 py-1.5 text-[11px]"
                        >
                          <span
                            className={c.permitted ? "" : "text-subtle-foreground line-through"}
                          >
                            {formatAction(c.action)}
                          </span>
                          <span className="num text-muted-foreground">
                            net {formatINR(c.expected_net_recovery)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {analysis?.tool_calls && <ToolTrace toolCalls={analysis.tool_calls} />}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No recovery recommendation was returned for this order.
              </p>
            )}
          </section>
        </div>

        <footer className="space-y-2 border-t border-border px-5 py-4">
          {error && rec && <p className="text-[11px] text-negative">{error}</p>}
          {requested ? (
            <div className="flex items-center gap-2 rounded-lg border border-positive/25 bg-positive-soft px-3 py-2.5">
              <CheckCircle2 size={14} className="text-positive" />
              <p className="text-xs text-positive">
                Recovery requested —{" "}
                <Link to="/approvals" className="font-semibold underline">
                  review in Approval Center
                </Link>
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/agent"
                search={{ order: order.order_id }}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-border-strong px-3 py-2 text-xs font-semibold transition-colors hover:bg-muted"
              >
                <MessageSquare size={13} />
                Ask the agent
              </Link>
              <button
                onClick={handleRequestRecovery}
                disabled={!rec || requesting}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {requesting ? <Loader2 size={13} className="animate-spin" /> : null}
                Recover order
              </button>
            </div>
          )}
          <p className="text-[10px] text-subtle-foreground"></p>
        </footer>
      </aside>
    </>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "risk" | "recovery" | undefined;
}) {
  return (
    <div className="rounded-lg border border-border bg-canvas p-3">
      <p className="label-xs">{label}</p>
      <p
        className={`num mt-1.5 text-lg font-semibold ${
          tone === "risk" ? "text-negative" : tone === "recovery" ? "text-positive" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function Row({
  label,
  value,
  tone,
  strong,
}: {
  label: string;
  value: string;
  tone?: "risk" | "recovery" | undefined;
  strong?: boolean | undefined;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={`num text-[13px] ${strong ? "font-semibold" : "font-medium"} ${
          tone === "risk" ? "text-negative" : tone === "recovery" ? "text-positive" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
