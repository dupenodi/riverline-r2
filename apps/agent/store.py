"""Durable storage for sessions and the financial state they produce.

SQLite, on local disk. The numbers a call produces are the point of the call,
and until now they lived only in the bot process — a restart, a crash or a
closed tab took them with it. Every snapshot version is written as it is
published, so the row the user was last looking at can always be read back.

Writes are fire-and-forget from the agent's point of view (see `save_snapshot`):
persistence must never add latency to, or fail, a live conversation.

Deliberately SQLite and not a service: one file, no container to wait on, and
`docker compose up` stays one command.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT,
    room_name   TEXT,
    room_url    TEXT,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    ended_at    TEXT
);

-- One row per published version, not one row per session. A snapshot is
-- immutable once written, so the whole conversation can be replayed, and a
-- late-arriving version can never overwrite a newer one.
CREATE TABLE IF NOT EXISTS snapshots (
    session_id  TEXT NOT NULL,
    version     INTEGER NOT NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, version)
);

CREATE INDEX IF NOT EXISTS snapshots_by_session
    ON snapshots (session_id, version DESC);

CREATE INDEX IF NOT EXISTS sessions_by_user
    ON sessions (user_id, created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """A single SQLite connection, guarded by a lock and used off the loop.

    One connection rather than a pool: the write volume is a handful of rows per
    call, and a pool would be machinery with nothing to do.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL so a read (the restore endpoint) never blocks behind a write from
        # a live call.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(SCHEMA)
        conn.commit()
        self._conn = conn
        logger.info("store ready path={}", self.path)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if self._conn is None:
            return
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        if self._conn is None:
            return []
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # --- writes -------------------------------------------------------------

    def record_session(
        self,
        *,
        session_id: str,
        user_id: str | None,
        room_name: str,
        room_url: str,
        status: str,
    ) -> None:
        self._execute(
            """
            INSERT INTO sessions
                (session_id, user_id, room_name, room_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET status = excluded.status
            """,
            (session_id, user_id, room_name, room_url, status, _now()),
        )

    def set_session_status(self, *, session_id: str, status: str) -> None:
        ended = _now() if status in ("ended", "error") else None
        self._execute(
            """
            UPDATE sessions
               SET status = ?,
                   ended_at = COALESCE(?, ended_at)
             WHERE session_id = ?
            """,
            (status, ended, session_id),
        )

    def save_snapshot(self, *, session_id: str, payload: dict[str, Any]) -> None:
        version = int(payload.get("version", 0))
        self._execute(
            """
            INSERT INTO snapshots (session_id, version, payload, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, version) DO UPDATE SET
                payload = excluded.payload,
                created_at = excluded.created_at
            """,
            (session_id, version, json.dumps(payload), _now()),
        )

    # --- reads --------------------------------------------------------------

    def latest_snapshot(self, session_id: str) -> dict[str, Any] | None:
        rows = self._query(
            """
            SELECT payload FROM snapshots
             WHERE session_id = ?
             ORDER BY version DESC
             LIMIT 1
            """,
            (session_id,),
        )
        if not rows:
            return None
        return json.loads(rows[0]["payload"])

    def latest_snapshot_for_user(self, user_id: str) -> dict[str, Any] | None:
        """The most recent snapshot from any of this user's past calls."""
        rows = self._query(
            """
            SELECT s.payload FROM snapshots s
              JOIN sessions x ON x.session_id = s.session_id
             WHERE x.user_id = ?
             ORDER BY x.created_at DESC, s.version DESC
             LIMIT 1
            """,
            (user_id,),
        )
        if not rows:
            return None
        return json.loads(rows[0]["payload"])


# Module-level singleton, created at import and connected by the app on startup.
DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "kubera.db"
store = Store(DEFAULT_PATH)


def configure(path: str | None) -> None:
    """Point the store at a different file. Call before `connect`."""
    if path:
        store.path = Path(path).expanduser().resolve()


# --- async wrappers ---------------------------------------------------------
#
# Every call goes through a thread so a disk write never stalls the event loop
# a live conversation is running on.


async def init() -> None:
    await asyncio.to_thread(store.connect)


async def shutdown() -> None:
    await asyncio.to_thread(store.close)


async def record_session(**kwargs: Any) -> None:
    await _safely(store.record_session, **kwargs)


async def set_session_status(**kwargs: Any) -> None:
    await _safely(store.set_session_status, **kwargs)


async def save_snapshot(**kwargs: Any) -> None:
    await _safely(store.save_snapshot, **kwargs)


async def latest_snapshot(session_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(store.latest_snapshot, session_id)


async def latest_snapshot_for_user(user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(store.latest_snapshot_for_user, user_id)


async def _safely(fn: Any, **kwargs: Any) -> None:
    """Run a write, logging rather than raising.

    A failed disk write is worth knowing about but is never worth dropping a
    call for — the conversation and the cards both work without it.
    """
    try:
        await asyncio.to_thread(lambda: fn(**kwargs))
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        logger.warning("store write failed fn={} err={}", getattr(fn, "__name__", fn), exc)
