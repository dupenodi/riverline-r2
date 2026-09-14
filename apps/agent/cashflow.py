"""30-day cash-flow projection. Pure: caller passes `today`."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal, Sequence

WINDOW_DAYS = 30

Kind = Literal["income", "need", "debt", "flex", "owed"]
Cadence = Literal["monthly", "weekly", "daily", "once"]
Status = Literal["due", "paid", "unknown"]
INFLOW_KINDS = ("income", "owed")


@dataclass(frozen=True)
class Entry:
    id: str
    kind: Kind
    label: str
    amount: int | None = None
    amount_min: int | None = None
    amount_max: int | None = None
    day: int | None = None
    day_min: int | None = None
    day_max: int | None = None
    cadence: Cadence = "monthly"
    status: Status = "unknown"
    min_due: int | None = None
    on_date: str | None = None


def is_inflow(entry: Entry) -> bool:
    return entry.kind in INFLOW_KINDS


@dataclass(frozen=True)
class Movement:
    entry_id: str
    label: str
    amount: int
    kind: Kind


@dataclass
class Day:
    date: date
    inflows: list[Movement]
    outflows: list[Movement]
    closing: int
    trough: int


@dataclass(frozen=True)
class Crunch:
    date: date
    amount: int


@dataclass(frozen=True)
class IssueSpan:
    start: date
    end: date
    low: int
    low_date: date


@dataclass(frozen=True)
class Projection:
    days: list[Day]
    crunch: Crunch
    finish: int


def norm_label(label: str) -> str:
    return " ".join(label.lower().split())


def is_card(entry: Entry) -> bool:
    return "card" in entry.label.lower()


def planning_amount(entry: Entry) -> int | None:
    # A stated range is the fact. A point amount beside it is leftover extraction.
    if entry.amount_min is not None and entry.amount_max is not None:
        return entry.amount_min if is_inflow(entry) else entry.amount_max
    if entry.amount is not None:
        return entry.amount
    if is_inflow(entry):
        for value in (entry.amount_min, entry.amount_max):
            if value is not None:
                return value
        return None
    for value in (entry.amount_max, entry.amount_min):
        if value is not None:
            return value
    return None


def planning_day(entry: Entry) -> int | None:
    if entry.on_date:
        try:
            return date.fromisoformat(entry.on_date).day
        except ValueError:
            pass
    if entry.day is not None:
        return entry.day
    if is_inflow(entry):
        for value in (entry.day_max, entry.day_min):
            if value is not None:
                return value
        return None
    for value in (entry.day_min, entry.day_max):
        if value is not None:
            return value
    return None


def when_key(entry: Entry) -> str | None:
    """When this fact hits. None means 'not specified' (a patch can fill it)."""
    if entry.on_date:
        return entry.on_date
    if entry.cadence == "daily":
        return "daily"
    if entry.cadence == "weekly":
        return "weekly"
    if entry.day is not None:
        return f"{entry.cadence}:{entry.day}"
    return None


def same_item(existing: Entry, incoming: Entry) -> bool:
    """Same kind+label is one fact unless the dates clearly differ."""
    if existing.id == incoming.id:
        return True
    if existing.kind != incoming.kind:
        return False
    if norm_label(existing.label) != norm_label(incoming.label):
        return False
    a, b = when_key(existing), when_key(incoming)
    if a is not None and b is not None and a != b:
        return False
    return True


def window_end(today: date) -> date:
    return today + timedelta(days=WINDOW_DAYS - 1)


def missing(cash: int | None, entries: Sequence[Entry], today: date | None = None) -> list[str]:
    gaps: list[str] = []
    if cash is None:
        gaps.append("available")
    for entry in entries:
        if entry.status == "paid":
            continue
        if entry.kind in ("income", "owed", "need", "debt"):
            needs_day = entry.cadence not in ("daily", "weekly")
            if planning_amount(entry) is None or (
                needs_day and planning_day(entry) is None
            ):
                gaps.append(entry.label)
                continue
            day_n = planning_day(entry)
            if (
                today is not None
                and day_n is not None
                and entry.cadence == "monthly"
                and entry.status == "unknown"
                and _clamp_day(today.year, today.month, day_n) < today
            ):
                gaps.append(entry.label)
                continue
    return gaps


def upsert(entries: Sequence[Entry], incoming: Entry) -> list[Entry]:
    current = list(entries)
    for i, entry in enumerate(current):
        if entry.id == incoming.id:
            current[i] = incoming
            return current
    for i, entry in enumerate(current):
        if same_item(entry, incoming):
            current[i] = replace(incoming, id=entry.id)
            return current
    current.append(incoming)
    return current


def project(today: date, cash: int, entries: Sequence[Entry]) -> Projection:
    end = window_end(today)
    days = [
        Day(
            date=today + timedelta(days=i),
            inflows=[],
            outflows=[],
            closing=0,
            trough=0,
        )
        for i in range(WINDOW_DAYS)
    ]
    by_date = {day.date: day for day in days}

    for entry in entries:
        amount = planning_amount(entry)
        if amount is None:
            continue
        move = Movement(entry.id, entry.label, amount, entry.kind)
        for when in _occurrence_dates(today, end, entry):
            cell = by_date.get(when)
            if cell is None:
                continue
            if is_inflow(entry):
                cell.inflows.append(move)
            else:
                cell.outflows.append(move)

    balance = cash
    crunch_amt = cash
    crunch_date = today
    for cell in days:
        trough = balance
        for move in cell.outflows:
            balance -= move.amount
            trough = min(trough, balance)
        for move in cell.inflows:
            balance += move.amount
            trough = min(trough, balance)
        cell.trough = trough
        cell.closing = balance
        if trough < crunch_amt:
            crunch_amt = trough
            crunch_date = cell.date

    return Projection(
        days=days,
        crunch=Crunch(crunch_date, crunch_amt),
        finish=days[-1].closing,
    )


def issue_spans(proj: Projection) -> list[IssueSpan]:
    spans: list[IssueSpan] = []
    start: date | None = None
    end: date | None = None
    low = 0
    low_date: date | None = None
    for day in proj.days:
        if day.closing < 0:
            if start is None:
                start = end = low_date = day.date
                low = day.closing
            else:
                end = day.date
                if day.closing < low:
                    low = day.closing
                    low_date = day.date
            continue
        if start is not None and end is not None and low_date is not None:
            spans.append(IssueSpan(start, end, low, low_date))
            start = end = low_date = None
    if start is not None and end is not None and low_date is not None:
        spans.append(IssueSpan(start, end, low, low_date))
    return spans


def with_amount(entry: Entry, amount: int) -> Entry:
    return replace(entry, amount=amount, amount_min=None, amount_max=None)


def _clamp_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _monthly_dates(today: date, end: date, day_n: int) -> list[date]:
    dates: list[date] = []
    year, month = today.year, today.month
    for _ in range(4):
        candidate = _clamp_day(year, month, day_n)
        if today <= candidate <= end:
            dates.append(candidate)
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        if date(year, month, 1) > end:
            break
    return dates


def resolve_on_date(today: date, in_days: int) -> date:
    return today + timedelta(days=in_days)


def _occurrence_dates(today: date, end: date, entry: Entry) -> list[date]:
    if entry.on_date:
        try:
            when = date.fromisoformat(entry.on_date)
        except ValueError:
            when = None
        if when is not None:
            if entry.status == "paid":
                return []
            if today <= when <= end:
                return [when]
            if when < today and entry.status == "due":
                return [today]
            return []

    if entry.cadence in ("daily", "weekly"):
        if entry.status == "paid":
            return []
        step = 1 if entry.cadence == "daily" else 7
        hits: list[date] = []
        cursor = today
        while cursor <= end:
            hits.append(cursor)
            cursor += timedelta(days=step)
        return hits

    day_n = planning_day(entry)
    if day_n is None:
        return []
    this_cycle = _clamp_day(today.year, today.month, day_n)
    upcoming = _monthly_dates(today, end, day_n)

    if entry.cadence == "once":
        if entry.status == "paid":
            return []
        if this_cycle < today and entry.status == "due":
            return [today]
        return upcoming[:1]

    dates = list(upcoming)
    if entry.status == "paid":
        return [d for d in dates if d != this_cycle]
    if this_cycle < today and entry.status == "due":
        return [today] + [d for d in dates if d != today]
    return dates
