"""Planner tests.

No LLM, no network, no clock — `today` is passed in, so every case here is
deterministic and runs in milliseconds rather than in 40-second phone calls.

The dates matter as much as the amounts. Several of these cases have identical
monthly totals and completely different answers, which is the whole reason the
planner walks a timeline instead of netting totals.
"""

from __future__ import annotations

from datetime import date

import pytest

from finance import Fact, FactError, FinanceState
from plan import WINDOW_DAYS, build_plan, project

# A 15th start, so the 30-day window straddles two months — the normal case,
# and the one a calendar-month implementation gets wrong.
TODAY = date(2026, 9, 15)


def state(*facts: Fact) -> FinanceState:
    s = FinanceState()
    for f in facts:
        s.upsert(f)
    return s


def balance(amount: int) -> Fact:
    return Fact(id="cash", kind="balance", label="Money in hand", amount=amount)


# --------------------------------------------------------------------------
# Timeline shape
# --------------------------------------------------------------------------


def test_window_is_thirty_days_from_today_not_a_calendar_month():
    plan = build_plan(state(balance(10_000)), TODAY)
    assert len(plan.timeline) == WINDOW_DAYS
    assert plan.timeline[0].day == TODAY
    assert plan.timeline[-1].day == date(2026, 10, 14)
    # Straddles the month boundary.
    assert {c.day.month for c in plan.timeline} == {9, 10}


def test_monthly_bill_can_occur_twice_in_a_straddling_window():
    # Rent on the 20th falls on 20 Sep and 20 Oct... but 20 Oct is outside a
    # window ending 14 Oct, so exactly once. The 1st, however, falls once too.
    plan = build_plan(
        state(
            balance(100_000),
            Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20),
        ),
        TODAY,
    )
    hits = [c.day for c in plan.timeline if c.total_out]
    assert hits == [date(2026, 9, 20)]


def test_monthly_bill_on_the_31st_clamps_into_a_thirty_day_month():
    # September has 30 days. A bill set for the 31st must still come out.
    plan = build_plan(
        state(
            balance(50_000),
            Fact(id="emi", kind="debt", label="EMI", amount=8_000, day=31),
        ),
        date(2026, 9, 1),
    )
    hits = [c.day for c in plan.timeline if c.total_out]
    assert hits == [date(2026, 9, 30)]


def test_weekly_expense_recurs_across_the_window():
    plan = build_plan(
        state(
            balance(100_000),
            Fact(
                id="groceries",
                kind="essential",
                label="Groceries",
                amount=2_000,
                frequency="weekly",
            ),
        ),
        TODAY,
    )
    assert plan.total_out == 2_000 * 5  # days 0, 7, 14, 21, 28


def test_already_paid_is_not_counted_again():
    plan = build_plan(
        state(
            balance(10_000),
            Fact(
                id="emi",
                kind="debt",
                label="Car EMI",
                amount=9_000,
                day=20,
                status="already_paid",
            ),
        ),
        TODAY,
    )
    assert plan.total_out == 0
    assert plan.solvable


# --------------------------------------------------------------------------
# The case totals-only math gets wrong
# --------------------------------------------------------------------------


def test_income_after_the_bill_is_a_shortfall_even_though_the_month_nets_positive():
    """Same numbers, wrong order. Monthly totals would call this comfortable."""
    plan = build_plan(
        state(
            balance(5_000),
            Fact(id="salary", kind="income", label="Salary", amount=60_000, day=10),
            Fact(id="rent", kind="essential", label="Rent", amount=25_000, day=20),
        ),
        TODAY,
    )
    # Nets +40,000 over the window, yet rent lands before the salary does.
    assert plan.net == 35_000
    assert plan.has_shortfall
    assert plan.crunch_day == date(2026, 9, 20)


def test_same_numbers_in_the_other_order_are_fine():
    plan = build_plan(
        state(
            balance(5_000),
            Fact(id="salary", kind="income", label="Salary", amount=60_000, day=18),
            Fact(id="rent", kind="essential", label="Rent", amount=25_000, day=20),
        ),
        TODAY,
    )
    assert plan.solvable
    assert plan.shortfall == 0


