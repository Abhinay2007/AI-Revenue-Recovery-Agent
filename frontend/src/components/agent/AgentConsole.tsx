import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Bot, Loader2, Send, User } from "lucide-react";
import type { AgentResponse } from "@/lib/types";
import { agentChat } from "@/lib/api/agent";
import { formatAction, formatINR, formatPercent } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { RiskBadge } from "@/components/shared/Badges";
import { ToolTrace } from "./ToolTrace";

interface Message {
  role: "user" | "agent";
  content: string;
  response?: AgentResponse | undefined;
  timestamp: string;
  loading?: boolean | undefined;
}

const SUGGESTED_PROMPTS = [
  "What revenue is at risk?",
  "Which orders should I prioritize for recovery?",
  "Show recovery opportunity summary",
  "Show recovery action distribution",
];

export function AgentConsole({ initialOrder }: { initialOrder?: string | undefined }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(initialOrder ? `Analyze ${initialOrder}` : "");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const { sessionId, addAuditEntry, addPendingApproval } = useAppStore();

  const handleSend = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || isLoading) return;

    setInput("");
    const ts = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      { role: "user", content: message, timestamp: ts },
      { role: "agent", content: "", timestamp: ts, loading: true },
    ]);
    setIsLoading(true);

    try {
      const res = await agentChat({ message, session_id: sessionId });
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? {
                ...m,
                content: res.natural_language_response || res.summary,
                response: res,
                loading: false,
                timestamp: new Date().toISOString(),
              }
            : m,
        ),
      );

      if (res.audit_id) {
        addAuditEntry({
          audit_id: res.audit_id,
          timestamp: new Date().toISOString(),
          session_id: res.session_id,
          order_id: res.order_id,
          tool: "agent.chat",
          summary: message,
          tool_calls: res.tool_calls,
        });
      }

      if (res.approval_required && res.pending_action_id) {
        addPendingApproval({
          pending_action_id: res.pending_action_id,
          order_id: res.order_id ?? "",
          recommended_action: res.recommendation?.recommended_action ?? "",
          session_id: res.session_id,
          expected_net_recovery: res.recommendation?.expected_net_recovery,
          expected_intervention_cost: res.recommendation?.expected_intervention_cost,
          expected_recovered_revenue: res.recommendation?.expected_recovered_revenue,
          expected_revenue_at_risk: res.revenue_at_risk?.expected_revenue_at_risk,
          rto_probability: res.risk?.rto_probability,
          risk_level: res.risk?.risk_level,
          policy_allowed: res.policy_status?.allowed,
          created_at: new Date().toISOString(),
        });
      }
    } catch {
      const msg =
        "Unable to connect to the recovery service. Please check that the backend is running and try again.";
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? { ...m, content: msg, loading: false, timestamp: new Date().toISOString() }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (initialOrder && !started.current) {
      started.current = true;
      void handleSend(`Analyze ${initialOrder}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialOrder]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="panel flex h-[calc(100vh-9.5rem)] min-h-[520px] flex-col overflow-hidden">
      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-4 pt-14">
            <span className="flex size-11 items-center justify-center rounded-xl bg-primary-soft">
              <Bot size={20} className="text-primary" />
            </span>
            <div className="text-center">
              <p className="text-sm font-semibold">Recovery Agent</p>
              <p className="mx-auto mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
                Ask about revenue at risk, recovery opportunities, and specific orders. Every answer
                is grounded in backend tool outputs — the agent does not invent numbers.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleSend(p)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border-strong hover:bg-muted"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "agent" && (
              <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft">
                <Bot size={13} className="text-primary" />
              </span>
            )}
            <div className={`max-w-[85%] ${msg.role === "user" ? "order-first" : ""}`}>
              {msg.loading ? (
                <div className="flex items-center gap-2 py-2">
                  <Loader2 size={13} className="animate-spin text-primary" />
                  <span className="text-xs text-muted-foreground">Running tools…</span>
                </div>
              ) : (
                <>
                  <div
                    className={
                      msg.role === "user"
                        ? "rounded-xl rounded-br-sm bg-foreground px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap text-primary-foreground"
                        : "rounded-xl rounded-bl-sm border border-border bg-canvas px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap"
                    }
                  >
                    {msg.content}
                  </div>
                  {msg.response && <ResponseCards response={msg.response} />}
                  {msg.response?.tool_calls?.length ? (
                    <ToolTrace toolCalls={msg.response.tool_calls} />
                  ) : null}
                </>
              )}
            </div>
            {msg.role === "user" && (
              <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-canvas">
                <User size={13} className="text-muted-foreground" />
              </span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border px-4 py-3">
        <div className="flex items-end gap-2 rounded-xl border border-border-strong bg-canvas px-3 py-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            placeholder="Ask the Recovery Agent…"
            aria-label="Message the Recovery Agent"
            rows={1}
            className="max-h-28 flex-1 resize-none bg-transparent text-[13px] outline-none"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            aria-label="Send message"
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity disabled:opacity-40"
          >
            {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-subtle-foreground">
          Financial calculations are deterministic and every action requires approval.
        </p>
      </div>
    </div>
  );
}

function ResponseCards({ response }: { response: AgentResponse }) {
  const { recommendation, risk, revenue_at_risk, priority_orders, recovery_opportunity } = response;

  if (recommendation && risk && revenue_at_risk) {
    return (
      <div className="mt-2 space-y-2.5 rounded-xl border border-border bg-surface p-3.5">
        <div className="flex items-center gap-2">
          <span className="num text-xs font-semibold">{recommendation.order_id}</span>
          <RiskBadge level={risk.risk_level} />
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          <DataPoint label="RTO risk" value={formatPercent(risk.rto_probability, 2)} />
          <DataPoint
            label="Revenue at risk"
            value={formatINR(revenue_at_risk.expected_revenue_at_risk)}
            tone="risk"
          />
          <DataPoint label="Recommended" value={formatAction(recommendation.recommended_action)} />
          <DataPoint
            label="Expected net recovery"
            value={formatINR(recommendation.expected_net_recovery)}
            tone="recovery"
          />
        </div>
        {response.approval_required && (
          <p className="rounded-lg border border-warning/25 bg-warning-soft px-3 py-2 text-[11px] text-warning">
            Recovery action pending approval —{" "}
            <Link to="/approvals" className="font-semibold underline">
              open Approval Center
            </Link>
          </p>
        )}
      </div>
    );
  }

  if (priority_orders?.orders?.length) {
    const top = priority_orders.orders.slice(0, 3);
    return (
      <div className="mt-2 space-y-2 rounded-xl border border-border bg-surface p-3.5">
        <p className="label-xs">Top {top.length} priority orders</p>
        {top.map((o) => (
          <div key={o.order_id} className="flex items-center justify-between">
            <span className="num text-[11px]">{o.order_id}</span>
            <div className="flex items-center gap-2">
              <RiskBadge level={o.risk_level} />
              <span className="num text-[11px] text-negative">
                {formatINR(o.expected_revenue_at_risk)}
              </span>
            </div>
          </div>
        ))}
        <Link
          to="/recovery"
          className="block rounded-lg border border-primary/20 py-1.5 text-center text-[11px] font-medium text-primary transition-colors hover:bg-primary-soft"
        >
          View full recovery queue
        </Link>
      </div>
    );
  }

  if (recovery_opportunity) {
    return (
      <div className="mt-2 space-y-2.5 rounded-xl border border-border bg-surface p-3.5">
        <p className="label-xs">Recovery opportunity</p>
        <div className="grid grid-cols-2 gap-2.5">
          <DataPoint
            label="Revenue at risk"
            value={formatINR(recovery_opportunity.total_revenue_at_risk)}
            tone="risk"
          />
          <DataPoint
            label="Expected net recovery"
            value={formatINR(recovery_opportunity.expected_net_recovery)}
            tone="recovery"
          />
          <DataPoint
            label="Orders evaluated"
            value={String(recovery_opportunity.orders_evaluated)}
          />
          <DataPoint
            label="Recoverable orders"
            value={String(recovery_opportunity.orders_with_positive_expected_recovery)}
          />
        </div>
      </div>
    );
  }

  return null;
}

function DataPoint({
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
      <p className="text-[10px] text-subtle-foreground">{label}</p>
      <p
        className={`num text-xs font-semibold ${
          tone === "risk" ? "text-negative" : tone === "recovery" ? "text-positive" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
