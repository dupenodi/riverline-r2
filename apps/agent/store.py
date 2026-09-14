"""Durable storage for sessions, transcripts, and money transactions.

SQLite on local disk. Writes are fire-and-forget from the call path so
persistence never adds latency to a live conversation.
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
    ended_at    TEXT,
    duration_seconds INTEGER,
    ended_reason TEXT,
    name        TEXT,
    cash        INTEGER,
    advice      TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    direction   TEXT NOT NULL,
    kind        TEXT,
    label       TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    amount_min  INTEGER,
    amount_max  INTEGER,
    day         INTEGER,
    day_min     INTEGER,
    day_max     INTEGER,
    cadence     TEXT,
    status      TEXT,
    min_due     INTEGER,
    on_date     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_turns (
    session_id   TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    role         TEXT NOT NULL,
    text         TEXT NOT NULL,
    interrupted  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);

CREATE INDEX IF NOT EXISTS tx_by_session
    ON transactions (session_id, created_at);

CREATE INDEX IF NOT EXISTS sessions_by_user
    ON sessions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS transcript_by_session
    ON transcript_turns (session_id, seq);
"""

# Columns added after the first schema — applied on connect if missing.
_SESSION_COLUMNS = {
    "duration_seconds": "INTEGER",
    "ended_reason": "TEXT",
    "name": "TEXT",
    "cash": "INTEGER",
    "advice": "TEXT",
}

