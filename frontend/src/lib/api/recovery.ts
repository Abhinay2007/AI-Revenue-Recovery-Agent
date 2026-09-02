import { apiFetch } from "./client";
import type { RecoveryDecisionRequest, RecoveryDecisionResponse } from "../types";

export async function getRecoveryDecision(
  request: RecoveryDecisionRequest,
): Promise<RecoveryDecisionResponse> {
  return apiFetch<RecoveryDecisionResponse>("/api/v1/recovery/decision", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
