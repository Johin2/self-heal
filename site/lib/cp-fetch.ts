/**
 * Server-side fetch from the control plane that forwards the user's
 * session cookie. Returns parsed JSON, or null if the upstream returned
 * a 4xx (the caller can render an empty / unauthorized state).
 */

import { cookies } from "next/headers";

export async function cpFetch<T>(path: string): Promise<T | null> {
  const base = process.env.CONTROL_PLANE_URL;
  if (!base) return null;
  const jar = await cookies();
  const session = jar.get("cp_session");
  if (!session) return null;

  const res = await fetch(base.replace(/\/$/, "") + path, {
    headers: { cookie: `cp_session=${session.value}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as T;
}
