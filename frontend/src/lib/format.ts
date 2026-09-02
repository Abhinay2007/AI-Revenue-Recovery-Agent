// ─── Number formatters ────────────────────────────────────────────────────

/**
 * Format a number as Indian Rupees with the ₹ symbol.
 * Uses Indian numbering system (lakhs, crores).
 */
export function formatINR(value: number): string {
  if (value == null || isNaN(value)) return "₹—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Compact INR — e.g. ₹1.33L for ₹133,594
 */
export function formatINRCompact(value: number): string {
  if (value == null || isNaN(value)) return "₹—";
  if (value >= 10_000_000) {
    return `₹${(value / 10_000_000).toFixed(2)}Cr`;
  }
  if (value >= 100_000) {
    return `₹${(value / 100_000).toFixed(2)}L`;
  }
  if (value >= 1_000) {
    return `₹${(value / 1_000).toFixed(1)}K`;
  }
  return formatINR(value);
}

export function formatPercent(value: number, decimals = 1): string {
  if (value == null || isNaN(value)) return "—%";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatPercentInt(value: number): string {
  if (value == null || isNaN(value)) return "—%";
  return `${Math.round(value * 100)}%`;
}

// ─── Date formatters ──────────────────────────────────────────────────────

export function formatDateTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      timeStyle: "medium",
      timeZone: "Asia/Kolkata",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "Asia/Kolkata",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "Asia/Kolkata",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function today(): string {
  return formatDate(new Date().toISOString());
}

export function greetingTime(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

// ─── Action label helpers ─────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  PARTIAL_PREPAY: "Partial Prepay",
  PREPAID_INCENTIVE: "Prepaid Incentive",
  ADDRESS_OTP: "Address OTP",
  MANUAL_REVIEW: "Manual Review",
  NO_ACTION: "No Action",
};

export function formatAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// ─── Risk helpers ─────────────────────────────────────────────────────────

export function riskColor(level: string): string {
  switch (level?.toUpperCase()) {
    case "HIGH":
      return "text-negative";
    case "MEDIUM":
      return "text-warning";
    case "LOW":
      return "text-positive";
    default:
      return "text-muted-foreground";
  }
}

export function riskBg(level: string): string {
  switch (level?.toUpperCase()) {
    case "HIGH":
      return "bg-negative-soft text-negative border-negative/20";
    case "MEDIUM":
      return "bg-warning-soft text-warning border-warning/25";
    case "LOW":
      return "bg-positive-soft text-positive border-positive/20";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

export function riskBarColor(level: string): string {
  switch (level?.toUpperCase()) {
    case "HIGH":
      return "bg-negative";
    case "MEDIUM":
      return "bg-warning";
    case "LOW":
      return "bg-positive";
    default:
      return "bg-border-strong";
  }
}

// ─── Clsx helper ─────────────────────────────────────────────────────────

export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(" ");
}
