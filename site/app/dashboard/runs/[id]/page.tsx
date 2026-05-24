import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { notFound } from "next/navigation";

import { cpFetch } from "@/lib/cp-fetch";
import { RunStatusPill } from "@/components/dashboard/RunStatusPill";

type EventRecord = {
  id: number;
  ts: string;
  type: string;
  attempt_number: number | null;
  payload: Record<string, unknown>;
};

type RunDetail = {
  id: string;
  function_name: string;
  module_name: string | null;
  status: "in_progress" | "succeeded" | "exhausted";
  started_at: string;
  ended_at: string | null;
  attempts: number;
  final_error: string | null;
  final_source: string | null;
  events: EventRecord[];
};

function fmt(iso: string): string {
  return new Date(iso).toLocaleString();
}

const EVENT_TONE: Record<string, string> = {
  attempt_start: "text-neutral-300",
  attempt_failed: "text-red-300",
  propose_start: "text-neutral-300",
  propose_complete: "text-neutral-200",
  install_success: "text-emerald-300",
  install_failed: "text-red-300",
  safety_violation: "text-amber-300",
  verify_success: "text-emerald-300",
  repair_succeeded: "text-emerald-300",
  repair_exhausted: "text-red-300",
};

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await cpFetch<RunDetail>(`/v1/runs/${id}`);
  if (!run) notFound();

  return (
    <div className="max-w-4xl">
      <Link
        href="/dashboard/runs"
        className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-300 transition"
      >
        <ArrowLeft className="h-3 w-3" /> All runs
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-mono text-xl tracking-tight text-neutral-100">
            {run.function_name}
          </h1>
          {run.module_name ? (
            <div className="mt-1 text-xs text-neutral-500">{run.module_name}</div>
          ) : null}
        </div>
        <RunStatusPill status={run.status} />
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Attempts" value={String(run.attempts)} />
        <Stat label="Started" value={fmt(run.started_at)} />
        <Stat label="Ended" value={run.ended_at ? fmt(run.ended_at) : "—"} />
        <Stat label="Events" value={String(run.events.length)} />
      </dl>

      {run.final_error ? (
        <section className="mt-6 rounded-lg border border-red-900/50 bg-red-950/20 p-4">
          <div className="text-xs uppercase tracking-wider text-red-300/80">Final error</div>
          <pre className="mt-2 whitespace-pre-wrap break-words text-sm text-red-200">
            {run.final_error}
          </pre>
        </section>
      ) : null}

      {run.final_source ? (
        <section className="mt-6 rounded-lg border border-neutral-900 bg-neutral-950/40 p-4">
          <div className="text-xs uppercase tracking-wider text-neutral-500">Final source</div>
          <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-3 font-mono text-xs text-neutral-200">
            {run.final_source}
          </pre>
        </section>
      ) : null}

      <h2 className="mt-10 text-sm font-medium uppercase tracking-wider text-neutral-500">
        Timeline
      </h2>
      <ol className="mt-3 space-y-1.5 border-l border-neutral-900 pl-5">
        {run.events.map((e) => (
          <li key={e.id} className="relative">
            <span className="absolute -left-[1.435rem] top-2 inline-block h-1.5 w-1.5 rounded-full bg-neutral-700" />
            <div className="flex items-baseline gap-3">
              <span
                className={`font-mono text-xs ${EVENT_TONE[e.type] ?? "text-neutral-400"}`}
              >
                {e.type}
              </span>
              {e.attempt_number != null ? (
                <span className="text-xs text-neutral-600">#{e.attempt_number}</span>
              ) : null}
              <span className="ml-auto text-[11px] text-neutral-600">{fmt(e.ts)}</span>
            </div>
            {Object.keys(e.payload).length > 0 ? (
              <pre className="mt-1 overflow-x-auto rounded bg-neutral-950/60 p-2 text-[11px] text-neutral-400">
                {JSON.stringify(e.payload, null, 2)}
              </pre>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-900 bg-neutral-950/40 p-3">
      <div className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-1 truncate text-sm text-neutral-100" title={value}>
        {value}
      </div>
    </div>
  );
}
