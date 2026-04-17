"""SQLite-backed repair cache.

Skips the LLM when the same function + failure has already been repaired.
Lookups are by (source_hash, failure_signature). Opt-in via
`RepairLoop(cache=RepairCache(path))` or `@repair(cache_path=...)`.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from self_heal.types import Failure

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repairs (
    source_hash        TEXT NOT NULL,
    failure_signature  TEXT NOT NULL,
    proposed_source    TEXT NOT NULL,
    succeeded          INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    hit_count          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source_hash, failure_signature)
);
CREATE INDEX IF NOT EXISTS idx_repairs_source ON repairs(source_hash);
"""


class RepairCache:
    """Persistent repair cache keyed on (source, failure) signature.

    Thread-safe for typical decorator usage. Concurrent processes should
    each open their own connection (SQLite handles it).
    """

    def __init__(self, path: str | Path = ".self_heal_cache.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- public API ------------------------------------------------------

    def lookup(self, source: str, failure: Failure) -> str | None:
        """Return a previously-successful repair, or None."""
        sh = self._source_hash(source)
        sig = self._failure_signature(failure)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT proposed_source FROM repairs
                WHERE source_hash = ? AND failure_signature = ? AND succeeded = 1
                """,
                (sh, sig),
            ).fetchone()
            if row:
                self._conn.execute(
                    """UPDATE repairs SET hit_count = hit_count + 1
                       WHERE source_hash = ? AND failure_signature = ?""",
                    (sh, sig),
                )
                self._conn.commit()
                return row[0]
        return None

    def record(
        self,
        source: str,
        failure: Failure,
        proposed_source: str,
        succeeded: bool,
    ) -> None:
        """Store a repair attempt (success or failure)."""
        sh = self._source_hash(source)
        sig = self._failure_signature(failure)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO repairs
                    (source_hash, failure_signature, proposed_source,
                     succeeded, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_hash, failure_signature) DO UPDATE SET
                    proposed_source = excluded.proposed_source,
                    succeeded = excluded.succeeded,
                    created_at = excluded.created_at
                """,
                (
                    sh,
                    sig,
                    proposed_source,
                    1 if succeeded else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def stats(self) -> dict[str, Any]:
        """Return simple cache statistics."""
        with self._lock:
            total, successes, hits = self._conn.execute(
                """SELECT COUNT(*), SUM(succeeded), SUM(hit_count) FROM repairs"""
            ).fetchone()
        return {
            "entries": total or 0,
            "successful_entries": successes or 0,
            "total_hits": hits or 0,
            "path": str(self.path),
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- signatures ------------------------------------------------------

    @staticmethod
    def _source_hash(source: str) -> str:
        # Normalize trivial whitespace so cosmetic edits still hit the cache.
        normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _failure_signature(failure: Failure) -> str:
        # Strip addresses / ids from the message to improve cache hit rate.
        import re

        msg = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", failure.message)
        msg = re.sub(r"at 0x[0-9a-fA-F]+", "at 0xADDR", msg)
        return f"{failure.kind}|{failure.error_type}|{msg[:300]}"
