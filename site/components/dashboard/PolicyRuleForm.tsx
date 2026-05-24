"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

type Condition = { field: string; op: string; value: string };

const FIELDS = [
  "type",
  "function_name",
  "module_name",
  "error_message",
  "attempt_number",
];
const OPS = ["eq", "ne", "contains", "regex", "gte", "lte"];
const ACTIONS = ["notify", "block", "allow"] as const;

export function PolicyRuleForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [priority, setPriority] = useState(100);
  const [action, setAction] = useState<(typeof ACTIONS)[number]>("notify");
  const [conditions, setConditions] = useState<Condition[]>([
    { field: "type", op: "eq", value: "" },
  ]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function setCond(i: number, patch: Partial<Condition>) {
    setConditions((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const body = {
        name: name.trim(),
        enabled: true,
        priority,
        action,
        conditions: conditions
          .filter((c) => c.value !== "")
          .map((c) => ({
            field: c.field,
            op: c.op,
            value: c.field === "attempt_number" ? Number(c.value) : c.value,
          })),
      };
      const res = await fetch("/api/cp/policy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json())?.detail || `${res.status}`);
      setName("");
      setConditions([{ field: "type", op: "eq", value: "" }]);
      router.refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-3 space-y-4 rounded-xl border border-neutral-900 bg-neutral-950/40 p-4"
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <input
          required
          placeholder="Rule name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm focus:border-neutral-700 focus:outline-none focus:ring-1 focus:ring-neutral-700 transition"
        />
        <select
          value={action}
          onChange={(e) => setAction(e.target.value as (typeof ACTIONS)[number])}
          className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm focus:border-neutral-700 focus:outline-none focus:ring-1 focus:ring-neutral-700 transition"
        >
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              Action: {a}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          max={1000}
          value={priority}
          onChange={(e) => setPriority(Number(e.target.value))}
          className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm focus:border-neutral-700 focus:outline-none focus:ring-1 focus:ring-neutral-700 transition"
          placeholder="Priority"
        />
      </div>

      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wider text-neutral-500">
          Conditions (all must match)
        </div>
        {conditions.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <select
              value={c.field}
              onChange={(e) => setCond(i, { field: e.target.value })}
              className="w-40 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm"
            >
              {FIELDS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <select
              value={c.op}
              onChange={(e) => setCond(i, { op: e.target.value })}
              className="w-28 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm"
            >
              {OPS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
            <input
              value={c.value}
              onChange={(e) => setCond(i, { value: e.target.value })}
              placeholder="value"
              className="flex-1 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm focus:border-neutral-700 focus:outline-none focus:ring-1 focus:ring-neutral-700 transition"
            />
            <button
              type="button"
              onClick={() => setConditions((cs) => cs.filter((_, idx) => idx !== i))}
              className="rounded-md p-1.5 text-neutral-500 hover:text-red-300"
              aria-label="Remove condition"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setConditions((cs) => [...cs, { field: "type", op: "eq", value: "" }])
          }
          className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-200"
        >
          <Plus className="h-3 w-3" /> Add condition
        </button>
      </div>

      {err ? <p className="text-xs text-red-400">{err}</p> : null}

      <div className="flex items-center justify-end gap-2">
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="rounded-md bg-white px-3.5 py-1.5 text-sm font-medium text-black hover:bg-neutral-200 disabled:opacity-60 transition"
        >
          {busy ? "Saving…" : "Save rule"}
        </button>
      </div>
    </form>
  );
}
