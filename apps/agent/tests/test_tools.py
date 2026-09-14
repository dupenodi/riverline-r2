"""Money tools record incoming/outgoing without planning."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tools import MoneyTools


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

    tools = MoneyTools(on_change=on_change)
    tools.published = published  # type: ignore[attr-defined]
    return tools


def test_add_money_records_incoming_and_outgoing(money: MoneyTools) -> None:
    params = _Params(
        {
            "items": [
                {
                    "direction": "incoming",
                    "label": "Salary",
                    "amount": 50000,
                    "day": 1,
                },
                {
                    "direction": "outgoing",
                    "label": "Rent",
                    "amount": 20000,
                    "day": 5,
                },
            ],
            "user_name": "Priya",
        }
    )
    asyncio.run(money._handle_add(params))

    assert len(params.result["recorded"]) == 2
    assert money.user_name == "Priya"
    assert [i["label"] for i in money.items] == ["Salary", "Rent"]
    assert money.items[0]["day"] == 1
    snap = money.snapshot()
    assert snap["type"] == "transactions"
    assert snap["name"] == "Priya"
    assert len(snap["items"]) == 2


def test_add_money_rejects_bad_direction(money: MoneyTools) -> None:
    params = _Params(
        {
            "items": [
                {
                    "direction": "sideways",
                    "label": "X",
                    "amount": 10,
                    "day": 1,
                }
            ]
        }
    )
    asyncio.run(money._handle_add(params))
    assert params.result["recorded"] == []
    assert "could_not_record" in params.result
    assert money.items == []


def test_add_money_requires_day(money: MoneyTools) -> None:
    params = _Params(
        {
            "items": [
                {"direction": "outgoing", "label": "EMI", "amount": 8000}
            ]
        }
    )
    asyncio.run(money._handle_add(params))
    assert params.result["recorded"] == []
    assert "could_not_record" in params.result


def test_remove_money(money: MoneyTools) -> None:
    add = _Params(
        {
            "items": [
                {
                    "direction": "outgoing",
                    "label": "EMI",
                    "amount": 8000,
                    "day": 10,
                }
            ]
        }
    )
    asyncio.run(money._handle_add(add))
    item_id = add.result["recorded"][0]

    remove = _Params({"ids": [item_id]})
    asyncio.run(money._handle_remove(remove))
    assert remove.result["removed"] == [item_id]
    assert money.items == []


def test_schemas_are_two_simple_tools(money: MoneyTools) -> None:
    names = [s.name for s in money.schemas()]
    assert names == ["add_money", "remove_money"]
