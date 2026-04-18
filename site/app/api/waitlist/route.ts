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

  try {
    await fs.mkdir(path.dirname(WAITLIST_FILE), { recursive: true });
    await fs.appendFile(WAITLIST_FILE, record + "\n", "utf-8");
  } catch (err) {
    // Production deployments on serverless platforms (Vercel) have a
    // read-only filesystem, so this will fail. The ok-path below still
    // returns 200 so the UI feels correct; logs capture the email.
    console.error("[waitlist] filesystem write failed", err);
    console.log("[waitlist]", record);
  }

  return NextResponse.json({ ok: true });
}