# --------------------------------------------------------------------------
# Shortfall resolution
# --------------------------------------------------------------------------


def test_optional_spend_is_cut_before_anything_else():
    # Dips to -2,000 on the 18th; dropping the 6,000 of eating out on the 16th
    # is enough on its own to carry the month.
    plan = build_plan(
        state(
            balance(12_000),
            Fact(id="salary", kind="income", label="Salary", amount=20_000, day=25),
            Fact(id="rent", kind="essential", label="Rent", amount=8_000, day=18),
            Fact(id="dining", kind="optional", label="Eating out", amount=6_000, day=16),
        ),
        TODAY,
    )
    assert plan.solvable
    assert [m.fact_id for m in plan.cut] == ["dining"]
    assert any(a.kind == "cut_optional" for a in plan.actions)


def test_optional_spend_after_the_crunch_is_not_treated_as_relief():
    """Cutting something that falls later frees no money before the dip."""
    plan = build_plan(
        state(
            balance(5_000),
            Fact(id="rent", kind="essential", label="Rent", amount=18_000, day=16),
            Fact(id="salary", kind="income", label="Salary", amount=30_000, day=20),
            Fact(id="trip", kind="optional", label="Weekend trip", amount=9_000, day=30),
        ),
        TODAY,
    )
    # The dip is on the 16th. By the 30th the salary has landed and the trip is
    # affordable, so cutting it would be theatre that fixes nothing.
    assert not plan.solvable
    assert plan.crunch_day == date(2026, 9, 16)
    assert plan.cut == []


def test_optional_is_preferred_over_paying_only_a_card_minimum():
    """When cutting discretionary spend is enough, the card still gets paid."""
    plan = build_plan(
        state(
            balance(30_000),
            Fact(id="salary", kind="income", label="Salary", amount=20_000, day=28),
            Fact(
                id="card",
                kind="debt",
                label="Credit card",
                amount=20_000,
                minimum_due=2_000,
                day=18,
            ),
            Fact(id="subs", kind="optional", label="Subscriptions", amount=12_000, day=16),
        ),
        TODAY,
    )
    assert plan.solvable
    assert [m.fact_id for m in plan.cut] == ["subs"]
    assert not any(a.kind == "pay_minimum" for a in plan.actions)


def test_a_card_minimum_is_used_when_cutting_optional_cannot_close_the_gap():
    plan = build_plan(
        state(
            balance(5_000),
            Fact(id="salary", kind="income", label="Salary", amount=20_000, day=28),
            Fact(
                id="card",
                kind="debt",
                label="Credit card",
                amount=20_000,
                minimum_due=2_000,
                day=18,
            ),
            Fact(id="subs", kind="optional", label="Subscriptions", amount=1_000, day=16),
        ),
        TODAY,
    )
    assert plan.solvable
    assert any(a.kind == "pay_minimum" for a in plan.actions)


def test_a_sacrifice_that_turns_out_to_be_unnecessary_is_given_back():
    """The greedy pass cuts small things first, then finds a much bigger lever.

    Without a restoration pass the plan keeps both and tells someone to cancel
    dinner for no reason. Every remaining cut must be one the month depends on.
    """
    plan = build_plan(
        state(
            balance(5_000),
            Fact(id="salary", kind="income", label="Salary", amount=20_000, day=28),
            Fact(
                id="card",
                kind="debt",
                label="Credit card",
                amount=20_000,
                minimum_due=2_000,
                day=18,
            ),
            Fact(id="subs", kind="optional", label="Subscriptions", amount=1_000, day=16),
            Fact(id="dining", kind="optional", label="Eating out", amount=900, day=17),
        ),
        TODAY,
    )
    assert plan.solvable
    # The card minimum alone carries it, so neither cut was needed.
    assert plan.cut == []
    assert any(a.kind == "pay_minimum" for a in plan.actions)


