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


def _session(db: Store, session_id: str, user_id: str = "u1") -> None:
    db.record_session(
        session_id=session_id,
        user_id=user_id,
        room_name="room",
        room_url="https://example.daily.co/room",
        status="ready",
    )


def test_add_and_list_transactions(db: Store) -> None:
    _session(db, "s1")
    db.add_transaction(
        session_id="s1",
        item={
            "id": "a1",
            "direction": "incoming",
            "label": "Salary",
            "amount": 50000,
            "day": 1,
        },
    )
    db.add_transaction(
        session_id="s1",
        item={
            "id": "a2",
            "direction": "outgoing",
            "label": "Rent",
            "amount": 20000,
            "day": 5,
        },
    )

    txs = db.list_transactions("s1")
    assert [t["label"] for t in txs] == ["Salary", "Rent"]
    assert txs[0]["direction"] == "incoming"
    assert txs[0]["day"] == 1
    assert txs[1]["amount"] == 20000


def test_remove_transaction(db: Store) -> None:
    _session(db, "s1")
    db.add_transaction(
        session_id="s1",
        item={
            "id": "a1",
            "direction": "outgoing",
            "label": "EMI",
            "amount": 8000,
            "day": 10,
        },
    )
    db.remove_transaction(session_id="s1", item_id="a1")
    assert db.list_transactions("s1") == []


def test_sessions_do_not_see_each_other_transactions(db: Store) -> None:
    _session(db, "s1")
    _session(db, "s2")
    db.add_transaction(
        session_id="s1",
        item={
            "id": "a1",
            "direction": "incoming",
            "label": "Pay",
            "amount": 1,
            "day": 1,
        },
    )
    assert db.list_transactions("s2") == []
    assert len(db.list_transactions("s1")) == 1


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


def test_a_failed_write_does_not_raise_into_the_call() -> None:
    """Persistence is best-effort: the conversation outranks the disk."""
    store = Store(Path("/definitely/not/a/writable/path/kubera.db"))

    async def run() -> None:
        await asyncio.sleep(0)
        store.add_transaction(
            session_id="s1",
            item={
                "id": "a1",
                "direction": "incoming",
                "label": "X",
                "amount": 1,
                "day": 1,
            },
        )
        assert store.list_transactions("s1") == []

    asyncio.run(run())


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
    db.set_session_name(session_id="new", name="Priya")
    db.add_transaction(
        session_id="new",
        item={
            "id": "t1",
            "direction": "outgoing",
            "label": "Bill",
            "amount": 500,
            "day": 12,
        },
    )

    listed = db.list_sessions(limit=10)
    assert [row["session_id"] for row in listed] == ["new", "old"]
    assert listed[0]["name"] == "Priya"
    assert listed[0]["tx_count"] == 1
    assert listed[1]["name"] is None
    assert listed[1]["tx_count"] == 0


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
    db.set_session_name(session_id="s1", name="Priya")
    db.append_turn(session_id="s1", seq=1, role="user", text="Hi")
    db.add_transaction(
        session_id="s1",
        item={
            "id": "t1",
            "direction": "incoming",
            "label": "Salary",
            "amount": 40000,
            "day": 1,
        },
    )

    history = db.session_history("s1")
    assert history is not None
    assert history["session"]["session_id"] == "s1"
    assert history["session"]["name"] == "Priya"
    assert history["transcript"][0]["text"] == "Hi"
    assert history["transactions"][0]["label"] == "Salary"
    assert history["transactions"][0]["day"] == 1
