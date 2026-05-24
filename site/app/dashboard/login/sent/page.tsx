import Link from "next/link";
import { Mail } from "lucide-react";

export default async function SentPage({
  searchParams,
}: {
  searchParams: Promise<{ email?: string }>;
}) {
  const { email } = await searchParams;
  return (
    <div className="relative flex min-h-screen items-center justify-center px-6 py-12">
      <div className="pointer-events-none absolute inset-0 dot-grid opacity-60" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[480px] hero-glow" />

      <div className="relative z-10 w-full max-w-md text-center">
        <Link
          href="/"
          className="mb-10 flex items-center justify-center gap-2 font-mono text-sm tracking-tight text-neutral-100 hover:text-white transition"
        >
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span>self-heal</span>
        </Link>

        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/5">
          <Mail className="h-5 w-5 text-emerald-400" />
        </div>

        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Check your email</h1>
        <p className="mt-2 text-sm text-neutral-400">
          {email ? (
            <>
              We sent a sign-in link to{" "}
              <span className="font-mono text-neutral-200">{email}</span>.
            </>
          ) : (
            <>We sent you a sign-in link.</>
          )}{" "}
          It expires in 15 minutes.
        </p>

        <Link
          href="/dashboard/login"
          className="mt-8 inline-block text-xs text-neutral-500 hover:text-neutral-300 transition"
        >
          Wrong email? Try again →
        </Link>
      </div>
    </div>
  );
}
