/**
 * Server-side helper for proxying the dashboard's API routes to the
 * control plane backend. Keeps the backend URL and cookie domain on the
 * frontend's origin so a session cookie set by the backend ends up on
 * the dashboard's domain.
 */

import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "cp_session";

function baseUrl(): string {
  const url = process.env.CONTROL_PLANE_URL;
  if (!url) throw new Error("CONTROL_PLANE_URL is not set");
  return url.replace(/\/$/, "");
}

export async function proxy(
  request: NextRequest,
  path: string,
  init?: { method?: string; body?: BodyInit | null }
): Promise<NextResponse> {
  const method = init?.method ?? request.method;
  const upstreamHeaders: Record<string, string> = {};

  const contentType = request.headers.get("content-type");
  if (contentType) upstreamHeaders["content-type"] = contentType;

  const session = request.cookies.get(SESSION_COOKIE);
  if (session) {
    upstreamHeaders["cookie"] = `${SESSION_COOKIE}=${session.value}`;
  }

  const upstream = await fetch(baseUrl() + path, {
    method,
    headers: upstreamHeaders,
    body: init?.body ?? (method === "GET" || method === "HEAD" ? undefined : await request.text()),
    cache: "no-store",
  });

  const text = await upstream.text();
  const res = new NextResponse(text, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
    },
  });

  // Forward Set-Cookie verbatim. The cookie's Domain attribute is unset
  // (the backend uses the default host), so the browser scopes it to the
  // dashboard's origin — exactly what we want.
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    res.headers.set("set-cookie", setCookie);
  }

  return res;
}
