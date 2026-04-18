import { CodeSample } from "@/components/CodeSample";
import { WaitlistForm } from "@/components/WaitlistForm";
import { ArrowUpRight, ShieldCheck, GitBranch, Activity } from "lucide-react";

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col">
      <div className="pointer-events-none absolute inset-0 dot-grid opacity-60" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[480px] hero-glow" />

      {/* Nav */}
      <header className="relative z-10 mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 font-mono text-sm tracking-tight">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span>self-heal</span>
          <span className="ml-2 rounded-md border border-neutral-800 px-1.5 py-0.5 text-xs text-neutral-500">
            v0.4.0
          </span>
        </div>
        <nav className="flex items-center gap-6 text-sm text-neutral-400">
          <a
            href="https://github.com/Johin2/self-heal"
            target="_blank"
            rel="noreferrer"
            className="hover:text-white transition"
          >
            GitHub
          </a>
          <a
            href="https://pypi.org/project/self-heal-llm/"
            target="_blank"
            rel="noreferrer"
            className="hover:text-white transition"
          >
            PyPI
          </a>
          <a
            href="#waitlist"
            className="rounded-md border border-neutral-800 bg-white px-3 py-1.5 text-xs font-medium text-black hover:bg-neutral-200 transition"
          >
            Join waitlist
          </a>
        </nav>
      </header>

      {/* Hero */}
      <section className="relative z-10 mx-auto w-full max-w-5xl px-6 pt-16 pb-24 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-neutral-800 bg-neutral-950/50 px-3 py-1 text-xs text-neutral-400">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Ship agents to production with a repair loop, audit trail, and sandbox
        </div>
        <h1 className="mx-auto mt-6 max-w-3xl text-balance text-5xl font-semibold tracking-tight sm:text-6xl">
          The reliability layer for AI agents
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-neutral-400">
          Your LLM agents fail silently in production. self-heal catches the
          failure, proposes a fix with memory of prior attempts, verifies it
          against your tests, and retries until it passes. One decorator.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <a
            href="https://github.com/Johin2/self-heal"
            target="_blank"
            rel="noreferrer"
            className="group inline-flex items-center gap-1.5 rounded-md bg-white px-4 py-2.5 text-sm font-medium text-black hover:bg-neutral-200 transition"
          >
            View on GitHub
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </a>
          <code className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2.5 font-mono text-sm text-neutral-300">
            pip install self-heal-llm
          </code>
        </div>
      </section>

      {/* Code sample */}
      <section className="relative z-10 mx-auto w-full max-w-3xl px-6">
        <CodeSample />
        <p className="mt-3 text-center text-xs text-neutral-500">
          Works with Claude, OpenAI, Gemini, and 100+ providers via LiteLLM.
          Sync and async. One decorator.
        </p>
      </section>

      {/* Benchmark numbers */}
      <section className="relative z-10 mx-auto mt-24 w-full max-w-5xl px-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <Stat
            label="Default suite (19 hand-written bugs)"
            naive="16 / 19 (84%)"
            healed="18 / 19 (95%)"
          />
          <Stat
            label="QuixBugs (31 classic bugs)"
            naive="27 / 31 (87%)"
            healed="29 / 31 (94%)"
          />
          <ProvidersCard />
        </div>
        <p className="mt-6 text-center text-xs text-neutral-500">
          Gemini 2.5 Flash, 3 max attempts, v0.4 harness. Full numbers in{" "}
          <a
            href="https://github.com/Johin2/self-heal/blob/main/benchmarks/RESULTS.md"
            target="_blank"
            rel="noreferrer"
            className="underline decoration-neutral-700 underline-offset-2 hover:text-neutral-300 transition"
          >
            benchmarks/RESULTS.md
          </a>
          .
        </p>
      </section>

      {/* Features */}
      <section className="relative z-10 mx-auto mt-24 w-full max-w-5xl px-6">
        <h2 className="text-center text-sm font-medium uppercase tracking-widest text-neutral-500">
          What the library ships today
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
          <Feature
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Three-layer safety"
            body="AST rails block dangerous calls. Subprocess sandbox runs proposals in python -I with pickle IPC. Opt-in, combinable."
          />
          <Feature
            icon={<GitBranch className="h-5 w-5" />}
            title="pytest --heal-apply"
            body="Your failing tests trigger repair. libcst writes the accepted fix back to the file with a git-dirty guard and backup."
          />
          <Feature
            icon={<Activity className="h-5 w-5" />}
            title="Streaming + async"
            body="Native apropose() on all four adapters. propose_chunk events stream tokens for agent UIs and observability."
          />
        </div>
      </section>

      {/* Waitlist */}
      <section
        id="waitlist"
        className="relative z-10 mx-auto mt-28 w-full max-w-3xl px-6 pb-24 text-center"
      >
        <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          The hosted control plane is coming
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-pretty text-neutral-400">
          Audit log, policy engine, approval workflows, per-function health
          dashboards. Built on top of the OSS library. Bring your own API keys.
        </p>
        <div className="mt-8 flex justify-center">
          <WaitlistForm />
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 mx-auto w-full max-w-5xl border-t border-neutral-900 px-6 py-8 text-xs text-neutral-500">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            MIT-licensed. Built by{" "}
            <a
              href="https://github.com/Johin2"
              target="_blank"
              rel="noreferrer"
              className="underline decoration-neutral-700 underline-offset-2 hover:text-neutral-300 transition"
            >
              @Johin2
            </a>
            . Solo-maintained; contributions welcome.
          </div>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/Johin2/self-heal/issues"
              target="_blank"
              rel="noreferrer"
              className="hover:text-neutral-300 transition"
            >
              Issues
            </a>
            <a
              href="https://github.com/Johin2/self-heal/blob/main/CONTRIBUTING.md"
              target="_blank"
              rel="noreferrer"
              className="hover:text-neutral-300 transition"
            >
              Contributing
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Stat({
  label,
  naive,
  healed,
}: {
  label: string;
  naive: string;
  healed: string;
}) {
  return (
    <div className="rounded-xl border border-neutral-900 bg-neutral-950/50 p-5">
      <div className="text-xs uppercase tracking-wider text-neutral-500">
        {label}
      </div>
      <div className="mt-4 space-y-2 text-sm">
        <Row k="Naive" v={naive} />
        <Row k="self-heal" v={healed} accent />
      </div>
    </div>
  );
}

