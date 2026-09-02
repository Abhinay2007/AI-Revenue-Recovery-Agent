import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  Coins,
  Gauge,
  LineChart,
  ListOrdered,
  MessageSquareText,
  PhoneCall,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Truck,
  Workflow,
} from "lucide-react";
import { formatINR, formatPercent } from "@/lib/format";
import { useMerchantSummary, useRecoveryOpportunity } from "@/hooks/useRecovery";
import { Skeleton } from "@/components/shared/States";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AI Revenue Recovery Agent — Recover COD revenue before it's lost" },
      {
        name: "description",
        content:
          "An agentic console that scores RTO risk on COD orders, quantifies revenue at risk, and recommends policy-checked recovery actions with human approval.",
      },
      {
        property: "og:title",
        content: "AI Revenue Recovery Agent — Recover COD revenue before it's lost",
      },
      {
        property: "og:description",
        content:
          "Score RTO risk, quantify revenue at risk, and approve policy-checked recovery actions.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});

/* ── motion helpers ────────────────────────────────────────────────────── */

function useInView<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setInView(true);
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => entries[0]?.isIntersecting && setInView(true),
      { threshold: 0.05 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, inView };
}

function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number | undefined;
  className?: string | undefined;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "none" : "translateY(14px)",
        transition: `opacity .6s ease ${delay}ms, transform .6s cubic-bezier(.16,1,.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/** Global scroll progress (0..1) */
function useScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setP(max > 0 ? window.scrollY / max : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return p;
}

/** Scroll offset for light parallax */
function useScrollY() {
  const [y, setY] = useState(0);
  useEffect(() => {
    const onScroll = () => setY(window.scrollY);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return y;
}

/** Index of the stage currently centred in a sticky scroll section */
function useStageScroll(count: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      if (total <= 0) return;
      const raw = (-rect.top / total) * count;
      setActive(Math.min(count - 1, Math.max(0, Math.floor(raw))));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [count]);
  return { ref, active };
}

/* ── content ───────────────────────────────────────────────────────────── */

const STAGES = [
  {
    icon: Gauge,
    title: "Score",
    body: "Every COD order is scored for return-to-origin probability with the reasons that drove the score.",
    detail: "Address quality, pincode history, order value, buyer history and channel signals.",
  },
  {
    icon: Boxes,
    title: "Quantify",
    body: "Risk is converted into rupees at risk, so the queue is ordered by money, not by guesswork.",
    detail: "Risk × order value × logistics cost gives a comparable exposure per order.",
  },
  {
    icon: Workflow,
    title: "Recommend",
    body: "Candidate interventions are evaluated on expected net recovery and filtered by policy.",
    detail:
      "Prepaid conversion nudges, confirmation calls, address fixes, or deliberate no-action.",
  },
  {
    icon: BadgeCheck,
    title: "Approve",
    body: "Nothing runs without a human approval before it reaches the customer.",
    detail: "Reviewers see risk, economics, policy version and the action about to be dispatched.",
  },
  {
    icon: ScrollText,
    title: "Audit",
    body: "Each decision keeps its tool trace and audit ID, so any number can be traced back.",
    detail: "Every tool call, timestamp and outcome is replayable from the audit log.",
  },
];

const FEATURES = [
  {
    icon: LineChart,
    title: "Revenue-at-risk dashboard",
    body: "Live exposure, RTO rate and recoverable value read straight from the recovery service.",
    to: "/overview" as const,
  },
  {
    icon: ListOrdered,
    title: "Money-ranked priority queue",
    body: "Orders sorted by rupees at risk with search, risk filters and sortable columns.",
    to: "/priority-orders" as const,
  },
  {
    icon: BrainCircuit,
    title: "Grounded AI agent",
    body: "Ask about any order in natural language; answers come with the tool trace behind them.",
    to: "/agent" as const,
  },
  {
    icon: ShieldCheck,
    title: "Policy-gated approvals",
    body: "Every recommended action is validated against the active policy version before review.",
    to: "/approvals" as const,
  },
  {
    icon: ScrollText,
    title: "Replayable audit log",
    body: "Session-level timeline of decisions, approvals and executed recovery actions.",
    to: "/audit" as const,
  },
  {
    icon: Coins,
    title: "Deterministic economics",
    body: "Rupee figures are computed in the backend — the language model never invents a number.",
    to: "/recovery" as const,
  },
];

const SIGNALS = [
  { icon: Truck, label: "Pincode RTO history", weight: 0.86 },
  { icon: Activity, label: "Buyer order history", weight: 0.74 },
  { icon: Coins, label: "Order value band", weight: 0.62 },
  { icon: MessageSquareText, label: "Address completeness", weight: 0.55 },
  { icon: PhoneCall, label: "Contact reachability", weight: 0.41 },
];

const TICKER = [
  "RTO risk scoring",
  "Revenue at risk",
  "Expected net recovery",
  "Prepaid conversion nudge",
  "Confirmation call",
  "Address correction",
  "Policy version check",
  "Human approval",
  "Tool trace",
  "Audit ID",
];

const FAQ = [
  {
    q: "Where do the numbers come from?",
    a: "Every figure on the console is read live from the recovery service. When the service returns nothing, the UI shows an unavailable state instead of a placeholder value.",
  },
  {
    q: "Can the agent act on its own?",
    a: "No. The agent recommends; a reviewer approves. Recovery actions are queued for human approval before anything is dispatched to a customer.",
  },
  {
    q: "How is an action chosen?",
    a: "Candidate interventions are scored on expected net recovery — recovered value minus intervention cost — then filtered against the active policy version.",
  },
  {
    q: "What if a decision is questioned later?",
    a: "Open the audit log. Each decision carries its tool calls, timestamps and audit ID, so any number can be traced back to the call that produced it.",
  },
];

/* ── page ──────────────────────────────────────────────────────────────── */

function Landing() {
  const summary = useMerchantSummary();
  const opportunity = useRecoveryOpportunity();
  const s = summary.data;
  const o = opportunity.data;
  const progress = useScrollProgress();
  const scrollY = useScrollY();
  const stages = useStageScroll(STAGES.length);

  return (
    <main className="relative min-h-screen overflow-x-clip bg-canvas">
      {/* scroll progress */}
      <div
        className="fixed top-0 left-0 z-50 h-0.5 bg-primary"
        style={{ width: `${progress * 100}%`, transition: "width .1s linear" }}
      />

      {/* infinite ambient background */}
      <AmbientBackground />

      <header className="sticky top-0 z-30 border-b border-border bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <span className="relative flex size-7 items-center justify-center rounded-md bg-foreground text-[11px] font-bold text-primary-foreground">
              RR
              <span className="absolute inset-0 rounded-md border border-primary/50 ping-ring" />
            </span>
            <span className="text-[13px] font-semibold">AI Revenue Recovery Agent</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/overview"
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              Open console <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative border-b border-border">
        <div
          className="pointer-events-none absolute inset-0 grid-pan opacity-70"
          style={{
            maskImage: "radial-gradient(ellipse 80% 60% at 50% 30%, black, transparent 75%)",
            WebkitMaskImage: "radial-gradient(ellipse 80% 60% at 50% 30%, black, transparent 75%)",
          }}
        />
        <div className="relative mx-auto max-w-6xl px-5 py-24 sm:py-32">
          <div style={{ transform: `translateY(${Math.min(scrollY, 400) * 0.06}px)` }}>
            <Reveal>
              <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-[11px] font-semibold tracking-[0.06em] text-muted-foreground uppercase backdrop-blur">
                <Sparkles size={12} className="text-primary" />
                Cash on delivery · Return to origin
              </p>
              <h1 className="mt-5 max-w-3xl text-[40px] leading-[1.06] font-semibold tracking-[-0.03em] text-balance sm:text-[58px]">
                Revenue leaks quietly. This agent finds it while the order is still in play.
              </h1>
              <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
                The Revenue Recovery Agent scores return risk on every COD order, prices the
                exposure in rupees, and proposes the intervention with the highest expected net
                recovery — under policy, with a human in the loop.
              </p>
            </Reveal>

            <Reveal delay={120} className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                to="/overview"
                className="group inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2.5 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-90"
              >
                View live recovery data
                <ArrowRight
                  size={14}
                  className="transition-transform group-hover:translate-x-0.5"
                />
              </Link>
              <Link
                to="/agent"
                className="rounded-md border border-border-strong px-4 py-2.5 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                Ask the agent
              </Link>
            </Reveal>
          </div>

          {/* Live figures — only real backend values */}
          <Reveal delay={220} className="mt-16">
            <div className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3">
              {/* <LiveStat
                label="Predicted revenue at risk"
                value={s ? formatINR(s.predicted_revenue_at_risk) : null}
                sub={s ? `${s.scored_cod_orders} scored COD orders` : "Awaiting recovery service"}
                loading={summary.isLoading}
                tone="risk"
              /> */}
              <LiveStat
                label="Expected net recovery"
                value={o ? formatINR(o.expected_net_recovery) : null}
                sub={
                  o
                    ? `${o.orders_with_positive_expected_recovery} recoverable orders`
                    : "Awaiting recovery service"
                }
                loading={opportunity.isLoading}
                tone="recovery"
              />
              {/* <LiveStat
                label="Historical RTO rate"
                value={s ? formatPercent(s.rto_rate, 2) : null}
                sub={
                  s
                    ? `${s.rto_orders} returns of ${s.total_orders} orders`
                    : "Awaiting recovery service"
                }
                loading={summary.isLoading}
              /> */}
            </div>
            <p className="mt-2.5 text-[11px] text-subtle-foreground">
              Figures are read live from the recovery service. When live data is unavailable no
              values are shown — nothing on this page is illustrative.
            </p>
          </Reveal>
        </div>
      </section>

      {/* Infinite ticker */}
      <section className="relative overflow-hidden border-b border-border bg-surface/60 py-3.5">
        <div className="flex w-max marquee-x gap-8 whitespace-nowrap">
          {[...TICKER, ...TICKER].map((item, i) => (
            <span
              key={`${item}-${i}`}
              className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.08em] text-subtle-foreground uppercase"
            >
              <span className="size-1 rounded-full bg-primary" />
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* Feature grid */}
      <section className="relative border-b border-border">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <Reveal>
            <p className="label-xs">Inside the console</p>
            <h2 className="mt-3 max-w-2xl text-[28px] leading-tight font-semibold tracking-[-0.02em] sm:text-[34px]">
              Six surfaces that turn return risk into recovered rupees.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 70}>
                <Link
                  to={f.to}
                  className="group panel relative block h-full overflow-hidden p-5 transition-colors hover:border-border-strong"
                >
                  <span className="pointer-events-none absolute -top-16 -right-16 size-32 rounded-full bg-primary/10 opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100" />
                  <span className="flex size-9 items-center justify-center rounded-lg bg-primary-soft">
                    <f.icon size={16} className="text-primary" />
                  </span>
                  <h3 className="mt-4 text-sm font-semibold">{f.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
                    {f.body}
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 text-[11px] font-semibold text-primary">
                    Open
                    <ArrowRight
                      size={12}
                      className="transition-transform group-hover:translate-x-0.5"
                    />
                  </span>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Sticky scroll pipeline */}
      <section ref={stages.ref} className="relative border-b border-border bg-surface">
        <div className="sticky top-14 mx-auto max-w-6xl px-5 py-16">
          <p className="label-xs">The loop</p>
          <h2 className="mt-3 max-w-xl text-[28px] leading-tight font-semibold tracking-[-0.02em] sm:text-[34px]">
            Five deterministic steps. One reversible decision at the end.
          </h2>

          <div className="mt-10 grid gap-8 lg:grid-cols-[1.1fr_1fr]">
            <ol className="space-y-2">
              {STAGES.map((stage, i) => {
                const on = i === stages.active;
                return (
                  <li
                    key={stage.title}
                    className={`flex items-center gap-4 rounded-lg border px-4 py-3 transition-all duration-500 ${
                      on
                        ? "border-border-strong bg-canvas"
                        : "border-transparent bg-transparent opacity-45"
                    }`}
                  >
                    <span className="num w-7 text-xs text-subtle-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span
                      className={`flex size-9 shrink-0 items-center justify-center rounded-lg border border-border ${
                        on ? "bg-primary-soft" : "bg-canvas"
                      }`}
                    >
                      <stage.icon
                        size={16}
                        className={on ? "text-primary" : "text-muted-foreground"}
                      />
                    </span>
                    <div>
                      <h3 className="text-sm font-semibold">{stage.title}</h3>
                      <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">
                        {stage.body}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="panel relative overflow-hidden p-6">
              <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent scan-sweep" />
              <p className="label-xs">
                Step {stages.active + 1} of {STAGES.length}
              </p>
              <h3 className="mt-3 text-[22px] font-semibold tracking-[-0.02em]">
                {STAGES[stages.active]?.title}
              </h3>
              <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
                {STAGES[stages.active]?.detail}
              </p>
              <FlowDiagram active={stages.active} />
            </div>
          </div>
        </div>
        {/* scroll runway that drives the sticky section */}
        <div style={{ height: `${STAGES.length * 45}vh` }} />
      </section>

      {/* Risk signals with animated weights */}
      <section className="relative border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-24 lg:grid-cols-2">
          <Reveal>
            <p className="label-xs">What the score reads</p>
            <h2 className="mt-3 text-[28px] leading-tight font-semibold tracking-[-0.02em] sm:text-[34px]">
              Risk is explained, not asserted.
            </h2>
            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-muted-foreground">
              Each score arrives with the signals that drove it, so a reviewer can agree or disagree
              with a reason rather than a number. The relative emphasis below illustrates the signal
              families the model reads — the live per-order contributions are shown in the order
              drawer.
            </p>
            <Link
              to="/priority-orders"
              className="mt-6 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary"
            >
              See scored orders <ArrowRight size={13} />
            </Link>
          </Reveal>
          <div className="space-y-3">
            {SIGNALS.map((sig, i) => (
              <SignalBar key={sig.label} {...sig} delay={i * 90} />
            ))}
          </div>
        </div>
      </section>

      {/* Guarantees */}
      <section className="relative border-b border-border bg-surface">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-24 lg:grid-cols-2">
          <Reveal>
            <p className="label-xs">Why it can be trusted</p>
            <h2 className="mt-3 text-[28px] leading-tight font-semibold tracking-[-0.02em] sm:text-[34px]">
              The model advises. The rules decide. A person approves.
            </h2>
            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-muted-foreground">
              Recovery economics are computed deterministically in the backend, so the language
              model never invents a rupee figure. Actions are checked against a versioned policy,
              and every recommendation carries the tool trace that produced it.
            </p>
          </Reveal>
          <div className="space-y-3">
            {[
              {
                icon: ShieldCheck,
                title: "Policy-gated actions",
                body: "Each candidate intervention is validated against the active policy version before it can be recommended.",
              },
              {
                icon: BadgeCheck,
                title: "Human approval required",
                body: "Recovery execution is queued for a human approval before anything is dispatched.",
              },
              {
                icon: ScrollText,
                title: "Traceable by design",
                body: "Tool calls, timestamps, and audit IDs are attached to every decision the agent makes.",
              },
            ].map((item, i) => (
              <Reveal key={item.title} delay={i * 90}>
                <div className="panel flex gap-3.5 bg-canvas p-4">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft">
                    <item.icon size={15} className="text-primary" />
                  </span>
                  <div>
                    <h3 className="text-[13px] font-semibold">{item.title}</h3>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                      {item.body}
                    </p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative border-b border-border">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <Reveal>
            <p className="label-xs">Questions a reviewer asks</p>
            <h2 className="mt-3 max-w-xl text-[28px] leading-tight font-semibold tracking-[-0.02em] sm:text-[34px]">
              Answers before the first approval.
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {FAQ.map((item, i) => (
              <Reveal key={item.q} delay={i * 80}>
                <div className="panel h-full p-5">
                  <h3 className="text-[13px] font-semibold">{item.q}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{item.a}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden bg-surface">
        <span className="aurora top-[-40%] left-1/2 size-[520px] -translate-x-1/2 bg-primary/25" />
        <div className="relative mx-auto max-w-6xl px-5 py-24 text-center">
          <Reveal>
            <h2 className="mx-auto max-w-2xl text-[30px] leading-tight font-semibold tracking-[-0.02em] text-balance sm:text-[38px]">
              Open the console and work today's at-risk orders.
            </h2>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link
                to="/overview"
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-5 py-2.5 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-90"
              >
                Open recovery console <ArrowRight size={14} />
              </Link>
              <Link
                to="/recovery"
                className="rounded-md border border-border-strong px-5 py-2.5 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                See the recovery queue
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="relative border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-[11px] text-subtle-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2.5">
            Built for
            <img
              src="/razorpay-wordmark.png"
              alt="Razorpay"
              className="h-6 w-auto rounded bg-white px-1.5 py-0.5"
            />
            AI Buildathon
          </span>
          <p>AI Revenue Recovery track</p>
        </div>
      </footer>
    </main>
  );
}

/* ── pieces ────────────────────────────────────────────────────────────── */

function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <span
        className="aurora top-[-18%] left-[-10%] size-[620px] bg-primary/25"
        style={{ animationDuration: "28s" }}
      />
      <span
        className="aurora top-[30%] right-[-14%] size-[520px] bg-positive/20"
        style={{ animationDuration: "34s", animationDelay: "-6s" }}
      />
      <span
        className="aurora bottom-[-20%] left-[25%] size-[560px] bg-negative/15"
        style={{ animationDuration: "40s", animationDelay: "-14s" }}
      />
    </div>
  );
}

function FlowDiagram({ active }: { active: number }) {
  return (
    <svg viewBox="0 0 320 80" className="mt-6 w-full">
      <line
        x1="16"
        y1="40"
        x2="304"
        y2="40"
        stroke="var(--border-strong)"
        strokeWidth="1.5"
        strokeDasharray="6 8"
        className="dash-flow"
      />
      {STAGES.map((_, i) => {
        const x = 16 + i * 72;
        const on = i <= active;
        return (
          <g key={i}>
            {i === active && (
              <circle
                cx={x}
                cy={40}
                r={14}
                fill="var(--primary)"
                opacity={0.18}
                className="float-y"
              />
            )}
            <circle
              cx={x}
              cy={40}
              r={7}
              fill={on ? "var(--primary)" : "var(--surface-sunken)"}
              stroke="var(--border-strong)"
            />
          </g>
        );
      })}
    </svg>
  );
}

function SignalBar({
  icon: Icon,
  label,
  weight,
  delay,
}: {
  icon: typeof Truck;
  label: string;
  weight: number;
  delay: number;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className="panel p-4">
      <div className="flex items-center gap-2.5">
        <Icon size={14} className="text-primary" />
        <span className="text-[13px] font-semibold">{label}</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-sunken">
        <div
          className="h-full rounded-full bg-primary"
          style={{
            width: inView ? `${weight * 100}%` : "0%",
            transition: `width 1s cubic-bezier(.16,1,.3,1) ${delay}ms`,
          }}
        />
      </div>
    </div>
  );
}

function LiveStat({
  label,
  value,
  sub,
  loading,
  tone,
}: {
  label: string;
  value: string | null;
  sub: string;
  loading?: boolean;
  tone?: "risk" | "recovery";
}) {
  return (
    <div className="bg-surface p-5">
      <p className="label-xs">{label}</p>
      {loading ? (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-3 w-40" />
        </div>
      ) : (
        <>
          <p
            className={`num mt-3 text-[26px] leading-none font-semibold ${
              value == null
                ? "text-subtle-foreground"
                : tone === "risk"
                  ? "text-negative"
                  : tone === "recovery"
                    ? "text-positive"
                    : ""
            }`}
          >
            {value ?? "—"}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">{sub}</p>
        </>
      )}
    </div>
  );
}
