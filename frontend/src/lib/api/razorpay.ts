import { apiFetch } from "./client";
import type {
  RazorpayConnectivity,
  RazorpayMappingResponse,
  RazorpayTestOrderRequest,
  RazorpayTestOrderResponse,
} from "../types";

export function getRazorpayConnectivity(razorpayOrderId?: string) {
  const query = razorpayOrderId ? `?razorpay_order_id=${encodeURIComponent(razorpayOrderId)}` : "";
  return apiFetch<RazorpayConnectivity>(`/api/v1/razorpay/connectivity${query}`);
}

export function createRazorpayTestOrder(request: RazorpayTestOrderRequest) {
  return apiFetch<RazorpayTestOrderResponse>("/api/v1/razorpay/test-orders", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getRazorpayMapping(internalOrderId: string) {
  return apiFetch<RazorpayMappingResponse>(
    `/api/v1/razorpay/test-orders/internal/${encodeURIComponent(internalOrderId)}`,
  );
}
