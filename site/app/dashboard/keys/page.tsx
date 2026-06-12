"use client";

import { useState, useEffect, useCallback } from "react";
import { Copy, Trash2, Plus } from "lucide-react";

type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
};

type RevealedKey = {
  id: string;
  key: string;
};

function fmt(iso: string): string {
  return new Date(iso).toLocaleString();
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={copy}
      className="ml-1 inline-flex items-center rounded p-0.5 text-neutral-500 hover:text-neutral-200 transition"
      title="Copy"
    >
      <Copy size={13} />
      {copied && <span className="ml-1 text-[10px] text-emerald-400">copied</span>}
    </button>
  );
}

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [revealed, setRevealed] = useState<RevealedKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch("/api/cp/keys", { credentials: "include" });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setKeys(data.keys ?? []);
    } catch {
      setError("Failed to load API keys.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const createKey = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/api/cp/keys", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setRevealed({ id: data.id, key: data.key });
      setNewName("");
      await fetchKeys();
    } catch {
      setError("Failed to create API key.");
    } finally {
      setCreating(false);
    }
  };

  const deleteKey = async (id: string) => {
    if (!confirm("Revoke this key? This cannot be undone.")) return;
    try {
      const res = await fetch(`/api/cp/keys/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setKeys((prev) => prev.filter((k) => k.id !== id));
      if (revealed?.id === id) setRevealed(null);
    } catch {
      setError("Failed to revoke key.");
    }
  };

  return (
    <div className="max-w-3xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Keys authenticate the{" "}
            <span className="font-mono text-neutral-300">ControlPlaneClient</span> in the OSS library.
          </p>
        </div>
      </div>

      {/* Create key */}
      <div className="mt-8 rounded-xl border border-neutral-900 bg-neutral-950/40 p-5">
        <h2 className="text-sm font-medium text-neutral-200">Create a new key</h2>
        <div className="mt-3 flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createKey()}
            placeholder="Key name (e.g. production)"
            className="flex-1 rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 focus:border-neutral-600 focus:outline-none"
          />
          <button
            onClick={createKey}
            disabled={creating || !newName.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-xs font-medium text-black hover:bg-neutral-200 transition disabled:opacity-40"
          >
            <Plus size={13} />
            {creating ? "Creating…" : "Create"}
          </button>
        </div>

        {/* One-time reveal */}
        {revealed && (
          <div className="mt-4 rounded-lg border border-emerald-900/60 bg-emerald-950/30 p-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-emerald-400">
                Copy this key now — it won&apos;t be shown again.
              </p>
              <button
                onClick={() => setRevealed(null)}
                className="text-xs text-neutral-500 hover:text-neutral-300"
              >
                dismiss
              </button>
            </div>
            <div className="mt-2 flex items-center gap-1 font-mono text-sm text-emerald-300">
              <span className="break-all">{revealed.key}</span>
              <CopyButton text={revealed.key} />
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="mt-3 text-xs text-red-400">{error}</p>
      )}

      {/* Key list */}
      <div className="mt-6">
        {loading ? (
          <div className="py-10 text-center text-sm text-neutral-600">Loading…</div>
        ) : keys.length === 0 ? (
          <div className="rounded-xl border border-neutral-900 bg-neutral-950/40 p-10 text-center">
            <div className="text-sm font-medium text-neutral-200">No keys yet</div>
            <p className="mt-2 text-xs text-neutral-500">
              Create your first key above to start sending events.
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-neutral-900 bg-neutral-950/40">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-neutral-900 bg-neutral-950/80 text-xs uppercase tracking-wider text-neutral-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Prefix</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Last used</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr
                    key={k.id}
                    className="border-b border-neutral-900 last:border-0 hover:bg-neutral-950 transition"
                  >
                    <td className="px-4 py-3 text-neutral-100">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                      {k.prefix}…
                      <CopyButton text={k.prefix} />
                    </td>
                    <td className="px-4 py-3 text-neutral-400 text-xs">{fmt(k.created_at)}</td>
                    <td className="px-4 py-3 text-neutral-500 text-xs">
                      {k.last_used_at ? fmt(k.last_used_at) : "Never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => deleteKey(k.id)}
                        className="inline-flex items-center gap-1 rounded p-1 text-neutral-600 hover:text-red-400 transition"
                        title="Revoke"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
