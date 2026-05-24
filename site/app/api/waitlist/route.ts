import { NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";

const databaseUrl = process.env.DATABASE_URL;
const sql = databaseUrl ? neon(databaseUrl) : null;

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

  const ip = request.headers.get("x-forwarded-for") ?? null;
  const ua = request.headers.get("user-agent") ?? null;

  // Always emit a structured log line first so Vercel logs hold a recovery
  // trail even if the DB write fails.
  console.log(
    `WAITLIST_SIGNUP ${JSON.stringify({
      email,
      ts: new Date().toISOString(),
      ip,
      ua,
    })}`,
  );

  if (!sql) {
    console.error("WAITLIST_DB_ERROR DATABASE_URL is not configured");
    return NextResponse.json(
      { error: "Waitlist is not configured. Please try again later." },
      { status: 500 },
    );
  }

  try {
    await sql`
      INSERT INTO waitlist_signups (email, ip, user_agent)
      VALUES (${email}, ${ip}, ${ua})
      ON CONFLICT (email) DO NOTHING
    `;
  } catch (err) {
    console.error("WAITLIST_DB_ERROR", err);
    return NextResponse.json(
      { error: "Could not record signup, please try again." },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}
