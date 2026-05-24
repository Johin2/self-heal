import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function DashboardHome() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Welcome. Once your library starts shipping events, you&apos;ll see runs and
        metrics here. Start by creating an API key.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Tile
          href="/dashboard/keys"
          title="Create your first API key"
          body="Use it in your code via ControlPlaneClient(api_key=...)."
        />
        <Tile
          href="/dashboard/runs"
          title="See incoming runs"
          body="Every @repair invocation appears here as soon as events arrive."
        />
        <Tile
          href="/dashboard/metrics"
          title="Reliability metrics"
          body="Success rate, attempts, latency, cost — over any time window."
        />
        <Tile
          href="/dashboard/policy"
          title="Set policy"
          body="Block dangerous proposals or get notified before they install."
        />
      </div>
    </div>
  );
}

function Tile({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link
      href={href}
      className="group block rounded-xl border border-neutral-900 bg-neutral-950/40 p-5 hover:border-neutral-800 hover:bg-neutral-950 transition"
    >
      <div className="flex items-start justify-between">
        <div className="text-sm font-medium text-neutral-100">{title}</div>
        <ArrowRight className="h-4 w-4 text-neutral-600 group-hover:text-neutral-300 group-hover:translate-x-0.5 transition" />
      </div>
      <div className="mt-2 text-xs text-neutral-500">{body}</div>
    </Link>
  );
}
