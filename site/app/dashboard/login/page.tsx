"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Mail } from "lucide-react";
import Link from "next/link";

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const errorParam = params.get("error");

  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">(
    errorParam ? "error" : "idle"
  );
  const [errorMsg, setErrorMsg] = useState(
    errorParam === "invalid"
      ? "That link is invalid or expired. Request a new one."
      : errorParam === "missing"
        ? "Missing token. Request a new sign-in link."
        : ""
  );

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setStatus("error");
      setErrorMsg("Please enter a valid email.");
      return;
    }
    setStatus("loading");
    setErrorMsg("");
    try {
      const res = await fetch("/api/auth/request-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.push(`/dashboard/login/sent?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-6 py-12">
      <div className="pointer-events-none absolute inset-0 dot-grid opacity-60" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[480px] hero-glow" />

      <div className="relative z-10 w-full max-w-md">
        <Link
          href="/"
          className="mb-10 flex items-center gap-2 font-mono text-sm tracking-tight text-neutral-100 hover:text-white transition"
        >
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span>self-heal</span>
        </Link>

        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Enter your email and we&apos;ll send you a one-time link. No password needed.
        </p>

        <AnimatePresence mode="wait">
          <motion.form
            key="form"
            onSubmit={onSubmit}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="mt-8 space-y-3"
          >
            <label className="block">
              <span className="sr-only">Email</span>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
                <input
                  type="email"
                  required
                  autoFocus
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-950 pl-9 pr-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-neutral-700 focus:outline-none focus:ring-1 focus:ring-neutral-700 transition"
                  disabled={status === "loading"}
                />
              </div>
            </label>
            <button
              type="submit"
              disabled={status === "loading"}
              className="group inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-white px-4 py-2.5 text-sm font-medium text-black hover:bg-neutral-200 disabled:opacity-60 disabled:cursor-not-allowed transition"
            >
              {status === "loading" ? (
                <span>Sending link…</span>
              ) : (
                <>
                  <span>Send sign-in link</span>
                  <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </button>
            {status === "error" && errorMsg ? (
              <p className="text-xs text-red-400">{errorMsg}</p>
            ) : null}
          </motion.form>
        </AnimatePresence>

        <p className="mt-10 text-xs text-neutral-500">
          The OSS library is free forever. This dashboard is part of the hosted
          control plane — audit log, policy, observability.
        </p>
      </div>
    </div>
  );
}
