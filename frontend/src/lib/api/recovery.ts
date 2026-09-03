import { apiFetch } from "./client";
import type {
  AgentResponse,
  RecoveryDecisionRequest,
  RecoveryDecisionResponse,
  RecoveryRequest,
} from "../types";

export async function getRecoveryDecision(
  request: RecoveryDecisionRequest,
): Promise<RecoveryDecisionResponse> {
  return apiFetch<RecoveryDecisionResponse>("/api/v1/recovery/decision", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function requestRecovery(request: RecoveryRequest): Promise<AgentResponse> {
  return apiFetch<AgentResponse>("/api/v1/recovery/request", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
