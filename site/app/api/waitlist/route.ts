import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

/**
 * Simple waitlist endpoint.
 *
 * For now, appends to a JSONL file under `.waitlist/emails.jsonl`.
 * Swap this for a real backend (Resend + Postgres, Convex, Supabase,
 * Formspree) before heavy traffic. Configure via WAITLIST_BACKEND env
 * var once you pick one.
 */

const WAITLIST_FILE = path.join(process.cwd(), ".waitlist", "emails.jsonl");

function isValidEmail(e: unknown): e is string {
  return (
    typeof e === "string" &&
    e.length < 320 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)
  );
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const email = (body as { email?: unknown })?.email;
  if (!isValidEmail(email)) {
    return NextResponse.json({ error: "Invalid email" }, { status: 400 });
  }

  const record = JSON.stringify({
    email,
    ts: new Date().toISOString(),
    ip: request.headers.get("x-forwarded-for") ?? null,
    ua: request.headers.get("user-agent") ?? null,
  });

  // Always emit a greppable structured log line. On Vercel this is
  // visible under Logs in the project dashboard and is the only
  // durable capture path until we swap to a real backend.
  console.log(`WAITLIST_SIGNUP ${record}`);

  try {
    await fs.mkdir(path.dirname(WAITLIST_FILE), { recursive: true });
    await fs.appendFile(WAITLIST_FILE, record + "\n", "utf-8");
  } catch {
    // Serverless platforms have a read-only filesystem; the structured
    // log above is the durable record in that case.
  }

  return NextResponse.json({ ok: true });
}
