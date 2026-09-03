import { Activity } from "lucide-react";
import type { AuditEntry } from "@/lib/types";
import { formatAction, formatTime } from "@/lib/format";
import { StatusBadge } from "@/components/shared/Badges";
import { ToolTrace } from "@/components/agent/ToolTrace";

export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="py-14 text-center text-sm text-muted-foreground">
        No audit entries recorded in this session yet. Actions taken in the console appear here.
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 pl-7 before:absolute before:top-2 before:bottom-2 before:left-[9px] before:w-px before:bg-border">
      {entries.map((entry, idx) => (
        <li key={entry.audit_id || idx} className="relative">
          <span className="absolute top-3 -left-7 flex size-[19px] items-center justify-center rounded-full border border-primary/40 bg-surface text-primary">
            <Activity size={10} />
          </span>
          <div className="panel p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="num text-xs font-semibold">
                  {entry.order_id || "System action"}
                </span>
                {entry.status && <StatusBadge status={entry.status} />}
              </div>
              <span className="num text-[11px] text-subtle-foreground">
                {formatTime(entry.timestamp)}
              </span>
            </div>

            <p className="mt-1.5 text-xs text-muted-foreground">{entry.summary}</p>

            <div className="num mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-2.5 text-[11px] text-subtle-foreground">
              <span>
                tool <span className="text-muted-foreground">{entry.tool}</span>
              </span>
              {entry.action && (
                <span>
                  action <span className="text-primary">{formatAction(entry.action)}</span>
                </span>
              )}
              {entry.audit_id && <span>audit {entry.audit_id.slice(0, 12)}…</span>}
            </div>

            {entry.tool_calls?.length ? <ToolTrace toolCalls={entry.tool_calls} /> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
