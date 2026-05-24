"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ShieldAlert, ShieldCheck, ShieldOff, Trash2 } from "lucide-react";

import type { PolicyRule } from "@/app/dashboard/policy/page";

const ACTION_ICON = {
  allow: <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />,
  block: <ShieldOff className="h-3.5 w-3.5 text-red-400" />,
  notify: <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />,
};

export function PolicyRulesList({ rules }: { rules: PolicyRule[] }) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);

  async function remove(id: string) {
    if (!confirm("Delete this rule?")) return;
    setPending(id);
    try {
      await fetch(`/api/cp/policy/${id}`, { method: "DELETE" });
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  if (rules.length === 0) {
    return (
      <div className="mt-3 rounded-xl border border-neutral-900 bg-neutral-950/40 p-6 text-center text-sm text-neutral-500">
        No rules yet. Default behaviour is <span className="font-mono">allow</span>.
      </div>
    );
  }

  return (
    <ul className="mt-3 divide-y divide-neutral-900 rounded-xl border border-neutral-900 bg-neutral-950/40">
      {rules.map((r) => (
        <li key={r.id} className="flex items-start gap-3 px-4 py-3">
          <div className="mt-0.5">{ACTION_ICON[r.action]}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-neutral-100">{r.name}</span>
              <span className="rounded-full border border-neutral-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-neutral-500">
                priority {r.priority}
              </span>
              <span className="text-xs uppercase tracking-wider text-neutral-500">
                → {r.action}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {r.conditions.length === 0 ? (
                <span className="text-xs text-neutral-500 italic">catch-all</span>
              ) : (
                r.conditions.map((c, i) => (
                  <code
                    key={i}
                    className="rounded bg-neutral-900 px-1.5 py-0.5 text-[11px] text-neutral-300"
                  >
                    {c.field} {c.op} {String(c.value)}
                  </code>
                ))
              )}
            </div>
          </div>
          <button
            onClick={() => remove(r.id)}
            disabled={pending === r.id}
            className="rounded-md p-1.5 text-neutral-500 hover:text-red-300 disabled:opacity-50 transition"
            aria-label="Delete rule"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </li>
      ))}
    </ul>
  );
}