function ProvidersCard() {
  const providers = [
    "Claude",
    "OpenAI",
    "Gemini",
    "LiteLLM (100+)",
    "Ollama",
    "vLLM",
    "OpenRouter",
    "Groq",
  ];
  return (
    <div className="rounded-xl border border-neutral-900 bg-neutral-950/50 p-5">
      <div className="text-xs uppercase tracking-wider text-neutral-500">
        Providers out of the box
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {providers.map((p) => (
          <span
            key={p}
            className="rounded-md border border-neutral-800 bg-neutral-900/60 px-2 py-0.5 font-mono text-xs text-neutral-300"
          >
            {p}
          </span>
        ))}
      </div>
      <div className="mt-3 text-xs text-neutral-500">
        Or bring your own: implement one <span className="font-mono text-neutral-400">propose()</span> method.
      </div>
    </div>
  );
}

function Row({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-neutral-500">{k}</span>
      <span
        className={
          accent
            ? "font-mono font-medium text-emerald-300"
            : "font-mono text-neutral-300"
        }
      >
        {v}
      </span>
    </div>
  );
}

function Feature({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border border-neutral-900 bg-neutral-950/40 p-5">
      <div className="inline-flex items-center gap-2 text-neutral-300">
        <span className="text-emerald-400">{icon}</span>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-neutral-400">{body}</p>
    </div>
  );
}
