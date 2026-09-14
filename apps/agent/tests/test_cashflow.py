"""30-day projector and plan — integer rupees, frozen `today`."""

from __future__ import annotations

from datetime import date, timedelta

from cashflow import (
    WINDOW_DAYS,
    Entry,
    issue_spans,
    missing,
    planning_amount,
    planning_day,
    project,
    upsert,
)
from plan import build_plan

TODAY = date(2026, 9, 1)


def _e(id: str, kind: str, label: str, **kwargs) -> Entry:
    return Entry(id=id, kind=kind, label=label, **kwargs)  # type: ignore[arg-type]


def test_salary_before_rent_survives_same_totals_as_rent_before_salary() -> None:
    cash = 5_000
    salary = _e("s", "income", "Salary", amount=50_000, day=10)
    rent_ok = _e("r", "need", "Rent", amount=15_000, day=20)
    ok = project(TODAY, cash, [salary, rent_ok])
    assert ok.crunch.amount == 5_000
    assert ok.finish == 40_000

    rent_early = _e("r", "need", "Rent", amount=15_000, day=3)
    salary_late = _e("s", "income", "Salary", amount=50_000, day=28)
    crisis = project(TODAY, cash, [salary_late, rent_early])
    assert crisis.finish == 40_000
    assert crisis.crunch.amount == -10_000
    assert crisis.crunch.date == date(2026, 9, 3)


def test_monthly_near_month_end_lands_twice() -> None:
    today = date(2026, 2, 1)
    rent = _e("r", "need", "Rent", amount=10_000, day=1)
    proj = project(today, 50_000, [rent])
    hits = [
        day.date
        for day in proj.days
        if any(m.label == "Rent" for m in day.outflows)
    ]
    assert hits == [date(2026, 2, 1), date(2026, 3, 1)]
    assert proj.finish == 30_000


def test_cash_is_opening_not_todays_inflow() -> None:
    proj = project(TODAY, 10_000, [])
    assert len(proj.days) == WINDOW_DAYS
    assert all(day.inflows == [] and day.outflows == [] for day in proj.days)
    assert all(day.closing == 10_000 for day in proj.days)
    assert proj.crunch.amount == 10_000
    assert proj.finish == 10_000


def test_paid_entry_is_skipped() -> None:
    rent = _e("r", "need", "Rent", amount=20_000, day=5, status="paid")
    proj = project(TODAY, 0, [rent])
    assert proj.finish == 0
    assert all(day.outflows == [] for day in proj.days)


def test_weekly_hits_about_four_times() -> None:
    groceries = _e(
        "g", "need", "Groceries", amount=2_000, day=15, cadence="weekly"
    )
    today = date(2026, 9, 14)
    proj = project(today, 20_000, [groceries])
    hits = sum(1 for day in proj.days if day.outflows)
    assert 4 <= hits <= 5
    assert proj.finish == 20_000 - 2_000 * hits


def test_range_income_low_late_bill_high_early() -> None:
    income = _e(
        "i",
        "income",
        "Freelance",
        amount_min=40_000,
        amount_max=50_000,
        day_min=20,
        day_max=25,
    )
    bill = _e(
        "b",
        "need",
        "Rent",
        amount_min=18_000,
        amount_max=22_000,
        day_min=3,
        day_max=7,
    )
    assert planning_amount(income) == 40_000
    assert planning_day(income) == 25
    assert planning_amount(bill) == 22_000
    assert planning_day(bill) == 3
    proj = project(TODAY, 0, [income, bill])
    assert proj.crunch.date == date(2026, 9, 3)
    assert proj.crunch.amount == -22_000
    assert proj.finish == 18_000


def test_same_day_outflows_before_inflows() -> None:
    salary = _e("s", "income", "Salary", amount=50_000, day=10)
    rent = _e("r", "need", "Rent", amount=20_000, day=10)
    proj = project(TODAY, 0, [salary, rent])
    day = next(d for d in proj.days if d.date.day == 10)
    assert day.closing == 30_000
    assert day.trough == -20_000
    assert proj.crunch.amount == -20_000
    assert proj.crunch.date == date(2026, 9, 10)


