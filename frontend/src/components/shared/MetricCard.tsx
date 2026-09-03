import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/format";
import { Skeleton } from "./States";

export type MetricTone = "neutral" | "risk" | "recovery" | "warning";

const TONE_VALUE: Record<MetricTone, string> = {
  neutral: "text-foreground",
  risk: "text-negative",
  recovery: "text-positive",
  warning: "text-warning",
};

export function MetricCard({
  label,
  value,
  sub,
  tone = "neutral",
  note,
  loading,
  unavailable,
}: {
  label: string;
  value: string;
  sub?: string | undefined;
  tone?: MetricTone | undefined;
  /** e.g. "Simulated recovery" — shown as a small qualifier */
  note?: string | undefined;
  loading?: boolean | undefined;
  unavailable?: boolean | undefined;
}) {
  return (
    <div className="panel flex flex-col gap-3 p-4 transition-colors hover:border-border-strong">
      <p className="label-xs">{label}</p>
      {loading ? (
        <>
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-3 w-36" />
        </>
      ) : unavailable ? (
        <>
          <p className="num text-2xl text-subtle-foreground">—</p>
          <p className="text-xs text-subtle-foreground">Not available from API</p>
        </>
      ) : (
        <>
          <p className={cn("num text-[26px] leading-none font-semibold", TONE_VALUE[tone])}>
            {value}
          </p>
          <div className="min-h-4 space-y-1">
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
            {note && (
              <p className="text-[10px] font-semibold tracking-[0.07em] text-warning uppercase">
                {note}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** Counts a numeric value up once it enters the viewport. */
export function useCountUp(target: number, active: boolean, duration = 1100) {
  const [value, setValue] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!active) return;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [target, active, duration]);

  return active ? value : 0;
}
