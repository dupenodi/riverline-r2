"""The local store keeps what a call produced, and keeps it in order."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from store import Store


@pytest.fixture()
def db(tmp_path: Path) -> Store:
    store = Store(tmp_path / "kubera.db")
    store.connect()
    yield store
    store.close()


def snap(version: int, **extra) -> dict:
    return {"type": "finance_state", "version": version, "facts": [], **extra}


def test_latest_snapshot_is_the_highest_version(db: Store) -> None:
    db.save_snapshot(session_id="s1", payload=snap(1))
    db.save_snapshot(session_id="s1", payload=snap(2, name="Priya"))

    assert db.latest_snapshot("s1")["version"] == 2


def test_a_late_older_version_does_not_become_the_latest(db: Store) -> None:
    """Frames can arrive out of order; the newest version still wins."""
    db.save_snapshot(session_id="s1", payload=snap(5, name="Priya"))
    db.save_snapshot(session_id="s1", payload=snap(3))

    assert db.latest_snapshot("s1")["name"] == "Priya"


def test_every_version_is_kept(db: Store) -> None:
    for version in range(1, 6):
        db.save_snapshot(session_id="s1", payload=snap(version))

    rows = db._query(
        "SELECT version FROM snapshots WHERE session_id = ? ORDER BY version",
        ("s1",),
    )
    assert [row["version"] for row in rows] == [1, 2, 3, 4, 5]


def test_republishing_a_version_replaces_it(db: Store) -> None:
    db.save_snapshot(session_id="s1", payload=snap(1))
    db.save_snapshot(session_id="s1", payload=snap(1, name="Priya"))

    assert db.latest_snapshot("s1")["name"] == "Priya"


def test_sessions_do_not_see_each_other(db: Store) -> None:
    db.save_snapshot(session_id="s1", payload=snap(9))
    db.save_snapshot(session_id="s2", payload=snap(1))

    assert db.latest_snapshot("s2")["version"] == 1


def test_unknown_session_has_nothing(db: Store) -> None:
    assert db.latest_snapshot("nope") is None


def test_session_status_moves_and_records_the_end(db: Store) -> None:
    db.record_session(
        session_id="s1",
        user_id="u1",
        room_name="room",
        room_url="https://example.daily.co/room",
        status="starting",
    )
    db.set_session_status(session_id="s1", status="ended")

    row = db._query("SELECT status, ended_at FROM sessions WHERE session_id = ?", ("s1",))[0]
    assert row["status"] == "ended"
    assert row["ended_at"] is not None


def test_recording_a_session_twice_is_not_an_error(db: Store) -> None:
    for status in ("starting", "ready"):
        db.record_session(
            session_id="s1",
            user_id="u1",
            room_name="room",
            room_url="https://example.daily.co/room",
            status=status,
        )

    row = db._query("SELECT status FROM sessions WHERE session_id = ?", ("s1",))[0]
    assert row["status"] == "ready"


def test_a_user_gets_their_most_recent_call(db: Store) -> None:
    for session_id in ("old", "new"):
        db.record_session(
            session_id=session_id,
            user_id="u1",
            room_name="room",
            room_url="https://example.daily.co/room",
            status="ended",
        )
    db.save_snapshot(session_id="old", payload=snap(4, name="Old"))
    db.save_snapshot(session_id="new", payload=snap(2, name="New"))

    assert db.latest_snapshot_for_user("u1")["name"] == "New"


def test_a_failed_write_does_not_raise_into_the_call() -> None:
    """Persistence is best-effort: the conversation outranks the disk."""
    store = Store(Path("/definitely/not/a/writable/path/kubera.db"))

    async def run() -> None:
        # Never connected, so every write is a no-op rather than a crash.
        await asyncio.sleep(0)
        store.save_snapshot(session_id="s1", payload=snap(1))
        assert store.latest_snapshot("s1") is None

    asyncio.run(run())