def test_cut_flex_before_crunch_clears_shortfall() -> None:
    rent = _e("r", "need", "Rent", amount=10_000, day=10)
    dinner = _e("d", "flex", "Dinner", amount=8_000, day=5)
    plan = build_plan(TODAY, 12_000, [rent, dinner])
    assert plan.solvable is True
    assert plan.steps[0].action == "delay"
    assert plan.steps[0].label == "Dinner"
    assert plan.gap is None
    after = project(TODAY, 12_000, [rent])
    assert after.crunch.amount >= 0


def test_card_drops_to_minimum() -> None:
    card = _e(
        "c",
        "debt",
        "HDFC card",
        amount=20_000,
        day=5,
        min_due=2_000,
    )
    plan = build_plan(TODAY, 3_000, [card])
    assert plan.solvable is True
    assert any(s.action == "pay_minimum" and s.amount == 2_000 for s in plan.steps)
    full = project(TODAY, 3_000, [card])
    assert full.crunch.amount < 0


def test_unsolvable_reports_gap_and_date() -> None:
    rent = _e("r", "need", "Rent", amount=20_000, day=5)
    plan = build_plan(TODAY, 1_000, [rent])
    assert plan.solvable is False
    assert plan.gap == 19_000
    assert plan.gap_date == date(2026, 9, 5)
    assert plan.steps[-1].action == "short"


def test_restatement_overwrites_same_label() -> None:
    first = _e("a", "need", "Rent", amount=20_000, day=5)
    second = _e("b", "need", "rent", amount=24_000, day=5)
    entries = upsert([first], second)
    assert len(entries) == 1
    assert entries[0].id == "a"
    assert entries[0].amount == 24_000


def test_upsert_by_id_updates_amount_and_timeline() -> None:
    rent = _e("r", "need", "Rent", amount=20_000, day=5)
    before = project(TODAY, 50_000, [rent])
    updated = _e("r", "need", "Rent", amount=24_000, day=5)
    entries = upsert([rent], updated)
    assert entries[0].amount == 24_000
    after = project(TODAY, 50_000, entries)
    assert after.finish == before.finish - 4_000


def test_missing_available_and_undated_need() -> None:
    rent = _e("r", "need", "Rent", amount=20_000)
    card = _e("c", "debt", "Credit card", amount=10_000, day=8)
    assert missing(None, [rent, card]) == ["available", "Rent"]


def _hits(proj, label: str) -> list[date]:
    dates: list[date] = []
    for day in proj.days:
        if any(m.label == label for m in day.inflows + day.outflows):
            dates.append(day.date)
    return dates


def test_mid_month_unknown_does_not_guess_this_cycle() -> None:
    today = date(2026, 9, 13)
    rent = _e("r", "need", "Rent", amount=10_000, day=5)
    proj = project(today, 50_000, [rent])
    assert _hits(proj, "Rent") == [date(2026, 10, 5)]
    assert "Rent" in missing(50_000, [rent], today)


def test_mid_month_unpaid_lands_today_and_next_month() -> None:
    today = date(2026, 9, 13)
    rent = _e("r", "need", "Rent", amount=10_000, day=5, status="due")
    proj = project(today, 50_000, [rent])
    assert _hits(proj, "Rent") == [date(2026, 9, 13), date(2026, 10, 5)]
    assert proj.finish == 30_000


def test_mid_month_paid_skips_this_cycle_keeps_next() -> None:
    today = date(2026, 9, 13)
    rent = _e("r", "need", "Rent", amount=10_000, day=5, status="paid")
    proj = project(today, 50_000, [rent])
    assert _hits(proj, "Rent") == [date(2026, 10, 5)]
    assert proj.finish == 40_000


def test_once_next_month_is_not_this_cycle() -> None:
    today = date(2026, 9, 14)
    rent = _e("r", "need", "Rent", amount=15_000, day=3, cadence="once")
    proj = project(today, 12_000, [rent])
    assert _hits(proj, "Rent") == [date(2026, 10, 3)]
    assert "Rent" not in missing(12_000, [rent], today)


