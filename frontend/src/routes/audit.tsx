import { createFileRoute } from "@tanstack/react-router";
import { useAppStore } from "@/lib/store";
import { AppShell } from "@/components/layout/AppShell";
import { AuditTimeline } from "@/components/audit/AuditTimeline";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit Log — AI Revenue Recovery Agent" },
      {
        name: "description",
        content:
          "Every agent decision, tool call, and approval recorded with timestamps for this session.",
      },
      { property: "og:title", content: "Audit Log" },
      {
        property: "og:description",
        content: "Timestamped record of agent decisions, tool calls, and approvals.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  const entries = useAppStore((s) => s.auditEntries);
  const sessionId = useAppStore((s) => s.sessionId);
  const clearAudit = useAppStore((s) => s.clearAudit);

  return (
    <AppShell
      title="Audit Log"
      subtitle="Decision trail for this session"
      actions={
        entries.length > 0 ? (
          <button
            onClick={clearAudit}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted"
          >
            Clear view
          </button>
        ) : undefined
      }
    >
      <div className="panel px-4 py-3">
        <p className="label-xs">Session</p>
        <p className="num mt-1 text-xs">{sessionId}</p>
        <p className="mt-2 text-[11px] text-subtle-foreground">
          Entries are reconstructed from audit IDs returned by the backend for this session.
        </p>
      </div>

      <AuditTimeline entries={entries} />
    </AppShell>
  );
}
