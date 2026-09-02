// ---------------------------------------------------------------------------
// Types derived from backend Pydantic schemas — do not fabricate fields
// ---------------------------------------------------------------------------

// ─── Agent API ──────────────────────────────────────────────────────────────

export interface AgentChatRequest {
  message: string;
  session_id?: string | undefined;
}

export interface AgentApprovalRequest {
  pending_action_id: string;
  approved: boolean;
  approved_action?: string | undefined;
  session_id?: string | undefined;
}

export interface ToolCallRecord {
  tool_name: string;
  inputs_summary: Record<string, unknown>;
  outputs_summary?: Record<string, unknown>;
  error?: string | undefined;
  timestamp: string;
}

export interface RiskResult {
  order_id: string;
  rto_probability: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  reasons: Array<{ feature?: string; value?: unknown; impact?: string; description?: string }>;
}

export interface RevenueRiskResult {
  order_id: string;
  order_amount: number;
  rto_probability: number;
  expected_revenue_at_risk: number;
}

export interface ExecutionResult {
  execution_id: string;
  status: "SIMULATED_SUCCESS" | "BLOCKED" | "FAILED";
  action: string;
  order_id: string;
  timestamp: string;
  reason: string;
}

export interface PolicyResult {
  order_id: string;
  action: string;
  allowed: boolean;
  reasons: string[];
  violations: string[];
  policy_version: string;
}

export interface MerchantSummary {
  merchant_id: string;
  merchant_context_source: string;
  total_orders: number;
  cod_orders: number;
  prepaid_orders: number;
  total_order_value: number;
  rto_orders: number;
  rto_value: number;
  rto_rate: number;
  predicted_revenue_at_risk: number;
  scored_cod_orders: number;
  ranking_note: string;
}

export interface PriorityOrder {
  order_id: string;
  amount: number;
  payment_method: string;
  rto_probability: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  expected_revenue_at_risk: number;
  recommended_action: string;
  expected_gross_recovery: number;
  expected_intervention_cost: number;
  expected_net_recovery: number;
}

export interface PriorityOrdersResult {
  merchant_id: string;
  ranking_metric: string;
  limit: number;
  minimum_rto_probability: number;
  minimum_order_value: number;
  orders: PriorityOrder[];
}

export interface RecoveryOpportunity {
  merchant_id: string;
  orders_evaluated: number;
  orders_with_positive_expected_recovery: number;
  total_revenue_at_risk: number;
  expected_gross_recovery: number;
  expected_intervention_cost: number;
  expected_net_recovery: number;
  assumption_source: string;
}

export interface ActionDistributionRow {
  action: string;
  count: number;
  percentage: number;
  expected_net_recovery: number;
}

export interface ActionDistribution {
  merchant_id: string;
  orders_evaluated: number;
  distribution: ActionDistributionRow[];
}

export interface MerchantAnalytics {
  summary: MerchantSummary;
  opportunity: RecoveryOpportunity;
  distribution: ActionDistribution;
  priority: PriorityOrdersResult;
}

export interface RecoveryRecommendation {
  order_id: string;
  recommended_action: string;
  reason: string;
  reason_codes: string[];
  rto_probability: number;
  order_amount: number;
  expected_revenue_at_risk: number;
  candidate_actions: CandidateAction[];
  expected_recovered_revenue: number;
  expected_intervention_cost: number;
  expected_net_recovery: number;
  policy_checks: Record<string, unknown[]>;
  assumption_source: string;
  audit_event?: Record<string, unknown>;
}

export interface CandidateAction {
  action: string;
  permitted: boolean;
  expected_recovered_revenue: number;
  expected_intervention_cost: number;
  expected_net_recovery: number;
  success_probability: number;
  assumption_source: string;
}

export interface AgentResponse {
  status: "ANALYSIS" | "RECOMMENDATION" | "EXECUTED_ACTION" | "FAILED";
  summary: string;
  natural_language_response: string;
  session_id: string;
  intent?: string | undefined;
  order_id?: string | undefined;
  risk?: RiskResult | undefined;
  revenue_at_risk?: RevenueRiskResult | undefined;
  recommendation?: RecoveryRecommendation | undefined;
  merchant_summary?: MerchantSummary | undefined;
  priority_orders?: PriorityOrdersResult | undefined;
  recovery_opportunity?: RecoveryOpportunity | undefined;
  action_distribution?: ActionDistribution | undefined;
  approval_required: boolean;
  pending_action_id?: string | undefined;
  policy_status?: PolicyResult | undefined;
  execution_status?: ExecutionResult | undefined;
  audit_id?: string | undefined;
  tool_calls: Array<ToolCallRecord | Record<string, unknown>>;
}

// ─── Recovery decision API ───────────────────────────────────────────────────

export interface RecoveryDecisionRequest {
  order_id: string;
  amount: number;
  rto_probability: number;
  attempt_count?: number | undefined;
}

export interface RecoveryDecisionResponse {
  order_id: string;
  recommended_action: string;
  reason: string;
  reason_codes: string[];
  rto_probability: number;
  order_amount: number;
  expected_revenue_at_risk: number;
  candidate_actions: CandidateAction[];
  expected_recovered_revenue: number;
  expected_intervention_cost: number;
  expected_net_recovery: number;
  policy_checks: Record<string, unknown[]>;
  assumption_source: string;
  audit_event: Record<string, unknown>;
}

// ─── Frontend state ─────────────────────────────────────────────────────────

export interface PendingApprovalItem {
  pending_action_id: string;
  order_id: string;
  recommended_action: string;
  session_id: string;
  expected_net_recovery?: number | undefined;
  expected_intervention_cost?: number | undefined;
  expected_recovered_revenue?: number | undefined;
  expected_revenue_at_risk?: number | undefined;
  rto_probability?: number | undefined;
  risk_level?: string | undefined;
  policy_allowed?: boolean | undefined;
  created_at: string;
}

export interface AuditEntry {
  audit_id: string;
  timestamp: string;
  session_id: string;
  order_id?: string | undefined;
  tool: string;
  action?: string | undefined;
  status?: string | undefined;
  summary: string;
  tool_calls?: Array<ToolCallRecord | Record<string, unknown>>;
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
