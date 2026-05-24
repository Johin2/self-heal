"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Data = {
  by_status: { succeeded: number; exhausted: number; in_progress: number };
  runs_over_time: { day: string; succeeded: number; exhausted: number }[];
  top_failing_functions: { function_name: string; count: number }[];
};

const TOOLTIP = {
  contentStyle: {
    background: "#0a0a0a",
    border: "1px solid #262626",
    borderRadius: "6px",
    fontSize: "12px",
  },
  itemStyle: { color: "#e5e5e5" },
  labelStyle: { color: "#a3a3a3" },
  cursor: { fill: "rgba(255,255,255,0.03)" },
};

export function MetricsCharts({ data }: { data: Data }) {
  const empty = data.runs_over_time.length === 0 && data.top_failing_functions.length === 0;
  if (empty) {
    return (
      <div className="mt-10 rounded-xl border border-neutral-900 bg-neutral-950/40 p-10 text-center text-sm text-neutral-500">
        No data in this range yet.
      </div>
    );
  }

  return (
    <>
      <section className="mt-8 rounded-xl border border-neutral-900 bg-neutral-950/40 p-4">
        <div className="px-1 text-xs uppercase tracking-wider text-neutral-500">
          Runs over time
        </div>
        <div className="mt-3 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.runs_over_time}>
              <CartesianGrid stroke="#171717" strokeDasharray="3 3" />
              <XAxis
                dataKey="day"
                stroke="#525252"
                fontSize={11}
                tickFormatter={(d) =>
                  new Date(d).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })
                }
              />
              <YAxis stroke="#525252" fontSize={11} allowDecimals={false} />
              <Tooltip {...TOOLTIP} />
              <Legend wrapperStyle={{ fontSize: 12, color: "#a3a3a3" }} />
              <Bar dataKey="succeeded" stackId="x" fill="#34d399" name="Succeeded" />
              <Bar dataKey="exhausted" stackId="x" fill="#ef4444" name="Exhausted" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-neutral-900 bg-neutral-950/40 p-4">
          <div className="px-1 text-xs uppercase tracking-wider text-neutral-500">
            By status
          </div>
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={[
                  { name: "Succeeded", value: data.by_status.succeeded, fill: "#34d399" },
                  { name: "Exhausted", value: data.by_status.exhausted, fill: "#ef4444" },
                  { name: "Running", value: data.by_status.in_progress, fill: "#f59e0b" },
                ]}
              >
                <CartesianGrid stroke="#171717" strokeDasharray="3 3" />
                <XAxis type="number" stroke="#525252" fontSize={11} allowDecimals={false} />
                <YAxis type="category" dataKey="name" stroke="#a3a3a3" fontSize={12} width={80} />
                <Tooltip {...TOOLTIP} />
                <Bar dataKey="value">
                  {data.by_status &&
                    [data.by_status.succeeded, data.by_status.exhausted, data.by_status.in_progress].map(
                      (_, i) => (
                        <Cell
                          key={i}
                          fill={["#34d399", "#ef4444", "#f59e0b"][i]}
                        />
                      )
                    )}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-900 bg-neutral-950/40 p-4">
          <div className="px-1 text-xs uppercase tracking-wider text-neutral-500">
            Top failing functions
          </div>
          {data.top_failing_functions.length === 0 ? (
            <div className="mt-8 text-center text-sm text-neutral-500">
              No exhausted runs in this range.
            </div>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.top_failing_functions.map((f) => (
                <li
                  key={f.function_name}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-neutral-900/50"
                >
                  <span className="truncate font-mono text-neutral-200" title={f.function_name}>
                    {f.function_name}
                  </span>
                  <span className="ml-3 text-xs tabular-nums text-red-300">{f.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
