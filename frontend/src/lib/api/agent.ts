import { apiFetch } from "./client";
import type { AgentApprovalRequest, AgentChatRequest, AgentResponse } from "../types";

export async function agentChat(request: AgentChatRequest): Promise<AgentResponse> {
  return apiFetch<AgentResponse>("/api/v1/agent/chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function agentApprove(request: AgentApprovalRequest): Promise<AgentResponse> {
  return apiFetch<AgentResponse>("/api/v1/agent/approve", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
