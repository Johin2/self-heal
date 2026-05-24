"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function SignOutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.push("/dashboard/login");
      router.refresh();
    }
  }

  return (
    <button
      onClick={signOut}
      disabled={busy}
      className="mt-3 inline-flex items-center gap-2 px-2 text-xs text-neutral-500 hover:text-neutral-300 transition disabled:opacity-60"
    >
      <LogOut className="h-3.5 w-3.5" />
      <span>{busy ? "Signing out…" : "Sign out"}</span>
    </button>
  );
}
