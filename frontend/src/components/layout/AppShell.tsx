import { Link, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  BadgeCheck,
  Bot,
  LayoutDashboard,
  ListOrdered,
  Menu,
  ScrollText,
  TrendingUp,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/format";
import { useAppStore } from "@/lib/store";

const NAV = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/recovery", label: "Recovery", icon: TrendingUp },
  { to: "/priority-orders", label: "Priority Orders", icon: ListOrdered },
  { to: "/agent", label: "AI Agent", icon: Bot },
  { to: "/approvals", label: "Approvals", icon: BadgeCheck },
  { to: "/audit", label: "Audit Log", icon: ScrollText },
] as const;

export function AppShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string | undefined;
  actions?: ReactNode | undefined;
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pendingCount = useAppStore((s) => s.pendingApprovals.length);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="min-h-screen bg-canvas">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[232px] flex-col border-r border-border bg-surface transition-transform duration-200 lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <Link to="/" className="group flex items-center gap-2.5">
            <span className="flex size-7 items-center justify-center rounded-md bg-foreground text-[11px] font-bold text-primary-foreground">
              RR
            </span>
            <span className="leading-tight">
              <span className="block text-[13px] font-semibold">AI Revenue Recovery</span>
              <span className="block text-[10px] text-subtle-foreground">Agent Console</span>
            </span>
          </Link>
          <button
            className="lg:hidden"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={16} className="text-muted-foreground" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Main">
          <p className="label-xs px-2 pb-2">Recovery</p>
          <ul className="space-y-0.5">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavItem
                  {...item}
                  active={pathname === item.to}
                  badge={item.to === "/approvals" && pendingCount > 0 ? pendingCount : undefined}
                  onNavigate={() => setMobileOpen(false)}
                />
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-border p-3">
          <p className="text-[10px] leading-relaxed font-semibold tracking-[0.07em] text-subtle-foreground uppercase">
            Built for
          </p>
          <img
            src="/razorpay-wordmark.png"
            alt="Razorpay"
            className="mt-1.5 h-7 w-auto rounded bg-white px-1.5 py-1"
          />
          <p className="mt-1.5 text-[11px] text-muted-foreground">AI Buildathon</p>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-foreground/20 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Main column */}
      <div className="lg:pl-[232px]">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-surface/90 px-4 backdrop-blur-sm md:px-6">
          <button
            className="lg:hidden"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={18} className="text-muted-foreground" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold">{title}</h1>
            {subtitle && (
              <p className="hidden truncate text-xs text-muted-foreground sm:block">{subtitle}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2 md:gap-3">
            {actions}
            <span className="hidden items-center gap-2 border-l border-border pl-3 text-xs md:flex">
              <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[10px] font-semibold">
                DS
              </span>
              <span className="text-muted-foreground">Demo Store</span>
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-[1400px] space-y-4 px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function NavItem({
  to,
  label,
  icon: Icon,
  active,
  badge,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: typeof Activity;
  active?: boolean | undefined;
  badge?: number | undefined;
  onNavigate?: () => void | undefined;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={cn(
        "relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors",
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      {active && (
        <span className="absolute top-1.5 bottom-1.5 -left-2 w-[2px] rounded-full bg-primary" />
      )}
      <Icon size={15} className={active ? "text-primary" : "text-subtle-foreground"} />
      <span className="flex-1">{label}</span>
      {badge !== undefined && (
        <span className="num rounded bg-warning-soft px-1.5 text-[10px] font-semibold text-warning">
          {badge}
        </span>
      )}
    </Link>
  );
}
