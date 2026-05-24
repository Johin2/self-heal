# self-heal landing site

Next.js 16 + Tailwind 4 + framer-motion. Single page with waitlist capture.

## Dev

```bash
cd site
npm install
npm run dev       # http://localhost:3000
npm run build     # type-check + prod build
```

## Waitlist backend

`app/api/waitlist/route.ts` writes signups to a Neon Postgres database (table `waitlist_signups`). Every request also emits a structured `WAITLIST_SIGNUP {...}` line in the Vercel logs as a secondary trail.

### Setup

1. Create a project at [neon.tech](https://console.neon.tech/) and grab the **pooled** connection string.
2. Copy `.env.example` to `.env.local` and paste the URL into `DATABASE_URL`.
3. Run the migration in `db/001_waitlist.sql` — paste it into the Neon SQL editor, or:
   ```bash
   psql "$DATABASE_URL" -f db/001_waitlist.sql
   ```
4. For production, add `DATABASE_URL` as an env var in the Vercel project settings.

### Inspecting signups

```sql
SELECT email, ts FROM waitlist_signups ORDER BY ts DESC LIMIT 100;
```

## Deploy

```bash
# First time
vercel
# Subsequent
vercel --prod
```

Or connect the repo in the Vercel dashboard with `site/` as the root directory.
