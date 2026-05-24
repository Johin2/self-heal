import { neon } from "@neondatabase/serverless";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

// Load .env.local manually so this script works without dotenv.
try {
  const env = readFileSync(join(here, "..", ".env.local"), "utf-8");
  for (const line of env.split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$/i);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
} catch {}

const url = process.env.DATABASE_URL_UNPOOLED ?? process.env.DATABASE_URL;
if (!url) {
  console.error("DATABASE_URL not set");
  process.exit(1);
}

const sql = neon(url);

const files = readdirSync(here).filter((f) => f.endsWith(".sql")).sort();
for (const file of files) {
  console.log(`Applying ${file}...`);
  const text = readFileSync(join(here, file), "utf-8");
  // neon() tagged-template doesn't support multi-statement strings via
  // raw query. Split on `;` boundaries (naive but fine for our DDL).
  const statements = text
    .split(/;\s*$/m)
    .map((s) => s.trim())
    .filter(Boolean);
  for (const stmt of statements) {
    await sql(stmt);
  }
  console.log(`  ok`);
}
console.log("Migrations complete.");
