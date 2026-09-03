import { apiFetch } from "./client";
import type { MerchantAnalytics } from "../types";

export function getMerchantAnalytics(): Promise<MerchantAnalytics> {
  return apiFetch<MerchantAnalytics>("/api/v1/merchant/analytics");
}