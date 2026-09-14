"""30-day advice from a projection. Numbers stay in the engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Sequence

from cashflow import (
    WINDOW_DAYS,
    Entry,
    Projection,
    is_card,
    planning_amount,
    project,
    with_amount,
)

Action = Literal["delay", "reduce", "collect", "pay_minimum", "cover", "short"]


@dataclass(frozen=True)
class PlanStep:
    action: Action
    label: str
    amount: int
    crunch_before: int
    crunch_after: int
    date: date | None = None
    until: date | None = None
    note: str | None = None


@dataclass(frozen=True)
class Plan:
    solvable: bool
    steps: list[PlanStep]
    gap: int | None
    gap_date: date | None


def build_plan(today: date, cash: int, entries: Sequence[Entry]) -> Plan:
    proj = project(today, cash, entries)
    advice = _advice(today, cash, entries, proj)
    if proj.crunch.amount >= 0:
        return Plan(True, advice, None, None)

    working = list(entries)
    for flex in _flex_before_crunch(working, proj):
        working = [e for e in working if e.id != flex.id]
        proj = project(today, cash, working)
        if proj.crunch.amount >= 0:
            return Plan(True, advice, None, None)

    for card in _cards_with_min(working):
        full = planning_amount(card)
        if full is None or card.min_due is None or card.min_due >= full:
            continue
        before = proj.crunch.amount
        working = [with_amount(e, e.min_due) if e.id == card.id else e for e in working]
        proj = project(today, cash, working)
        advice.append(
            PlanStep(
                "pay_minimum",
                card.label,
                card.min_due,
                before,
                proj.crunch.amount,
                note=(
                    f"Pay {card.label} minimum {card.min_due} instead of {full}."
                ),
            )
        )
        if proj.crunch.amount >= 0:
            return Plan(True, advice, None, None)

    gap = max(0, -proj.crunch.amount)
    advice.append(
        PlanStep(
            "short",
            "shortfall",
            gap,
            proj.crunch.amount,
            proj.crunch.amount,
            date=proj.crunch.date,
            note=f"Still short {gap} on {proj.crunch.date.isoformat()}.",
        )
    )
    return Plan(False, advice, gap, proj.crunch.date)


def _advice(
    today: date,
    cash: int,
    entries: Sequence[Entry],
    proj: Projection,
) -> list[PlanStep]:
    crunch = proj.crunch
    if crunch.amount >= 0:
        return [
            PlanStep(
                "cover",
                "lowest",
                crunch.amount,
                crunch.amount,
                crunch.amount,
                date=crunch.date,
                note=(
                    f"Lowest {crunch.amount} on {crunch.date.isoformat()}, "
                    "stays above zero."
                ),
            )
        ]

    steps: list[PlanStep] = []
    inflows = [
        (day.date, move)
        for day in proj.days
        for move in day.inflows
    ]
    first_inflow = min(inflows, key=lambda row: row[0]) if inflows else None

    for flex in _flex_before_crunch(entries, proj)[:3]:
        amount = planning_amount(flex) or 0
        hit = _first_hit(proj, flex.id)
        until = None
        note = f"{flex.label} {amount}"
        if hit:
            note += f" on {hit.isoformat()}"
        if first_inflow and (hit is None or first_inflow[0] > hit):
            until = first_inflow[0]
            note += (
                f", before {first_inflow[1].label} "
                f"{first_inflow[1].amount} on {until.isoformat()}"
            )
        steps.append(
            PlanStep(
                "delay",
                flex.label,
                amount,
                crunch.amount,
                crunch.amount,
                date=hit,
                until=until,
                note=note,
            )
        )

    for entry in entries:
        if entry.cadence != "daily":
            continue
        amount = planning_amount(entry)
        if not amount:
            continue
        total = amount * WINDOW_DAYS
        if total < max(cash // 5, 1):
            continue
        steps.append(
            PlanStep(
                "reduce",
                entry.label,
                amount,
                crunch.amount,
                crunch.amount,
                note=f"{entry.label} {amount} a day is {total} over 30 days.",
            )
        )

    seen: set[str] = set()
    for when, move in inflows:
        if when < crunch.date:
            continue
        if move.entry_id in seen:
            continue
        seen.add(move.entry_id)
        if len(seen) > 2:
            break
        relation = "on" if when == crunch.date else "after"
        steps.append(
            PlanStep(
                "collect",
                move.label,
                move.amount,
                crunch.amount,
                crunch.amount,
                date=when,
                note=(
                    f"{move.label} {move.amount} on {when.isoformat()} "
                    f"is {relation} the low."
                ),
            )
        )

    return steps[:5]


def _first_hit(proj: Projection, entry_id: str) -> date | None:
    for day in proj.days:
        if any(m.entry_id == entry_id for m in (*day.outflows, *day.inflows)):
            return day.date
    return None


def _flex_before_crunch(entries: Sequence[Entry], proj: Projection) -> list[Entry]:
    crunch_date = proj.crunch.date
    eligible: list[Entry] = []
    for entry in entries:
        if entry.kind != "flex":
            continue
        amount = planning_amount(entry)
        if not amount:
            continue
        if any(
            any(m.entry_id == entry.id for m in day.outflows)
            and day.date <= crunch_date
            for day in proj.days
        ):
            eligible.append(entry)
    eligible.sort(key=lambda e: planning_amount(e) or 0, reverse=True)
    return eligible


def _cards_with_min(entries: Sequence[Entry]) -> list[Entry]:
    cards = [e for e in entries if is_card(e) and e.min_due is not None]
    cards.sort(
        key=lambda e: (planning_amount(e) or 0) - (e.min_due or 0),
        reverse=True,
    )
    return cards
