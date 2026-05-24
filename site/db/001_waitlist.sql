CREATE TABLE IF NOT EXISTS waitlist_signups (
  id          BIGSERIAL PRIMARY KEY,
  email       TEXT NOT NULL,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  ip          TEXT,
  user_agent  TEXT,
  UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS waitlist_signups_ts_idx
  ON waitlist_signups (ts DESC);
