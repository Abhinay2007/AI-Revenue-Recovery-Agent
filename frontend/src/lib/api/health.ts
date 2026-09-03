import { apiFetch } from "./client";

export async function checkHealth(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health");
}
