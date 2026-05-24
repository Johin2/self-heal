import Link from "next/link";
import { cpFetch } from "@/lib/cp-fetch";
import { RunStatusPill } from "@/components/dashboard/RunStatusPill";

type RunsPage = {
  runs: {
    id: string;
    function_name: string;
    module_name: string | null;
    status: "in_progress" | "succeeded" | "exhausted";
    started_at: string;
    ended_at: string | null;
    attempts: number;
  }[];
  next_cursor: string | null;
};

function fmt(iso: string): string {
  return new Date(iso).toLocaleString();
}

function dur(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return "—";
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default async function RunsPage() {
  const data = await cpFetch<RunsPage>("/v1/runs?limit=50");
  const runs = data?.runs ?? [];

  return (
    <div className="max-w-5xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Every <span className="font-mono text-neutral-300">@repair</span> invocation,
            most recent first.
          </p>
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="mt-10 rounded-xl border border-neutral-900 bg-neutral-950/40 p-10 text-center">
          <div className="text-sm font-medium text-neutral-200">No runs yet</div>
          <p className="mx-auto mt-2 max-w-md text-xs text-neutral-500">
            Create an API key and point the OSS library at this control plane.
            Runs land here as soon as events start arriving.
          </p>
          <Link
            href="/dashboard/keys"
            className="mt-5 inline-block rounded-lg bg-white px-3.5 py-2 text-xs font-medium text-black hover:bg-neutral-200 transition"
          >
            Create API key
          </Link>
        </div>
      ) : (
        <div className="mt-8 overflow-hidden rounded-xl border border-neutral-900 bg-neutral-950/40">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-900 bg-neutral-950/80 text-xs uppercase tracking-wider text-neutral-500">
              <tr>
                <th className="px-4 py-3 font-medium">Function</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Attempts</th>
                <th className="px-4 py-3 font-medium text-right">Duration</th>
                <th className="px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-neutral-900 last:border-0 hover:bg-neutral-950 transition"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/dashboard/runs/${r.id}`}
                      className="font-mono text-neutral-100 hover:text-white"
                    >
                      {r.function_name}
                    </Link>
                    {r.module_name ? (
                      <div className="text-xs text-neutral-500">{r.module_name}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <RunStatusPill status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-right text-neutral-300">{r.attempts}</td>
                  <td className="px-4 py-3 text-right text-neutral-300">
                    {dur(r.started_at, r.ended_at)}
                  </td>
                  <td className="px-4 py-3 text-neutral-400">{fmt(r.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
