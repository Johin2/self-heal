import { cpFetch } from "@/lib/cp-fetch";
import { MetricsCharts } from "@/components/dashboard/MetricsCharts";
import { RangeSwitch } from "@/components/dashboard/RangeSwitch";

type Metrics = {
  range: string;
  total_runs: number;
  success_rate: number | null;
  by_status: { succeeded: number; exhausted: number; in_progress: number };
  avg_attempts: number | null;
  p50_duration_ms: number | null;
  p95_duration_ms: number | null;
  runs_over_time: { day: string; succeeded: number; exhausted: number }[];
  top_failing_functions: { function_name: string; count: number }[];
};

const RANGES = ["24h", "7d", "30d", "90d"] as const;

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function ms(v: number | null): string {
  if (v == null) return "—";
  if (v < 1000) return `${v.toFixed(0)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export default async function MetricsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  const { range } = await searchParams;
  const active = (RANGES as readonly string[]).includes(range ?? "")
    ? (range as string)
    : "7d";

  const data = await cpFetch<Metrics>(`/v1/metrics?range=${active}`);

  return (
    <div className="max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Metrics</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Reliability and latency, aggregated over the selected window.
          </p>
        </div>
        <RangeSwitch options={[...RANGES]} active={active} />
      </div>

      <dl className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KPI label="Total runs" value={String(data?.total_runs ?? 0)} />
        <KPI label="Success rate" value={pct(data?.success_rate ?? null)} />
        <KPI label="Avg attempts" value={data?.avg_attempts != null ? data.avg_attempts.toFixed(2) : "—"} />
        <KPI label="p95 duration" value={ms(data?.p95_duration_ms ?? null)} />
      </dl>

      {data ? <MetricsCharts data={data} /> : null}
    </div>
  );
}

function KPI({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-neutral-900 bg-neutral-950/40 p-4">
      <div className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight text-neutral-100">{value}</div>
    </div>
  );
}
