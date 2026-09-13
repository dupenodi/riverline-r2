"""Tool-layer tests.

This is the boundary where whatever the model produces meets the planner, so
the cases that matter are the malformed and hostile ones: a mis-heard number, a
field the model invented, a plan asked for too early.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from finance import FinanceState, fact_from_item
from tools import FinanceTools, snapshot

TODAY = date(2026, 9, 15)


class Recorder:
    """Captures what would have been pushed to the UI."""

    def __init__(self) -> None:
        self.pushes: list[dict[str, Any]] = []

    async def __call__(self, payload: dict[str, Any]) -> None:
        self.pushes.append(payload)


class Params:
    """The bits of FunctionCallParams the handlers actually touch."""

    def __init__(self, **arguments: Any) -> None:
        self.arguments = arguments
        self.result: Any = None

    async def result_callback(self, result: Any) -> None:
        self.result = result


def make() -> tuple[FinanceTools, Recorder]:
    pushes = Recorder()
    return FinanceTools(on_change=pushes, today=lambda: TODAY), pushes


async def call(tools: FinanceTools, name: str, **kwargs: Any) -> Any:
    params = Params(**kwargs)
    handler = {
        "update_finances": tools._handle_update,
        "build_plan": tools._handle_build_plan,
        "check_day": tools._handle_check_day,
    }[name]
    await handler(params)
    return params.result


pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


async def test_a_batch_of_facts_is_recorded_in_one_call():
    tools, pushes = make()
    result = await call(
        tools,
        "update_finances",
        items=[
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": 24000, "day": 5},
            {"id": "emi", "kind": "debt", "label": "Car EMI", "amount": 12000, "day": 10},
        ],
    )
    assert set(result["recorded"]) == {"rent", "emi"}
    assert len(tools.state.facts) == 2
    assert len(pushes.pushes) == 1


async def test_the_result_carries_current_state_so_no_read_tool_is_needed():
    tools, _ = make()
    result = await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 24000, "day": 5}],
    )
    assert "Rent" in result["current_state"]
    assert result["still_missing"]


async def test_reusing_an_id_corrects_rather_than_duplicates():
    tools, _ = make()
    await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 20000, "day": 5}],
    )
    result = await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 24000, "day": 5}],
    )
    assert len(tools.state.facts) == 1
    assert tools.state.facts["rent"].amount == 24000
    assert result["needs_confirming"]


async def test_retraction_removes_the_fact():
    tools, _ = make()
    await call(
        tools,
        "update_finances",
        items=[{"id": "gym", "kind": "optional", "label": "Gym", "amount": 2000, "day": 5}],
    )
    await call(tools, "update_finances", remove=["gym"])
    assert tools.state.facts == {}


# --------------------------------------------------------------------------
# Malformed input from the model
# --------------------------------------------------------------------------


async def test_a_bad_value_is_reported_back_instead_of_raising():
    tools, _ = make()
    result = await call(
        tools,
        "update_finances",
        items=[
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": -5, "day": 5},
            {"id": "emi", "kind": "debt", "label": "EMI", "amount": 9000, "day": 8},
        ],
    )
    # The good one still lands; the bad one comes back as something to ask about.
    assert result["recorded"] == ["emi"]
    assert result["could_not_record"]
    # The instruction must tell it to retry silently: told only that something
    # failed, the model narrated the failure to the user and lost the figure.
    assert "call update_finances again" in result["instruction"].lower()
    assert "do not mention this to the user" in result["instruction"].lower()


async def test_an_invented_field_does_not_lose_the_number():
    tools, _ = make()
    result = await call(
        tools,
        "update_finances",
        items=[
            {
                "id": "rent",
                "kind": "essential",
                "label": "Rent",
                "amount": 24000,
                "day": 5,
                "currency": "INR",       # not in the schema
                "notes": "paid by UPI",  # not in the schema
            }
        ],
    )
    assert result["recorded"] == ["rent"]
    assert tools.state.facts["rent"].amount == 24000


async def test_a_missing_required_field_is_reported_not_raised():
    tools, _ = make()
    result = await call(
        tools, "update_finances", items=[{"kind": "essential", "amount": 100}]
    )
    assert result["recorded"] == []
    assert result["could_not_record"]


async def test_junk_in_the_items_array_is_ignored():
    tools, _ = make()
    result = await call(tools, "update_finances", items=["not an object", None, 42])
    assert result["recorded"] == []


async def test_an_empty_call_is_harmless():
    tools, _ = make()
    result = await call(tools, "update_finances")
    assert result["recorded"] == []


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------


async def _load_a_full_picture(tools: FinanceTools) -> None:
    await call(
        tools,
        "update_finances",
        items=[
            {"id": "cash", "kind": "balance", "label": "Money in hand", "amount": 9000},
            {"id": "salary", "kind": "income", "label": "Salary", "amount": 50000, "day": 1},
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": 18000, "day": 5},
        ],
    )


async def test_a_plan_is_refused_while_information_is_missing():
    tools, _ = make()
    await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 18000, "day": 5}],
    )
    result = await call(tools, "build_plan")
    assert result["ready"] is False
    assert result["still_missing"]
    assert tools.plan is None


async def test_a_complete_picture_produces_a_plan():
    tools, pushes = make()
    await _load_a_full_picture(tools)
    result = await call(tools, "build_plan")
    assert result["ready"] is True
    assert result["solvable"] is True
    assert pushes.pushes[-1]["plan"] is not None


async def test_every_figure_in_the_result_is_precomputed():
    """The model must never have to work a number out for itself."""
    tools, _ = make()
    await _load_a_full_picture(tools)
    result = await call(tools, "build_plan")
    for key in ("money_on_hand", "coming_in", "going_out", "lowest_balance"):
        assert isinstance(result[key], int)


async def test_an_unsolvable_month_is_labelled_and_steered_away_from_lending():
    tools, _ = make()
    await call(
        tools,
        "update_finances",
        items=[
            {"id": "cash", "kind": "balance", "label": "Money in hand", "amount": 1000},
            {"id": "salary", "kind": "income", "label": "Salary", "amount": 9000, "day": 28},
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": 30000, "day": 18},
        ],
    )
    result = await call(tools, "build_plan")
    assert result["solvable"] is False
    assert result["short_by"] > 0
    assert "do not suggest a loan" in result["instruction"].lower()


async def test_correcting_a_number_after_planning_refreshes_the_plan():
    """A card left showing figures the user has already corrected is the exact
    inconsistency the brief warns about."""
    tools, pushes = make()
    await _load_a_full_picture(tools)
    await call(tools, "build_plan")
    before = pushes.pushes[-1]["plan"]["total_out"]

    await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 26000, "day": 5}],
    )
    after = pushes.pushes[-1]["plan"]["total_out"]
    assert after != before
    assert after - before == 8000


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------


async def test_the_snapshot_is_json_serialisable():
    import json

    tools, _ = make()
    await _load_a_full_picture(tools)
    await call(tools, "build_plan")
    payload = snapshot(tools.state, tools.plan)
    json.dumps(payload)  # must not raise
    assert len(payload["plan"]["timeline"]) == 30


async def test_the_version_rises_with_every_change_so_stale_pushes_can_be_dropped():
    tools, pushes = make()
    await _load_a_full_picture(tools)
    await call(
        tools,
        "update_finances",
        items=[{"id": "gym", "kind": "optional", "label": "Gym", "amount": 1500, "day": 9}],
    )
    versions = [p["version"] for p in pushes.pushes]
    assert versions == sorted(versions)
    assert versions[-1] > versions[0]


async def test_a_plan_is_not_blocked_by_an_undated_expense():
    """Observed deadlock: the agent refused to plan and kept asking which day
    the user eats out, while they were saying "that's everything"."""
    tools, _ = make()
    await call(
        tools,
        "update_finances",
        items=[
            {"id": "cash", "kind": "balance", "label": "Money in hand", "amount": 9000},
            {"id": "salary", "kind": "income", "label": "Salary", "amount": 50000, "day": 1},
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": 18000, "day": 5},
            {"id": "dining", "kind": "optional", "label": "Eating out", "amount": 5000},
        ],
    )
    result = await call(tools, "build_plan")
    assert result["ready"] is True


async def test_every_number_the_model_might_say_is_precomputed():
    tools, _ = make()
    await _load_a_full_picture(tools)
    result = await call(tools, "build_plan")
    for key in (
        "money_on_hand",
        "coming_in",
        "going_out",
        "left_at_the_end",
        "lowest_balance",
    ):
        assert isinstance(result[key], int), key
    assert result["lowest_balance_day"]
    assert "do not add up" in result["instruction"].lower()


async def test_the_snapshot_carries_a_projection_once_the_balance_is_known():
    """The calendar must be able to appear mid-conversation, not only at the end."""
    tools, pushes = make()

    await call(
        tools,
        "update_finances",
        items=[{"id": "rent", "kind": "essential", "label": "Rent", "amount": 20000, "day": 20}],
    )
    # An expense alone says nothing about what is in the account. Drawing a
    # calendar here would put the month deep in the red on no evidence.
    assert pushes.pushes[-1]["projection"] is None

    await call(
        tools,
        "update_finances",
        items=[{"id": "cash", "kind": "balance", "label": "Money in hand", "amount": 30000}],
    )
    forecast = pushes.pushes[-1]["projection"]
    assert forecast is not None
    assert len(forecast["timeline"]) == 30
    # Still no plan: the user has not asked for one.
    assert pushes.pushes[-1]["plan"] is None


async def test_the_projection_never_shows_relief_the_agent_has_not_offered():
    tools, pushes = make()
    await call(
        tools,
        "update_finances",
        items=[
            {"id": "cash", "kind": "balance", "label": "Money in hand", "amount": 5000},
            {"id": "rent", "kind": "essential", "label": "Rent", "amount": 20000, "day": 20},
            {"id": "trip", "kind": "optional", "label": "Trip", "amount": 6000, "day": 18},
            {"id": "salary", "kind": "income", "label": "Salary", "amount": 30000, "day": 28},
        ],
    )
    forecast = pushes.pushes[-1]["projection"]
    assert forecast["cut"] == []
    assert forecast["actions"] == []

    await call(tools, "build_plan")
    # The plan may well cut the trip; the projection beside it still shows the
    # month as it stands, so the two cards answer two different questions.
    assert pushes.pushes[-1]["projection"]["cut"] == []


# --- group subtotals shown in the rail ---------------------------------------


def _state(*items: dict) -> FinanceState:
    state = FinanceState()
    for item in items:
        state.upsert(fact_from_item(item))
    return state


async def test_totals_are_empty_before_anything_is_said() -> None:
    totals = FinanceState().kind_totals()

    assert totals["income"] == {"amount": None, "estimated": False, "count": 0}


async def test_totals_add_up_a_group() -> None:
    state = _state(
        {"id": "rent", "kind": "essential", "label": "Rent", "amount": 24000},
        {"id": "power", "kind": "essential", "label": "Electricity", "amount": 2400},
    )

    assert state.kind_totals()["essential"]["amount"] == 26400
    assert state.kind_totals()["essential"]["count"] == 2


async def test_a_group_holding_one_guess_is_a_guess() -> None:
    state = _state(
        {"id": "rent", "kind": "essential", "label": "Rent", "amount": 24000},
        {
            "id": "food",
            "kind": "essential",
            "label": "Eating out",
            "amount": 5000,
            "certainty": "estimated",
        },
    )

    assert state.kind_totals()["essential"]["estimated"] is True


async def test_a_range_totals_the_way_the_plan_will_read_it() -> None:
    """Outgoings take the high end, income the low. The rail must not show a
    friendlier number than the planner is working with."""
    state = _state(
        {
            "id": "food",
            "kind": "essential",
            "label": "Groceries",
            "amount_min": 4000,
            "amount_max": 6000,
        },
        {
            "id": "gig",
            "kind": "income",
            "label": "Freelance",
            "amount_min": 10000,
            "amount_max": 20000,
        },
    )
    totals = state.kind_totals()

    assert totals["essential"]["amount"] == 6000
    assert totals["income"]["amount"] == 10000
    assert totals["essential"]["estimated"] is True


async def test_totals_ride_along_in_the_snapshot() -> None:
    state = _state(
        {"id": "bal", "kind": "balance", "label": "In hand", "amount": 35000}
    )

    assert snapshot(state, None)["totals"]["balance"]["amount"] == 35000


# --- check_day: answering a question about one date --------------------------
#
# Added after a real call: asked "what will be my balance on 29th?", the agent
# said it had no day-by-day figure and named the tool it was missing. The
# numbers existed in the timeline the whole time; nothing could reach them.


def funded() -> FinanceTools:
    """A state with enough in it to project a timeline."""
    tools, _ = make()
    for item in (
        {"id": "bal", "kind": "balance", "label": "In hand", "amount": 30000},
        {"id": "pay", "kind": "income", "label": "Salary", "amount": 50000, "day": 1},
        {"id": "rent", "kind": "essential", "label": "Rent", "amount": 20000, "day": 20},
    ):
        tools.state.upsert(fact_from_item(item))
    return tools


async def test_a_date_question_is_answered_from_the_timeline():
    result = await call(funded(), "check_day", day=20)

    assert result["ready"] is True
    assert result["date"] == "20 September"
    assert result["money_out_that_day"] == 20000
    assert any(m["what"] == "Rent" for m in result["what_moves_that_day"])


async def test_a_quiet_day_still_answers():
    """Most days have nothing on them; the balance is still the answer."""
    result = await call(funded(), "check_day", day=17)

    assert result["ready"] is True
    assert result["what_moves_that_day"] == []
    assert isinstance(result["balance_at_the_end_of_that_day"], int)


async def test_a_date_question_works_before_a_plan_is_built():
    """The user asked on turn six, long before anyone said "build me a plan"."""
    tools = funded()
    assert tools.plan is None

    assert (await call(tools, "check_day", day=20))["ready"] is True


async def test_a_date_beyond_the_window_says_so():
    """15 Sep to 14 Oct covers every day-of-month from 1 to 30 somewhere in it.
    Only a 31st falls outside, September having none and 31 Oct being past the
    end — so that is the one case where "I cannot see that far" is the answer."""
    result = await call(funded(), "check_day", day=31)

    assert result["ready"] is False
    assert "window_ends" in result


async def test_a_date_question_before_any_balance_asks_for_one():
    """No opening balance means no timeline, and no honest answer."""
    tools, _ = make()

    result = await call(tools, "check_day", day=20)

    assert result["ready"] is False
    assert result["still_missing"]


async def test_a_nonsense_day_is_rejected():
    assert (await call(funded(), "check_day", day=47))["ready"] is False
    assert (await call(funded(), "check_day", day="tuesday"))["ready"] is False


async def test_the_tightest_day_is_flagged():
    """So the agent can say "that is your worst day" without working it out."""
    assert (await call(funded(), "check_day", day=20))["is_the_tightest_day"] is True
