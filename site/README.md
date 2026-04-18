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

`app/api/waitlist/route.ts` currently appends emails to `.waitlist/emails.jsonl` on the local filesystem. On Vercel this will fail silently (read-only FS) and log to console.

Swap for a real backend before launch. Easiest options:

1. **Formspree** (free 50/mo): replace the fetch call with the Formspree endpoint.
2. **Resend + Postgres**: install `resend`, add a Postgres DB, persist + send a welcome email.
3. **Convex / Supabase**: full backend-as-a-service with a free tier.

## Deploy

```bash
# First time
vercel
# Subsequent
vercel --prod
```

Or connect the repo in the Vercel dashboard with `site/` as the root directory.
