import { useQuery } from "@tanstack/react-query";
import { checkHealth } from "@/lib/api/health";
import { getMerchantAnalytics } from "@/lib/api/merchant";

const shared = {
  staleTime: 60_000,
  retry: 0 as const,
  refetchOnWindowFocus: false,
};

export function useMerchantSummary() {
  const analytics = useMerchantAnalytics();
  return { ...analytics, data: analytics.data?.summary ?? null };
}

export function useMerchantAnalytics() {
  return useQuery({
    queryKey: ["merchant-analytics"],
    queryFn: getMerchantAnalytics,
    ...shared,
  });
}

export function useRecoveryOpportunity() {
  const analytics = useMerchantAnalytics();
  return { ...analytics, data: analytics.data?.opportunity ?? null };
}

export function useActionDistribution() {
  const analytics = useMerchantAnalytics();
  return { ...analytics, data: analytics.data?.distribution ?? null };
}

export function usePriorityOrders() {
  const analytics = useMerchantAnalytics();
  return { ...analytics, data: analytics.data?.priority ?? null };
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    retry: 0,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });
}
