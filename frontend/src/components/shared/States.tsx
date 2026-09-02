import type { LucideIcon } from "lucide-react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/format";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon | undefined;
  title: string;
  description: string;
  action?: React.ReactNode | undefined;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      {Icon && (
        <div className="mb-4 flex size-11 items-center justify-center rounded-lg border border-border bg-muted">
          <Icon size={18} className="text-subtle-foreground" />
        </div>
      )}
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// export function ErrorState({
//   title = "Something went wrong",
//   message,
//   onRetry,
//   retryLabel = "Retry",
// }: {
//   title?: string | undefined;
//   message: string;
//   onRetry?: () => void | undefined;
//   retryLabel?: string | undefined;
// }) {
//   return (
//     <div
//       role="alert"
//       className="max-w-lg rounded-lg border border-negative/25 bg-negative-soft p-5"
//     >
//       <div className="flex items-center gap-2">
//         <AlertTriangle size={15} className="text-negative" />
//         <p className="text-sm font-semibold text-negative">{title}</p>
//       </div>
//       <p className="mt-2 text-sm leading-relaxed text-negative/85">{message}</p>
//       {onRetry && (
//         <button
//           onClick={onRetry}
//           className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-negative/30 bg-surface px-3 py-1.5 text-xs font-semibold text-negative transition-colors hover:bg-negative-soft"
//         >
//           <RefreshCw size={12} />
//           {retryLabel}
//         </button>
//       )}
//     </div>
//   );
// }
