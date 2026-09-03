import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/layout/AppShell";
import { AgentConsole } from "@/components/agent/AgentConsole";

type AgentSearch = { order?: string | undefined };

export const Route = createFileRoute("/agent")({
  validateSearch: (search: Record<string, unknown>): AgentSearch => ({
    order: typeof search["order"] === "string" ? (search["order"] as string) : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Recovery Agent Console — AI Revenue Recovery Agent" },
      {
        name: "description",
        content:
          "Ask the recovery agent about revenue at risk and specific orders. Every answer is grounded in backend tool outputs.",
      },
      { property: "og:title", content: "Recovery Agent Console" },
      {
        property: "og:description",
        content: "Grounded, tool-traced answers about revenue at risk and order recovery.",
      },
    ],
  }),
  component: AgentPage,
});

function AgentPage() {
  const { order } = Route.useSearch();

  return (
    <AppShell
      title="Recovery Agent"
      subtitle="Grounded in deterministic risk, revenue, and policy tools"
    >
      <AgentConsole initialOrder={order} />
    </AppShell>
  );
}