def test_every_surviving_cut_is_load_bearing():
    """Property: putting any single cut back must break the plan."""
    from plan import _build_timeline, _lowest  # noqa: PLC0415

    s = state(
        balance(20_000),
        Fact(id="salary", kind="income", label="Salary", amount=26_000, day=28),
        Fact(id="rent", kind="essential", label="Rent", amount=15_000, day=17),
        Fact(id="gym", kind="optional", label="Gym", amount=3_000, day=16),
        Fact(id="dining", kind="optional", label="Eating out", amount=7_000, day=16),
        Fact(id="ott", kind="optional", label="Streaming", amount=800, day=16),
    )
    plan = build_plan(s, TODAY)
    assert plan.solvable
    assert plan.cut, "this scenario is meant to require at least one cut"

    skip = {m.fact_id for m in plan.cut}
    for restored in skip:
        cells = _build_timeline(s, TODAY, skip=skip - {restored}, minimum_only=set())
        assert _lowest(cells)[0] < 0, f"cutting {restored} was not necessary"


def test_unsolvable_month_says_so_plainly():
    plan = build_plan(
        state(
            balance(1_000),
            Fact(id="salary", kind="income", label="Salary", amount=10_000, day=28),
            Fact(id="rent", kind="essential", label="Rent", amount=30_000, day=18),
        ),
        TODAY,
    )
    assert not plan.solvable
    # Deepest point, not the closing position: -29,000 on the 18th, ten days
    # before the salary arrives. Netting the month would have said -19,000 and
    # understated how bad it gets.
    assert plan.shortfall == 29_000
    assert plan.crunch_day == date(2026, 9, 18)
    head = plan.actions[0]
    assert head.kind == "shortfall"
    assert head.amount == 29_000


def test_no_action_ever_suggests_borrowing():
    plan = build_plan(
        state(
            balance(0),
            Fact(id="rent", kind="essential", label="Rent", amount=40_000, day=18),
        ),
        TODAY,
    )
    words = " ".join(f"{a.label} {a.detail}" for a in plan.actions).lower()
    for banned in ("loan", "borrow", "credit line", "advance"):
        assert banned not in words


# --------------------------------------------------------------------------
# Uncertainty is resolved against the user, never averaged
# --------------------------------------------------------------------------


def test_income_range_plans_on_the_low_end():
    plan = build_plan(
        state(
            balance(0),
            Fact(
                id="freelance",
                kind="income",
                label="Freelance",
                amount_min=20_000,
                amount_max=60_000,
                day=20,
                certainty="estimated",
            ),
        ),
        TODAY,
    )
    assert plan.total_in == 20_000


def test_expense_range_plans_on_the_high_end():
    plan = build_plan(
        state(
            balance(0),
            Fact(
                id="power",
                kind="essential",
                label="Electricity",
                amount_min=2_000,
                amount_max=5_000,
                day=20,
                certainty="estimated",
            ),
        ),
        TODAY,
    )
    assert plan.total_out == 5_000


def test_uncertain_dates_assume_the_worst_gap():
    """Income late, bills early — the widest window where things go wrong."""
    s = state(
        balance(0),
        Fact(id="salary", kind="income", label="Salary", day_min=5, day_max=7, amount=1),
        Fact(id="rent", kind="essential", label="Rent", day_min=1, day_max=3, amount=1),
    )
    assert s.facts["salary"].planning_day() == 7
    assert s.facts["rent"].planning_day() == 1


# --------------------------------------------------------------------------
# Corrections and conflicts
# --------------------------------------------------------------------------


def test_restating_an_amount_updates_the_plan():
    s = state(
        balance(50_000),
        Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20),
    )
    s.upsert(Fact(id="rent", kind="essential", label="Rent", amount=24_000, day=20))
    plan = build_plan(s, TODAY)
    assert plan.total_out == 24_000


