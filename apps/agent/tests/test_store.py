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


def _session(db: Store, session_id: str, user_id: str = "u1") -> None:
    db.record_session(
        session_id=session_id,
        user_id=user_id,
        room_name="room",
        room_url="https://example.daily.co/room",
        status="ready",
    )


def test_transcript_turns_are_ordered(db: Store) -> None:
    _session(db, "s1")
    db.append_turn(session_id="s1", seq=1, role="user", text="Hi")
    db.append_turn(session_id="s1", seq=2, role="agent", text="Hello")
    db.append_turn(session_id="s1", seq=3, role="user", text="Rent is 20k")

    turns = db.list_transcript("s1")
    assert [t["role"] for t in turns] == ["user", "agent", "user"]
    assert turns[2]["text"] == "Rent is 20k"


def test_duplicate_seq_is_ignored(db: Store) -> None:
    _session(db, "s1")
    db.append_turn(session_id="s1", seq=1, role="user", text="First")
    db.append_turn(session_id="s1", seq=1, role="user", text="Retry")

    turns = db.list_transcript("s1")
    assert len(turns) == 1
    assert turns[0]["text"] == "First"


def test_empty_turn_is_not_stored(db: Store) -> None:
    _session(db, "s1")
    db.append_turn(session_id="s1", seq=1, role="user", text="   ")
    assert db.list_transcript("s1") == []


def test_list_sessions_newest_first_with_name(db: Store) -> None:
    _session(db, "old")
    _session(db, "new")
    db.save_snapshot(session_id="new", payload=snap(1, name="Priya"))

    listed = db.list_sessions(limit=10)
    assert [row["session_id"] for row in listed] == ["new", "old"]
    assert listed[0]["name"] == "Priya"
    assert listed[1]["name"] is None


def test_list_sessions_filters_by_user(db: Store) -> None:
    _session(db, "mine", user_id="u1")
    _session(db, "theirs", user_id="u2")

    listed = db.list_sessions(user_id="u1")
    assert [row["session_id"] for row in listed] == ["mine"]


def test_end_session_fills_duration(db: Store) -> None:
    _session(db, "s1")
    db.end_session(session_id="s1", ended_reason="user")

    row = db.get_session("s1")
    assert row is not None
    assert row["status"] == "ended"
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "user"
    assert row["duration_seconds"] is not None


def test_session_history_bundles_everything(db: Store) -> None:
    _session(db, "s1")
    db.append_turn(session_id="s1", seq=1, role="user", text="Hi")
    db.save_snapshot(session_id="s1", payload=snap(1, name="Priya"))

    history = db.session_history("s1")
    assert history is not None
    assert history["session"]["session_id"] == "s1"
    assert history["transcript"][0]["text"] == "Hi"
    assert history["finance"]["name"] == "Priya"
