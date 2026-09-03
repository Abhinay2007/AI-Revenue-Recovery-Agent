import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ActionDistribution } from "@/lib/types";
import { formatAction, formatINR } from "@/lib/format";
import { Skeleton } from "@/components/shared/States";

export function ActionDistributionChart({
  data,
  loading,
}: {
  data?: ActionDistribution | null | undefined;
  loading?: boolean | undefined;
}) {
  if (loading) return <Skeleton className="h-[220px]" />;

  if (!data?.distribution?.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Action distribution unavailable from the recovery service.
      </p>
    );
  }

  const rows = [...data.distribution]
    .sort((a, b) => b.count - a.count)
    .map((row) => ({ ...row, label: formatAction(row.action) }));

  return (
    <div>
      <div style={{ height: rows.length * 40 + 20 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 24, top: 4 }}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={122}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <Tooltip
              cursor={{ fill: "var(--surface-sunken)" }}
              contentStyle={{
                borderRadius: 8,
                border: "1px solid var(--border)",
                fontSize: 12,
                boxShadow: "var(--shadow-raised)",
              }}
              formatter={(value: number, name) =>
                name === "count" ? [`${value} orders`, "Orders"] : [String(value), String(name)]
              }
            />
            <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={16}>
              {rows.map((row) => (
                <Cell
                  key={row.action}
                  fill={row.expected_net_recovery > 0 ? "var(--primary)" : "var(--border-strong)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
        {rows.map((row) => (
          <li key={row.action} className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{row.label}</span>
            <span className="num flex items-center gap-3">
              <span className="text-subtle-foreground">{row.percentage.toFixed(1)}%</span>
              <span
                className={
                  row.expected_net_recovery > 0 ? "text-positive" : "text-subtle-foreground"
                }
              >
                {formatINR(row.expected_net_recovery)}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-subtle-foreground">
        {data.orders_evaluated} orders evaluated by the recovery engine.
      </p>
    </div>
  );
}