def test_a_material_restatement_is_flagged_for_confirmation():
    s = state(Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20))
    s.upsert(Fact(id="rent", kind="essential", label="Rent", amount=24_000, day=20))
    assert len(s.conflicts) == 1
    assert (s.conflicts[0].previous, s.conflicts[0].current) == (20_000, 24_000)


def test_a_trivial_restatement_is_not_worth_asking_about():
    s = state(Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20))
    s.upsert(Fact(id="rent", kind="essential", label="Rent", amount=20_050, day=20))
    assert s.conflicts == []


def test_an_estimate_becoming_exact_is_not_a_conflict():
    s = state(
        Fact(
            id="power",
            kind="essential",
            label="Electricity",
            amount=3_000,
            certainty="estimated",
            day=20,
        )
    )
    s.upsert(
        Fact(id="power", kind="essential", label="Electricity", amount=4_200, day=20)
    )
    assert s.conflicts == []


def test_retracting_a_fact_removes_it_and_its_conflict():
    s = state(Fact(id="gym", kind="optional", label="Gym", amount=2_000, day=20))
    s.upsert(Fact(id="gym", kind="optional", label="Gym", amount=3_500, day=20))
    assert s.conflicts
    assert s.remove("gym")
    assert s.facts == {}
    assert s.conflicts == []
    assert not s.remove("gym")


# --------------------------------------------------------------------------
# Missing information
# --------------------------------------------------------------------------


def test_missing_information_is_listed_before_anything_is_known():
    gaps = FinanceState().missing()
    assert len(gaps) == 3


def test_a_fact_without_an_amount_is_reported_as_missing():
    s = state(
        balance(1_000),
        Fact(id="salary", kind="income", label="Salary", amount=10_000, day=1),
        Fact(id="rent", kind="essential", label="Rent", day=5),
    )
    assert any("how much rent" in g.lower() for g in s.missing())


def test_a_missing_due_date_sharpens_the_plan_but_does_not_block_it():
    """An earlier version blocked on this and deadlocked the conversation."""
    s = state(
        balance(1_000),
        Fact(id="salary", kind="income", label="Salary", amount=10_000, day=1),
        Fact(id="rent", kind="essential", label="Rent", amount=20_000),
    )
    assert s.missing() == []
    assert any("when rent" in g.lower() for g in s.would_sharpen())


def test_an_undated_monthly_amount_is_spread_across_the_window():
    plan = build_plan(
        state(
            balance(50_000),
            Fact(id="dining", kind="optional", label="Eating out", amount=6_000),
        ),
        TODAY,
    )
    # Spread, not charged in full every day, and the parts still sum to what
    # the user actually said.
    assert plan.total_out == 6_000
    assert all(c.total_out > 0 for c in plan.timeline)


def test_spreading_does_not_lose_rupees_to_rounding():
    for amount in (5_000, 6_001, 999, 30_031):
        plan = build_plan(
            state(
                balance(1_000_000),
                Fact(id="x", kind="optional", label="Thing", amount=amount),
            ),
            TODAY,
        )
        assert plan.total_out == amount


def test_a_fact_with_no_amount_cannot_silently_reach_the_timeline():
    plan = build_plan(
        state(balance(5_000), Fact(id="rent", kind="essential", label="Rent", day=20)),
        TODAY,
    )
    assert plan.total_out == 0
    assert plan.missing


# --------------------------------------------------------------------------
# Input the agent should re-ask about rather than record
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"amount": -5_000},
        {"amount": 10**12},
        {"day": 0},
        {"day": 45},
        {"amount_min": 50_000, "amount_max": 10_000},
        {"day_min": 20, "day_max": 5},
        {"amount": 5_000, "minimum_due": 9_000},
    ],
)
def test_impossible_values_are_rejected(kwargs):
    with pytest.raises(FactError):
        Fact(id="x", kind="essential", label="Thing", **kwargs)


def test_a_valid_fact_with_a_minimum_due_is_accepted():
    fact = Fact(
        id="card", kind="debt", label="Card", amount=20_000, minimum_due=2_000, day=10
    )
    assert fact.minimum_due == 2_000


