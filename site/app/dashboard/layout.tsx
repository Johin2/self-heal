import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Activity, FileCode2, GitBranch, KeyRound, LayoutDashboard, ShieldCheck } from "lucide-react";

import { SignOutButton } from "@/components/dashboard/SignOutButton";

const SESSION_COOKIE = "cp_session";

async function fetchMe(cookieHeader: string): Promise<{ id: string; email: string } | null> {
  const base = process.env.CONTROL_PLANE_URL;
  if (!base) return null;
  try {
    const res = await fetch(base.replace(/\/$/, "") + "/v1/auth/me", {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as { id: string; email: string };
  } catch {
    return null;
  }
}

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const jar = await cookies();
  const session = jar.get(SESSION_COOKIE);
  if (!session) redirect("/dashboard/login");

  const me = await fetchMe(`${SESSION_COOKIE}=${session.value}`);
  if (!me) redirect("/dashboard/login");

  return (
    <div className="relative flex min-h-screen bg-black text-neutral-100">
      <aside className="hidden md:flex w-60 flex-col border-r border-neutral-900 bg-neutral-950/60 px-3 py-6">
        <Link
          href="/"
          className="mb-8 flex items-center gap-2 px-2 font-mono text-sm tracking-tight hover:text-white transition"
        >
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span>self-heal</span>
        </Link>

        <nav className="flex flex-col gap-0.5 text-sm">
          <NavLink href="/dashboard" icon={<LayoutDashboard className="h-4 w-4" />}>
            Overview
          </NavLink>
          <NavLink href="/dashboard/runs" icon={<GitBranch className="h-4 w-4" />}>
            Runs
          </NavLink>
          <NavLink href="/dashboard/metrics" icon={<Activity className="h-4 w-4" />}>
            Metrics
          </NavLink>
          <NavLink href="/dashboard/policy" icon={<ShieldCheck className="h-4 w-4" />}>
            Policy
          </NavLink>
          <NavLink href="/dashboard/keys" icon={<KeyRound className="h-4 w-4" />}>
            API keys
          </NavLink>
          <NavLink href="/dashboard/docs" icon={<FileCode2 className="h-4 w-4" />}>
            Docs
          </NavLink>
        </nav>

        <div className="mt-auto border-t border-neutral-900 pt-4">
          <div className="px-2 text-xs text-neutral-500">Signed in</div>
          <div className="px-2 truncate text-sm text-neutral-200" title={me.email}>
            {me.email}
          </div>
          <SignOutButton />
        </div>
      </aside>

      <main className="flex-1 px-6 py-8 md:px-10 md:py-10">{children}</main>
    </div>
  );
}

function NavLink({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100 transition"
    >
      {icon}
      <span>{children}</span>
    </Link>
  );
}