_TRANSACTION_COLUMNS = {
    "day": "INTEGER",
    "kind": "TEXT",
    "amount_min": "INTEGER",
    "amount_max": "INTEGER",
    "day_min": "INTEGER",
    "day_max": "INTEGER",
    "cadence": "TEXT",
    "status": "TEXT",
    "min_due": "INTEGER",
    "on_date": "TEXT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_seconds(created_at: str | None, ended_at: str | None) -> int | None:
    if not created_at or not ended_at:
        return None
    try:
        start = datetime.fromisoformat(created_at)
        end = datetime.fromisoformat(ended_at)
    except ValueError:
        return None
    return max(0, int((end - start).total_seconds()))


class Store:
    """One SQLite connection, locked, used off the event loop."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(SCHEMA)
        self._migrate(conn)
        conn.commit()
        self._conn = conn
        logger.info("store ready path={}", self.path)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        for name, sql_type in _SESSION_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}")

        tx_existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        for name, sql_type in _TRANSACTION_COLUMNS.items():
            if name not in tx_existing:
                conn.execute(
                    f"ALTER TABLE transactions ADD COLUMN {name} {sql_type}"
                )

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

    # --- sessions -----------------------------------------------------------

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
        if ended:
            self._fill_duration(session_id)

    def set_session_name(self, *, session_id: str, name: str) -> None:
        self._execute(
            "UPDATE sessions SET name = ? WHERE session_id = ?",
            (name, session_id),
        )

    def set_session_cash(self, *, session_id: str, cash: int) -> None:
        self._execute(
            "UPDATE sessions SET cash = ? WHERE session_id = ?",
            (cash, session_id),
        )

    def set_session_advice(self, *, session_id: str, advice: dict[str, Any]) -> None:
        self._execute(
            "UPDATE sessions SET advice = ? WHERE session_id = ?",
            (json.dumps(advice), session_id),
        )

    def end_session(
        self,
        *,
        session_id: str,
        status: str = "ended",
        ended_reason: str | None = None,
    ) -> None:
        ended = _now()
        self._execute(
            """
            UPDATE sessions
               SET status = ?,
                   ended_at = COALESCE(ended_at, ?),
                   ended_reason = COALESCE(?, ended_reason)
             WHERE session_id = ?
            """,
            (status, ended, ended_reason, session_id),
        )
        self._fill_duration(session_id)

    def _fill_duration(self, session_id: str) -> None:
        rows = self._query(
            "SELECT created_at, ended_at, duration_seconds FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            return
        row = rows[0]
        if row["duration_seconds"] is not None:
            return
        seconds = _duration_seconds(row["created_at"], row["ended_at"])
        if seconds is None:
            return
        self._execute(
            "UPDATE sessions SET duration_seconds = ? WHERE session_id = ?",
            (seconds, session_id),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            return None
        item = dict(rows[0])
        raw = item.get("advice")
        if isinstance(raw, str) and raw.strip():
            try:
                item["advice"] = json.loads(raw)
            except json.JSONDecodeError:
                item["advice"] = None
        else:
            item["advice"] = None
        return item

    def list_sessions(
        self,
        *,
        limit: int = 50,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        if user_id:
            rows = self._query(
                """
                SELECT * FROM sessions
                 WHERE user_id = ?
                 ORDER BY created_at DESC
                 LIMIT ?
                """,
                (user_id, limit),
            )
        else:
            rows = self._query(
                """
                SELECT * FROM sessions
                 ORDER BY created_at DESC
                 LIMIT ?
                """,
                (limit,),
            )
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            txs = self.list_transactions(row["session_id"])
            item["tx_count"] = len(txs)
            out.append(item)
        return out

    # --- transactions -------------------------------------------------------

    def add_transaction(self, *, session_id: str, item: dict[str, Any]) -> None:
        kind = item.get("kind")
        direction = item.get("direction")
        if kind not in ("income", "need", "debt", "flex", "owed"):
            kind = "income" if direction == "incoming" else "need"
        direction = "incoming" if kind in ("income", "owed") else "outgoing"
        self._execute(
            """
            INSERT INTO transactions
                (id, session_id, direction, kind, label, amount, amount_min,
                 amount_max, day, day_min, day_max, cadence, status, min_due,
                 on_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                direction = excluded.direction,
                kind = excluded.kind,
                label = excluded.label,
                amount = excluded.amount,
                amount_min = excluded.amount_min,
                amount_max = excluded.amount_max,
                day = excluded.day,
                day_min = excluded.day_min,
                day_max = excluded.day_max,
                cadence = excluded.cadence,
                status = excluded.status,
                min_due = excluded.min_due,
                on_date = excluded.on_date
            """,
            (
                item["id"],
                session_id,
                direction,
                kind,
                item["label"],
                int(item.get("amount") or 0),
                item.get("amount_min"),
                item.get("amount_max"),
                item.get("day"),
                item.get("day_min"),
                item.get("day_max"),
                item.get("cadence") or "monthly",
                item.get("status") or "unknown",
                item.get("min_due"),
                item.get("on_date"),
                _now(),
            ),
        )

    def remove_transaction(self, *, session_id: str, item_id: str) -> None:
        self._execute(
            "DELETE FROM transactions WHERE session_id = ? AND id = ?",
            (session_id, item_id),
        )

    def list_transactions(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._query(
            """
            SELECT id, direction, kind, label, amount, amount_min, amount_max,
                   day, day_min, day_max, cadence, status, min_due, on_date,
                   created_at
              FROM transactions
             WHERE session_id = ?
             ORDER BY created_at
            """,
            (session_id,),
        )
        return [
            {
                "id": row["id"],
                "direction": row["direction"],
                "kind": row["kind"],
                "label": row["label"],
                "amount": row["amount"],
                "amount_min": row["amount_min"],
                "amount_max": row["amount_max"],
                "day": row["day"],
                "day_min": row["day_min"],
                "day_max": row["day_max"],
                "cadence": row["cadence"],
                "status": row["status"],
                "min_due": row["min_due"],
                "on_date": row["on_date"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # --- transcript ---------------------------------------------------------

    def append_turn(
        self,
        *,
        session_id: str,
        seq: int,
        role: str,
        text: str,
        interrupted: bool = False,
    ) -> None:
        text = text.strip()
        if not text:
            return
        self._execute(
            """
            INSERT OR IGNORE INTO transcript_turns
                (session_id, seq, role, text, interrupted, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, seq, role, text, 1 if interrupted else 0, _now()),
        )

    def list_transcript(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._query(
            """
            SELECT seq, role, text, interrupted, created_at
              FROM transcript_turns
             WHERE session_id = ?
             ORDER BY seq
            """,
            (session_id,),
        )
        return [
            {
                "seq": row["seq"],
                "role": row["role"],
                "text": row["text"],
                "interrupted": bool(row["interrupted"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def session_history(self, session_id: str) -> dict[str, Any] | None:
        meta = self.get_session(session_id)
        if meta is None:
            return None
        return {
            "session": meta,
            "transcript": self.list_transcript(session_id),
            "transactions": self.list_transactions(session_id),
        }


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "kubera.db"
store = Store(DEFAULT_PATH)


def configure(path: str | None) -> None:
    if path:
        store.path = Path(path).expanduser().resolve()


async def init() -> None:
    await asyncio.to_thread(store.connect)


async def shutdown() -> None:
    await asyncio.to_thread(store.close)


async def record_session(**kwargs: Any) -> None:
    await _safely(store.record_session, **kwargs)


async def set_session_status(**kwargs: Any) -> None:
    await _safely(store.set_session_status, **kwargs)


async def set_session_name(**kwargs: Any) -> None:
    await _safely(store.set_session_name, **kwargs)


async def set_session_cash(**kwargs: Any) -> None:
    await _safely(store.set_session_cash, **kwargs)


async def set_session_advice(**kwargs: Any) -> None:
    await _safely(store.set_session_advice, **kwargs)


async def end_session(**kwargs: Any) -> None:
    await _safely(store.end_session, **kwargs)


async def add_transaction(**kwargs: Any) -> None:
    await _safely(store.add_transaction, **kwargs)


async def remove_transaction(**kwargs: Any) -> None:
    await _safely(store.remove_transaction, **kwargs)


async def append_turn(**kwargs: Any) -> None:
    await _safely(store.append_turn, **kwargs)


async def list_transactions(session_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(store.list_transactions, session_id)


async def get_session(session_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(store.get_session, session_id)


async def list_sessions(
    *, limit: int = 50, user_id: str | None = None
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(store.list_sessions, limit=limit, user_id=user_id)


async def list_transcript(session_id: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(store.list_transcript, session_id)


async def session_history(session_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(store.session_history, session_id)


async def _safely(fn: Any, **kwargs: Any) -> None:
    try:
        await asyncio.to_thread(lambda: fn(**kwargs))
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        logger.warning(
            "store write failed fn={} err={}", getattr(fn, "__name__", fn), exc
        )
