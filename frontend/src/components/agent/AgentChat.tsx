"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Bot, User } from "lucide-react";
import type { AgentResponse } from "@/lib/types";
import { agentChat } from "@/lib/api/agent";
import { formatINR, formatPercent, formatAction } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import ToolTrace from "./ToolTrace";
import RiskBadge from "@/components/shared/RiskBadge";

interface Message {
  role: "user" | "agent";
  content: string;
  response?: AgentResponse;
  timestamp: string;
  loading?: boolean;
}

const SUGGESTED_PROMPTS = [
  "What revenue is at risk?",
  "Which orders should I prioritize for recovery?",
  "Show today's recovery opportunities",
  "Show recovery action distribution",
];

interface AgentChatProps {
  initialOrder?: string;
}

export default function AgentChat({ initialOrder }: AgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(
    initialOrder ? `Analyze ${initialOrder}` : "",
  );
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { sessionId, addAuditEntry, addPendingApproval } = useAppStore();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || isLoading) return;

    setInput("");
    const ts = new Date().toISOString();
    const userMsg: Message = { role: "user", content: message, timestamp: ts };
    const loadingMsg: Message = {
      role: "agent",
      content: "",
      timestamp: ts,
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
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
          recommended_action:
            res.recommendation?.recommended_action ?? "",
          session_id: res.session_id,
          expected_net_recovery: res.recommendation?.expected_net_recovery,
          expected_intervention_cost:
            res.recommendation?.expected_intervention_cost,
          expected_recovered_revenue:
            res.recommendation?.expected_recovered_revenue,
          expected_revenue_at_risk: res.revenue_at_risk?.expected_revenue_at_risk,
          rto_probability: res.risk?.rto_probability,
          risk_level: res.risk?.risk_level,
          policy_allowed: res.policy_status?.allowed,
          created_at: new Date().toISOString(),
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Request failed";
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
    if (initialOrder) {
      const timer = window.setTimeout(() => {
        void handleSend(`Analyze ${initialOrder}`);
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [initialOrder]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center pt-16 pb-8 gap-4">
            <div
              className="flex items-center justify-center rounded-full"
              style={{ width: 48, height: 48, background: "hsl(220 87% 54% / 0.1)" }}
            >
              <Bot size={22} style={{ color: "hsl(var(--primary))" }} />
            </div>
            <div className="text-center">
              <div
                className="font-semibold"
                style={{ fontSize: 15, color: "hsl(var(--text))" }}
              >
                Recovery Agent
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: "hsl(var(--text-secondary))",
                  marginTop: 4,
                  maxWidth: 360,
                  lineHeight: 1.6,
                }}
              >
                Ask about revenue risk, recovery opportunities, and orders. Responses are grounded in backend tool outputs.
              </div>
            </div>
            {/* Suggested prompts */}
            <div className="flex flex-wrap gap-2 mt-2 justify-center">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleSend(p)}
                  className="px-3 py-1.5 rounded-full border font-medium transition-colors hover:bg-gray-50"
                  style={{
                    fontSize: 12,
                    color: "hsl(var(--text-secondary))",
                    borderColor: "hsl(var(--border))",
                  }}
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
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "agent" && (
              <div
                className="shrink-0 flex items-center justify-center rounded-full mt-0.5"
                style={{
                  width: 28,
                  height: 28,
                  background: "hsl(220 87% 54% / 0.1)",
                }}
              >
                <Bot size={13} style={{ color: "hsl(var(--primary))" }} />
              </div>
            )}

            <div
              className="max-w-[85%]"
              style={{ order: msg.role === "user" ? -1 : undefined }}
            >
              {msg.loading ? (
                <div className="flex items-center gap-2 py-2">
                  <Loader2
                    size={13}
                    className="animate-spin"
                    style={{ color: "hsl(var(--primary))" }}
                  />
                  <span
                    style={{
                      fontSize: 12,
                      color: "hsl(var(--text-secondary))",
                    }}
                  >
                    Analyzing…
                  </span>
                </div>
              ) : (
                <>
                  <div
                    className="rounded-xl px-4 py-3"
                    style={{
                      background:
                        msg.role === "user"
                          ? "hsl(var(--primary))"
                          : "hsl(var(--surface))",
                      border:
                        msg.role === "agent"
                          ? "1px solid hsl(var(--border))"
                          : undefined,
                      color:
                        msg.role === "user" ? "#fff" : "hsl(var(--text))",
                      fontSize: 13,
                      lineHeight: 1.7,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {msg.content}
                  </div>

                  {/* Inline data cards */}
                  {msg.response && <ResponseCards response={msg.response} />}

                  {/* Tool trace */}
                  {msg.response?.tool_calls &&
                    msg.response.tool_calls.length > 0 && (
                      <ToolTrace toolCalls={msg.response.tool_calls} />
                    )}
                </>
              )}
            </div>

            {msg.role === "user" && (
              <div
                className="shrink-0 flex items-center justify-center rounded-full mt-0.5"
                style={{ width: 28, height: 28, background: "hsl(var(--bg))", border: "1px solid hsl(var(--border))" }}
              >
                <User size={13} style={{ color: "hsl(var(--text-secondary))" }} />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        className="px-4 py-3"
        style={{ borderTop: "1px solid hsl(var(--border))" }}
      >
        <div
          className="flex items-end gap-2 rounded-xl px-3 py-2"
          style={{ border: "1px solid hsl(var(--border-strong))", background: "hsl(var(--surface))" }}
        >
          <textarea
            ref={inputRef}
            id="agent-chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask the Recovery Agent…"
            rows={1}
            className="flex-1 resize-none outline-none bg-transparent"
            style={{
              fontSize: 13,
              color: "hsl(var(--text))",
              lineHeight: 1.5,
              maxHeight: 120,
            }}
          />
          <button
            id="agent-send-btn"
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            className="flex items-center justify-center rounded-lg transition-opacity disabled:opacity-40"
            style={{
              width: 32,
              height: 32,
              background: "hsl(var(--primary))",
              color: "#fff",
              flexShrink: 0,
            }}
            aria-label="Send message"
          >
            {isLoading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
          </button>
        </div>
        <div
          className="mt-1.5 text-center"
          style={{ fontSize: 10, color: "hsl(var(--text-muted))" }}
        >
          Financial calculations are deterministic — the AI does not invent numbers
        </div>
      </div>
    </div>
  );
}

function ResponseCards({ response }: { response: AgentResponse }) {
  const { recommendation, risk, revenue_at_risk, priority_orders, recovery_opportunity } = response;

  if (recommendation && risk && revenue_at_risk) {
    return (
      <div
        className="mt-2 rounded-xl p-3.5 space-y-2"
        style={{ background: "hsl(var(--bg))", border: "1px solid hsl(var(--border))" }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-medium" style={{ color: "hsl(var(--text))" }}>
            {recommendation.order_id}
          </span>
          <RiskBadge level={risk.risk_level} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <DataPoint label="RTO Risk" value={formatPercent(risk.rto_probability)} />
          <DataPoint label="Revenue at Risk" value={formatINR(revenue_at_risk.expected_revenue_at_risk)} red />
          <DataPoint label="Recommended" value={formatAction(recommendation.recommended_action)} />
          <DataPoint label="Net Recovery" value={formatINR(recommendation.expected_net_recovery)} green />
        </div>
        {response.approval_required && (
          <div
            className="rounded-lg px-3 py-2 flex items-center gap-2"
            style={{ background: "#fffbeb", border: "1px solid #fcd34d" }}
          >
            <span style={{ fontSize: 11, color: "#92400e" }}>
              Recovery action pending approval — go to{" "}
              <a href="/approvals" className="underline font-medium">
                Approvals
              </a>
            </span>
          </div>
        )}
      </div>
    );
  }

  if (priority_orders?.orders) {
    const top = priority_orders.orders.slice(0, 3);
    return (
      <div
        className="mt-2 rounded-xl p-3.5 space-y-2"
        style={{ background: "hsl(var(--bg))", border: "1px solid hsl(var(--border))" }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Top {top.length} Priority Orders
        </div>
        {top.map((o) => (
          <div key={o.order_id} className="flex items-center justify-between">
            <span className="font-mono" style={{ fontSize: 11, color: "hsl(var(--text))" }}>
              {o.order_id}
            </span>
            <div className="flex items-center gap-2">
              <RiskBadge level={o.risk_level} />
              <span className="font-mono" style={{ fontSize: 11, color: "#dc2626" }}>
                {formatINR(o.expected_revenue_at_risk)}
              </span>
            </div>
          </div>
        ))}
        <a
          href="/recovery"
          className="block text-center rounded-lg py-1.5 font-medium transition-colors hover:bg-blue-50"
          style={{ fontSize: 11, color: "hsl(var(--primary))", border: "1px solid hsl(220 87% 54% / 0.2)" }}
        >
          View full recovery queue →
        </a>
      </div>
    );
  }

  if (recovery_opportunity) {
    return (
      <div
        className="mt-2 rounded-xl p-3.5 space-y-2"
        style={{ background: "hsl(var(--bg))", border: "1px solid hsl(var(--border))" }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: "hsl(var(--text-secondary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Recovery Opportunity
        </div>
        <div className="grid grid-cols-2 gap-2">
          <DataPoint label="Revenue at Risk" value={formatINR(recovery_opportunity.total_revenue_at_risk)} red />
          <DataPoint label="Net Recovery" value={formatINR(recovery_opportunity.expected_net_recovery)} green />
          <DataPoint label="Orders Evaluated" value={`${recovery_opportunity.orders_evaluated}`} />
          <DataPoint label="Recoverable Orders" value={`${recovery_opportunity.orders_with_positive_expected_recovery}`} />
        </div>
      </div>
    );
  }

  return null;
}

function DataPoint({ label, value, green, red }: { label: string; value: string; green?: boolean; red?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "hsl(var(--text-muted))", marginBottom: 1 }}>{label}</div>
      <div
        className="font-semibold mono"
        style={{
          fontSize: 12,
          color: green ? "#059669" : red ? "#dc2626" : "hsl(var(--text))",
        }}
      >
        {value}
      </div>
    </div>
  );
}
