"""record / forget write facts; engine numbers come back on the snapshot."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import pytest

from tools import MoneyTools

TODAY = date(2026, 9, 1)


class _Params:
    def __init__(self, arguments: dict[str, Any]) -> None:
        self.arguments = arguments
        self.result: Any = None

    async def result_callback(self, result: Any) -> None:
        self.result = result


@pytest.fixture()
def money() -> MoneyTools:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    tools = MoneyTools(on_change=on_change, today=TODAY)
    tools.published = published  # type: ignore[attr-defined]
    return tools


def test_record_cash_and_entries(money: MoneyTools) -> None:
    params = _Params(
        {
            "name": "Priya",
            "cash": 8000,
            "items": [
                {
                    "kind": "income",
                    "label": "Salary",
                    "amount": 50000,
                    "day": 10,
                },
                {
                    "kind": "need",
                    "label": "Rent",
                    "amount": 20000,
                    "day": 5,
                },
            ],
        }
    )
    asyncio.run(money._handle_record(params))

    assert money.user_name == "Priya"
    assert money.cash == 8000
    assert [e.label for e in money.entries] == ["Salary", "Rent"]
    snap = params.result
    assert snap["speak"]["cash"] == 8000
    assert "finish" in snap["speak"]
    assert "crunch_date" in snap["speak"]
    assert "derived" not in snap
    assert "items" not in snap
    assert "gap" not in snap["speak"]
    assert "issues" in snap["speak"]
    assert "plan" not in snap
    assert "gap" in money.snapshot()["plan"]
    assert "steps" not in money.snapshot()["plan"]
    assert snap["speak"]["upcoming"] == [
        {
            "id": money.entries[1].id,
            "label": "Rent",
            "amount": 20000,
            "kind": "need",
            "date": "2026-09-05",
        },
        {
            "id": money.entries[0].id,
            "label": "Salary",
            "amount": 50000,
            "kind": "income",
            "date": "2026-09-10",
        },
    ]
    assert snap["recorded"] == [money.entries[0].id, money.entries[1].id]
    published = money.published[-1]  # type: ignore[attr-defined]
    assert published["type"] == "finance"
    assert len(published["items"]) == 2
    assert published["items"][0]["direction"] == "incoming"
    assert published["items"][1]["direction"] == "outgoing"
    assert len(published["derived"]["days"]) == 30


def test_record_rejects_bad_kind(money: MoneyTools) -> None:
    params = _Params(
        {"items": [{"kind": "sideways", "label": "X", "amount": 10, "day": 1}]}
    )
    asyncio.run(money._handle_record(params))
    assert params.result["recorded"] == []
    assert "instruction" in params.result
    assert money.entries == []


def test_forget(money: MoneyTools) -> None:
    add = _Params(
        {
            "cash": 1000,
            "items": [
                {"kind": "debt", "label": "EMI", "amount": 8000, "day": 10}
            ],
        }
    )
    asyncio.run(money._handle_record(add))
    item_id = add.result["recorded"][0]
    remove = _Params({"ids": [item_id]})
    asyncio.run(money._handle_forget(remove))
    assert remove.result["removed"] == [item_id]
    assert money.entries == []
    assert remove.result["entries"] == []
    assert "derived" not in remove.result


def test_schemas_are_record_forget_recap(money: MoneyTools) -> None:
    assert [s.name for s in money.schemas()] == ["record", "forget", "recap"]


def test_restatement_overwrites(money: MoneyTools) -> None:
    first = _Params(
        {"items": [{"kind": "debt", "label": "Card", "amount": 20000, "day": 21}]}
    )
    asyncio.run(money._handle_record(first))
    second = _Params(
        {"items": [{"kind": "debt", "label": "card", "amount": 22000, "day": 21}]}
    )
    asyncio.run(money._handle_record(second))
    assert len(money.entries) == 1
    assert money.entries[0].amount == 22000
    assert money.entries[0].day == 21
    assert second.result["conflicts"] == []


def test_status_patch_keeps_amount_and_day(money: MoneyTools) -> None:
    first = _Params(
        {"items": [{"kind": "debt", "label": "Credit card", "amount": 20000, "day": 21}]}
    )
    asyncio.run(money._handle_record(first))
    item_id = first.result["recorded"][0]
    patch = _Params({"items": [{"id": item_id, "status": "due"}]})
    asyncio.run(money._handle_record(patch))
    assert len(money.entries) == 1
    assert money.entries[0].amount == 20000
    assert money.entries[0].day == 21
    assert money.entries[0].status == "due"
    assert money.entries[0].cadence == "monthly"


def test_amount_patch_keeps_day(money: MoneyTools) -> None:
    first = _Params(
        {"items": [{"kind": "debt", "label": "Credit card", "amount": 20000, "day": 21}]}
    )
    asyncio.run(money._handle_record(first))
    item_id = first.result["recorded"][0]
    patch = _Params({"items": [{"id": item_id, "amount": 22000}]})
    asyncio.run(money._handle_record(patch))
    assert money.entries[0].amount == 22000
    assert money.entries[0].day == 21
    assert money.entries[0].id == item_id


def test_live_call_patch_sequence_keeps_card_on_timeline() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(
        money._handle_record(
            _Params({"name": "Sarvagna", "cash": 10000})
        )
    )
    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "items": [
                        {
                            "kind": "income",
                            "label": "Salary",
                            "amount": 30000,
                            "day": 5,
                            "status": "paid",
                        }
                    ]
                }
            )
        )
    )
    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "items": [
                        {
                            "kind": "debt",
                            "label": "Credit card",
                            "amount": 20000,
                            "day": 21,
                        }
                    ]
                }
            )
        )
    )
    card_id = money.entries[-1].id
    asyncio.run(
        money._handle_record(
            _Params({"items": [{"id": card_id, "status": "due"}]})
        )
    )
    asyncio.run(
        money._handle_record(
            _Params({"items": [{"id": card_id, "amount": 22000}]})
        )
    )
    asyncio.run(
        money._handle_record(
            _Params({"items": [{"id": card_id, "day": 21}]})
        )
    )
    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "items": [
                        {
                            "kind": "need",
                            "label": "Rent",
                            "amount": 15000,
                            "day": 3,
                            "cadence": "monthly",
                            "status": "paid",
                        }
                    ]
                }
            )
        )
    )
    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "items": [
                        {
                            "kind": "flex",
                            "label": "Dinner",
                            "amount": 2000,
                            "day": 20,
                        }
                    ]
                }
            )
        )
    )

    card = next(e for e in money.entries if e.id == card_id)
    assert card.amount == 22000
    assert card.day == 21
    assert card.status == "due"
    speak = money.snapshot()["speak"]
    assert speak["crunch_date"] == "2026-10-03"
    assert speak["crunch"] == 10000 - 2000 - 22000 - 15000
    assert "gap" not in speak
    assert money.snapshot()["plan"]["gap"] == 27000
    days = {d["date"]: d for d in money.snapshot()["derived"]["days"]}
    assert any(m["label"] == "Credit card" for m in days["2026-09-21"]["moves"])
    assert any(m["label"] == "Dinner" for m in days["2026-09-20"]["moves"])
    assert any(m["label"] == "Rent" for m in days["2026-10-03"]["moves"])
    by_label = {row["label"]: row["date"] for row in speak["upcoming"]}
    assert by_label["Dinner"] == "2026-09-20"
    assert by_label["Credit card"] == "2026-09-21"
    assert by_label["Rent"] == "2026-10-03"
    assert by_label["Salary"] == "2026-10-05"


def test_paid_salary_upcoming_is_next_month() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 10000})))
    add = _Params(
        {
            "items": [
                {
                    "kind": "income",
                    "label": "Salary",
                    "amount": 30000,
                    "day": 5,
                    "status": "paid",
                }
            ]
        }
    )
    asyncio.run(money._handle_record(add))
    upcoming = add.result["speak"]["upcoming"]
    assert upcoming == [
        {
            "id": money.entries[0].id,
            "label": "Salary",
            "amount": 30000,
            "kind": "income",
            "date": "2026-10-05",
        }
    ]
    assert money.entries[0].day == 5
    assert money.entries[0].status == "paid"


def test_daily_zomato_needs_no_day(money: MoneyTools) -> None:
    asyncio.run(money._handle_record(_Params({"cash": 20000})))
    params = _Params(
        {
            "items": [
                {"kind": "need", "label": "Zomato", "amount": 600, "cadence": "daily"}
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    assert params.result["recorded"]
    assert money.entries[0].cadence == "daily"
    assert money.entries[0].day is None
    days = money.published[-1]["derived"]["days"]  # type: ignore[attr-defined]
    assert sum(1 for d in days if any(m["label"] == "Zomato" for m in d["moves"])) == 30
    upcoming = params.result["speak"]["upcoming"]
    assert len(upcoming) == 1
    assert upcoming[0]["times"] == 30
    assert upcoming[0]["total"] == 18_000
    assert params.result["speak"]["headline"]["cash"] == 20_000
    assert params.result["speak"]["advice"]["points"] == []
    recap = _Params({})
    asyncio.run(money._handle_recap(recap))
    advice = recap.result["speak"]["advice"]
    assert any("Zomato" in line for line in advice["points"])
    assert "lowest" in advice["payoff"]
    assert money.snapshot()["advice"]["points"] == advice["points"]
    patch = _Params({"items": [{"id": money.entries[0].id, "amount": 700}]})
    asyncio.run(money._handle_record(patch))
    assert money.snapshot()["advice"]["points"] == []


def test_due_label_clash_keeps_old_and_records_conflict(money: MoneyTools) -> None:
    first = _Params(
        {
            "items": [
                {
                    "kind": "debt",
                    "label": "Card",
                    "amount": 20000,
                    "day": 21,
                    "status": "due",
                }
            ]
        }
    )
    asyncio.run(money._handle_record(first))
    second = _Params(
        {
            "items": [
                {
                    "kind": "debt",
                    "label": "Card",
                    "amount": 25000,
                    "day": 21,
                    "status": "due",
                }
            ]
        }
    )
    asyncio.run(money._handle_record(second))
    assert len(money.entries) == 1
    assert money.entries[0].amount == 20000
    assert second.result["recorded"] == []
    assert second.result["conflicts"] == ["Card: 20000 then 25000"]

    item_id = money.entries[0].id
    third = _Params({"items": [{"id": item_id, "amount": 25000}]})
    asyncio.run(money._handle_record(third))
    assert money.entries[0].amount == 25000
    assert third.result["conflicts"] == []


def test_finance_from_rows_rebuilds_plan(money: MoneyTools) -> None:
    from tools import finance_from_rows, _row

    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "cash": 12000,
                    "items": [
                        {
                            "kind": "income",
                            "label": "Salary",
                            "amount": 50000,
                            "day": 1,
                        },
                        {
                            "kind": "need",
                            "label": "Rent",
                            "amount": 20000,
                            "day": 5,
                        },
                    ],
                }
            )
        )
    )
    live = money.published[-1]  # type: ignore[attr-defined]
    rows = [_row(entry) for entry in money.entries]
    view = finance_from_rows(today=TODAY, cash=12000, rows=rows)
    assert view["derived"] == live["derived"]
    assert view["plan"]["solvable"] == live["plan"]["solvable"]
    assert view["plan"]["gap"] == live["plan"]["gap"]
    assert [e["label"] for e in view["entries"]] == ["Salary", "Rent"]


def test_rebuild_derived_matches_live_snapshot(money: MoneyTools) -> None:
    """Past-call history must rebuild the same 30-day calendar the call showed."""
    from tools import rebuild_derived, _row

    asyncio.run(
        money._handle_record(
            _Params(
                {
                    "cash": 12000,
                    "items": [
                        {
                            "kind": "income",
                            "label": "Salary",
                            "amount": 50000,
                            "day": 1,
                        },
                        {
                            "kind": "need",
                            "label": "Rent",
                            "amount": 20000,
                            "day": 5,
                        },
                    ],
                }
            )
        )
    )
    live = money.published[-1]["derived"]  # type: ignore[attr-defined]
    rows = [_row(entry) for entry in money.entries]
    rebuilt = rebuild_derived(today=TODAY, cash=12000, rows=rows)
    assert rebuilt is not None
    assert rebuilt["finish"] == live["finish"]
    assert rebuilt["crunch"] == live["crunch"]
    assert len(rebuilt["days"]) == 30
    assert rebuilt["days"] == live["days"]


def test_rebuild_derived_without_cash_is_none() -> None:
    from tools import rebuild_derived

    assert rebuild_derived(today=TODAY, cash=None, rows=[]) is None


def test_in_days_sets_on_date_not_today() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 15000})))
    params = _Params(
        {
            "items": [
                {
                    "kind": "need",
                    "label": "Airtel",
                    "amount": 700,
                    "in_days": 5,
                }
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    assert money.entries[0].on_date == "2026-09-19"
    assert money.entries[0].day == 19
    assert money.entries[0].cadence == "once"
    upcoming = params.result["speak"]["upcoming"]
    assert upcoming[0]["date"] == "2026-09-19"
    assert upcoming[0]["label"] == "Airtel"
    days = {d["date"]: d for d in published[-1]["derived"]["days"]}
    assert any(m["label"] == "Airtel" for m in days["2026-09-19"]["moves"])
    assert not any(m["label"] == "Airtel" for m in days["2026-09-14"]["moves"])


def test_overdue_due_keeps_original_date_on_upcoming() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 50_000})))
    params = _Params(
        {
            "items": [
                {
                    "kind": "need",
                    "label": "Rent",
                    "amount": 10_000,
                    "day": 5,
                    "status": "due",
                }
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    rent = params.result["speak"]["upcoming"][0]
    assert rent["date"] == "2026-09-05"
    assert rent["overdue"] is True
    assert rent["times"] == 2
    days = {d["date"]: d for d in published[-1]["derived"]["days"]}
    assert not any(m["label"] == "Rent" for m in days["2026-09-14"]["moves"])
    assert any(m["label"] == "Rent" for m in days["2026-10-05"]["moves"])
    assert published[-1]["derived"]["overdue"] == [
        {
            "id": money.entries[0].id,
            "label": "Rent",
            "amount": 10_000,
            "kind": "need",
            "date": "2026-09-05",
        }
    ]


def test_two_freelance_dates_in_one_call() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 15000})))
    params = _Params(
        {
            "items": [
                {
                    "kind": "income",
                    "label": "Freelance project",
                    "amount": 25000,
                    "day": 18,
                    "cadence": "once",
                },
                {
                    "kind": "income",
                    "label": "Freelance project",
                    "amount": 25000,
                    "day": 2,
                    "cadence": "once",
                },
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    assert len(money.entries) == 2
    days = {e.day for e in money.entries}
    assert days == {18, 2}
    dates = {row["date"] for row in params.result["speak"]["upcoming"]}
    assert "2026-09-18" in dates
    assert "2026-10-02" in dates


def test_two_freelance_dates_without_once_cadence() -> None:
    """Live call omitted cadence; different days must still be two facts."""
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 15000})))
    params = _Params(
        {
            "items": [
                {
                    "kind": "income",
                    "label": "Freelance project",
                    "amount": 25000,
                    "day": 18,
                },
                {
                    "kind": "income",
                    "label": "Freelance project",
                    "amount": 25000,
                    "day": 2,
                },
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    assert len(money.entries) == 2
    dates = {row["date"] for row in params.result["speak"]["upcoming"]}
    assert "2026-09-18" in dates
    assert "2026-10-02" in dates


def test_owed_friend_is_incoming() -> None:
    published: list[dict[str, Any]] = []

    async def on_change(payload: dict[str, Any]) -> None:
        published.append(payload)

    money = MoneyTools(on_change=on_change, today=date(2026, 9, 14))
    asyncio.run(money._handle_record(_Params({"cash": 15000})))
    params = _Params(
        {
            "items": [
                {
                    "kind": "owed",
                    "label": "Karthik",
                    "amount": 5000,
                    "day": 24,
                    "cadence": "once",
                }
            ]
        }
    )
    asyncio.run(money._handle_record(params))
    assert money.entries[0].kind == "owed"
    day = next(
        d
        for d in published[-1]["derived"]["days"]
        if d["date"] == "2026-09-24"
    )
    assert day["in"] == 5000
    assert day["out"] == 0
    assert published[-1]["items"][0]["direction"] == "incoming"