@pytest.mark.parametrize(
    "kwargs",
    [
        # Observed from a real model: it put the frequency into the kind field.
        {"kind": "one_time"},
        {"kind": "expense"},
        {"frequency": "fortnightly"},
        {"certainty": "maybe"},
        {"status": "pending"},
    ],
)
def test_enum_values_outside_the_schema_are_rejected(kwargs):
    base = {"id": "x", "kind": "essential", "label": "Thing", "amount": 1_000, "day": 5}
    with pytest.raises(FactError):
        Fact(**{**base, **kwargs})


# --- the live projection -----------------------------------------------------
#
# What the calendar draws mid-conversation. It must be the month as it *is*,
# never the month as the planner would like it to be: showing a cut the agent
# has not yet proposed would put the screen at odds with what the user is
# hearing, which is the one thing generative cards must never do.


def test_projection_leaves_a_shortfall_alone():
    s = state(
        Fact(id="bal", kind="balance", label="In hand", amount=5_000),
        Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20),
        Fact(id="trip", kind="optional", label="Weekend trip", amount=6_000, day=18),
        Fact(id="pay", kind="income", label="Salary", amount=30_000, day=28),
    )
    forecast = project(s, TODAY)

    assert forecast.cut == []
    assert forecast.actions == []
    assert not forecast.solvable
    # The trip is still in the outgoings — a forecast reports, it does not advise.
    assert any(
        m.fact_id == "trip" for cell in forecast.timeline for m in cell.outflows
    )


def test_projection_and_plan_agree_when_the_month_already_works():
    s = state(
        Fact(id="bal", kind="balance", label="In hand", amount=60_000),
        Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=20),
        Fact(id="pay", kind="income", label="Salary", amount=50_000, day=28),
    )
    forecast, plan = project(s, TODAY), build_plan(s, TODAY)

    assert forecast.solvable and plan.solvable
    assert forecast.min_balance == plan.min_balance
    assert [c.closing_balance for c in forecast.timeline] == [
        c.closing_balance for c in plan.timeline
    ]


def test_projection_covers_the_whole_window_from_the_first_fact():
    s = state(Fact(id="bal", kind="balance", label="In hand", amount=9_000))
    forecast = project(s, TODAY)

    assert len(forecast.timeline) == WINDOW_DAYS
    assert forecast.timeline[0].day == TODAY
    # Nothing is known to move yet, so the balance holds flat all month.
    assert {c.closing_balance for c in forecast.timeline} == {9_000}


def test_undated_spending_is_one_action_not_thirty():
    """Spreading is a planning device; it must not leak into the advice."""
    s = state(
        Fact(id="bal", kind="balance", label="In hand", amount=40_000),
        Fact(id="food", kind="essential", label="Eating out", amount=5_000),
        Fact(id="rent", kind="essential", label="Rent", amount=18_000, day=20),
        Fact(id="pay", kind="income", label="Salary", amount=50_000, day=28),
    )
    plan = build_plan(s, TODAY)
    food = [a for a in plan.actions if a.fact_id == "food"]

    assert len(food) == 1
    assert "across the month" in food[0].label
    assert food[0].amount == 5_000
    # A dated bill still gets its own dated line.
    assert len([a for a in plan.actions if a.fact_id == "rent"]) == 1
    assert "Rent" in next(a for a in plan.actions if a.fact_id == "rent").label


def test_every_action_names_the_fact_it_came_from():
    s = state(
        Fact(id="bal", kind="balance", label="In hand", amount=3_000),
        Fact(id="rent", kind="essential", label="Rent", amount=20_000, day=18),
        Fact(id="trip", kind="optional", label="Trip", amount=6_000, day=16),
        Fact(id="pay", kind="income", label="Salary", amount=30_000, day=28),
    )
    plan = build_plan(s, TODAY)
    for action in plan.actions:
        if action.kind == "shortfall":
            continue
        assert action.fact_id, f"{action.kind} action has no fact to point at"