def test_end_of_month_window_includes_next_month_fifth() -> None:
    today = date(2026, 9, 25)
    salary = _e("s", "income", "Salary", amount=50_000, day=28)
    rent = _e("r", "need", "Rent", amount=15_000, day=5, status="paid")
    proj = project(today, 8_000, [salary, rent])
    assert date(2026, 9, 28) in _hits(proj, "Salary")
    assert date(2026, 10, 5) in _hits(proj, "Rent")
    assert date(2026, 9, 5) not in _hits(proj, "Rent")


def test_daily_hits_every_window_day_without_dom() -> None:
    today = date(2026, 9, 14)
    food = _e("z", "need", "Zomato", amount=600, cadence="daily")
    proj = project(today, 20_000, [food])
    assert _hits(proj, "Zomato") == [today + timedelta(days=i) for i in range(WINDOW_DAYS)]
    assert proj.finish == 20_000 - 600 * WINDOW_DAYS
    assert missing(20_000, [food], today) == []


def test_uncut_crunch_is_worst_close_plan_gap_is_after_flex_cut() -> None:
    today = date(2026, 9, 14)
    entries = [
        _e("e", "need", "EMI", amount=5_000, day=15, status="due"),
        _e("m", "flex", "mother", amount=10_000, day=16, status="due"),
        _e("b", "need", "electricity bill", amount=6_000, day=17, status="due"),
        _e("f", "income", "furniture sale", amount=10_000, day=20, cadence="once"),
        _e("c", "debt", "credit card", amount=5_962, day=21, status="due"),
        _e("a", "need", "Airtel postpaid", amount=530, day=22, status="due"),
        _e("p", "income", "freelance project", amount=25_000, day=23, cadence="once"),
        _e("d", "flex", "dinner", amount=4_000, day=27, cadence="once"),
        _e("t", "flex", "porter", amount=6_000, day=29, cadence="once"),
        _e("z", "need", "Zomato", amount=600, day=1, cadence="once"),
    ]
    proj = project(today, 10_000, entries)
    assert proj.crunch.date == date(2026, 9, 17)
    assert proj.crunch.amount == -11_000
    assert proj.finish == 6_908
    spans = issue_spans(proj)
    assert len(spans) == 1
    assert spans[0].start == date(2026, 9, 16)
    assert spans[0].end == date(2026, 9, 22)
    assert spans[0].low == -11_000
    assert spans[0].low_date == date(2026, 9, 17)
    plan = build_plan(today, 10_000, entries)
    assert plan.steps[0].action == "delay"
    assert plan.steps[0].label == "mother"
    assert plan.gap == 1_000
    assert plan.gap_date == date(2026, 9, 17)


def test_in_days_lands_on_today_plus_offset_not_today() -> None:
    today = date(2026, 9, 14)
    bill = _e(
        "a",
        "need",
        "Airtel",
        amount=700,
        cadence="once",
        on_date="2026-09-19",
        day=19,
    )
    proj = project(today, 15_000, [bill])
    assert _hits(proj, "Airtel") == [date(2026, 9, 19)]


def test_owed_is_inflow() -> None:
    today = date(2026, 9, 14)
    friend = _e(
        "k",
        "owed",
        "Karthik",
        amount=5_000,
        cadence="once",
        on_date="2026-09-24",
        day=24,
    )
    proj = project(today, 10_000, [friend])
    day = next(d for d in proj.days if d.date == date(2026, 9, 24))
    assert day.inflows[0].label == "Karthik"
    assert day.outflows == []
    assert proj.finish == 15_000


def test_two_once_same_label_different_days_stay_two() -> None:
    a = _e("a", "income", "Freelance", amount=25_000, day=18, cadence="once")
    b = _e("b", "income", "Freelance", amount=25_000, day=2, cadence="once")
    entries = upsert([a], b)
    assert [e.day for e in entries] == [18, 2]


def test_range_beats_point_amount_for_a_bill() -> None:
    bill = _e(
        "e",
        "need",
        "Electricity",
        amount=5_000,
        amount_min=5_000,
        amount_max=6_000,
        day=17,
    )
    assert planning_amount(bill) == 6_000
