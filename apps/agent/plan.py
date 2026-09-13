"""The 30-day cash-flow planner.

Pure functions over `FinanceState`. No LLM, no I/O, no clock of its own — the
caller passes `today` in — so every number here is reproducible and testable.

The core idea is that a month does not go wrong because the totals are wrong.
It goes wrong because of *order*: a salary on the 28th against rent due on the
3rd is a crisis, and the same two numbers in the other order are fine. So the
planner walks day by day and tracks a running balance, rather than netting
monthly totals — which is the calculation that would hide the problem.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from finance import Fact, FinanceState

WINDOW_DAYS = 30

# What gets protected when there is not enough to go around. Missing a secured
# EMI has consequences a skipped subscription does not, so the order is not
# arbitrary — it is the order in which real damage happens.
KIND_PRIORITY: dict[str, int] = {"debt": 0, "essential": 1, "optional": 2}

ActionKind = Literal["pay", "cut_optional", "pay_minimum", "shortfall"]


@dataclass(frozen=True)
class Movement:
    """One sum of money entering or leaving on one day."""

    fact_id: str
    label: str
    amount: int
    kind: str
    certainty: str


@dataclass
class DayCell:
    """One day of the window — what the calendar renders."""

    day: date
    index: int
    inflows: list[Movement] = field(default_factory=list)
    outflows: list[Movement] = field(default_factory=list)
    closing_balance: int = 0

    @property
    def total_in(self) -> int:
        return sum(m.amount for m in self.inflows)

    @property
    def total_out(self) -> int:
        return sum(m.amount for m in self.outflows)


@dataclass(frozen=True)
class Action:
    """Something the user can actually do.

    There is deliberately no action for borrowing. The assignment forbids
    recommending another loan, and leaving it out of the vocabulary means the
    planner cannot emit one even if a future prompt change invites it — a
    constraint in code rather than a line in a prompt the model may drift from.
    """

    kind: ActionKind
    label: str
    detail: str
    amount: int = 0
    # Lets the UI mark the matching row in the ledger. Without it the card has
    # only a sentence to match on, and "Pay the minimum on HDFC card" is not an
    # identifier.
    fact_id: str = ""


@dataclass
class Plan:
    """The full picture, and the only thing the UI renders."""

    start: date
    timeline: list[DayCell]
    opening_balance: int
    total_in: int
    total_out: int
    net: int
    min_balance: int
    crunch_day: date | None
    shortfall: int
    solvable: bool
    actions: list[Action] = field(default_factory=list)
    cut: list[Movement] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unfunded: int = 0

    @property
    def has_shortfall(self) -> bool:
        return self.shortfall > 0


def _days_in_month(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


def _occurrences(fact: Fact, start: date, days: int) -> list[date]:
    """The dates this fact lands on inside the window.

    Note the window is 30 days from today, not a calendar month, so it usually
    straddles two months and a monthly bill can legitimately occur twice.
    """
    if fact.status == "already_paid":
        return []
    window = [start + timedelta(days=i) for i in range(days)]
    target = fact.planning_day()

    if fact.frequency == "weekly":
        # No anchor day given: start from today, which is the only defensible
        # guess and errs toward counting a full four or five occurrences.
        first = next((d for d in window if target is None or d.day == target), window[0])
        return [d for d in window if (d - first).days % 7 == 0 and d >= first]

    if target is None:
        # No date given. Rather than refuse to plan — or invent a day and move
        # the crunch point to somewhere the user never said — the amount is
        # spread evenly across the window. That is also the honest shape of the
        # spending this usually is: "about five thousand eating out" does not
        # happen on one afternoon.
        return window if fact.frequency == "monthly" else []

    if fact.frequency == "one_time":
        return [d for d in window if d.day == target][:1]

    if fact.frequency == "quarterly":
        # Without a month anchor the safest reading is that it falls once in
        # this window if its day does — planning for it and not needing it is
        # recoverable; the reverse is not.
        return [d for d in window if d.day == target][:1]

    # Monthly. A bill set for the 31st still has to come out of a 30-day month,
    # so it clamps to the last day rather than silently vanishing.
    hits = []
    for d in window:
        effective = min(target, _days_in_month(d))
        if d.day == effective:
            hits.append(d)
    return hits


def _movement(fact: Fact, amount: int) -> Movement:
    return Movement(
        fact_id=fact.id,
        label=fact.label,
        amount=amount,
        kind=fact.kind,
        certainty=fact.certainty,
    )


def _build_timeline(
    state: FinanceState,
    start: date,
    *,
    skip: set[str],
    minimum_only: set[str],
) -> list[DayCell]:
    """Lay every movement onto the 30 days and carry the balance forward."""
    cells = [DayCell(day=start + timedelta(days=i), index=i) for i in range(WINDOW_DAYS)]
    by_date = {c.day: c for c in cells}

    for fact in state.facts.values():
        if fact.kind == "balance" or fact.id in skip:
            continue
        amount = fact.planning_amount()
        if amount is None:
            continue
        if fact.id in minimum_only and fact.minimum_due is not None:
            amount = fact.minimum_due

        days = _occurrences(fact, start, WINDOW_DAYS)
        if not days:
            continue

        # A spread fact was given as a monthly total, so it has to be divided
        # across the window rather than charged in full every day. Integer
        # rupees, with the remainder on day one, so the parts still sum to the
        # figure the user actually said.
        spread = len(days) == WINDOW_DAYS and not fact.has_day
        per_day = amount // WINDOW_DAYS if spread else amount
        remainder = amount - per_day * WINDOW_DAYS if spread else 0

        for position, when in enumerate(days):
            cell = by_date[when]
            value = per_day + (remainder if position == 0 else 0)
            if value == 0:
                continue
            if fact.is_income:
                cell.inflows.append(_movement(fact, value))
            else:
                cell.outflows.append(_movement(fact, value))

    balance = state.opening_balance
    for cell in cells:
        balance += cell.total_in - cell.total_out
        cell.closing_balance = balance
    return cells


def _lowest(cells: list[DayCell]) -> tuple[int, date]:
    worst = min(cells, key=lambda c: c.closing_balance)
    return worst.closing_balance, worst.day


def _relief_candidates(
    state: FinanceState, cells: list[DayCell], crunch: date
) -> list[Movement]:
    """Optional spend that happens early enough to help.

    Cutting something that falls after the crunch day frees no money before the
    balance goes negative, so it is not relief — it just looks like it on a
    monthly total. Largest first, to need the fewest cuts.
    """
    seen: dict[str, Movement] = {}
    for cell in cells:
        if cell.day > crunch:
            break
        for movement in cell.outflows:
            if movement.kind == "optional" and movement.fact_id not in seen:
                seen[movement.fact_id] = movement
    return sorted(seen.values(), key=lambda m: m.amount, reverse=True)


def _minimum_due_candidates(
    state: FinanceState, cells: list[DayCell], crunch: date, used: set[str]
) -> list[Fact]:
    """Debts carrying a minimum payment, usable before the crunch.

    Paying a card minimum is a real lever a person actually has. It is offered
    only after optional spend is gone, because it costs interest.
    """
    due_before = {
        m.fact_id for cell in cells if cell.day <= crunch for m in cell.outflows
    }
    return sorted(
        (
            f
            for f in state.of_kind("debt")
            if f.minimum_due is not None
            and f.id in due_before
            and f.id not in used
            and (f.planning_amount() or 0) > f.minimum_due
        ),
        key=lambda f: (f.planning_amount() or 0) - (f.minimum_due or 0),
        reverse=True,
    )


def _restore_unneeded(
    state: FinanceState,
    today: date,
    applied: list[tuple[str, str]],
    skip: set[str],
    minimum_only: set[str],
    cut: list[Movement],
) -> tuple[list[DayCell], int, date]:
    """Give back every change that turned out not to be needed.

    The solving loop is greedy and never revisits an earlier decision, so it can
    cut a subscription and then pull a much larger lever that would have been
    enough on its own. Left alone it tells someone to cancel dinner for nothing.

    So each change is offered back, most recent first, and kept only if the
    month stops balancing without it. What survives is a minimal set: every
    remaining sacrifice is one the plan genuinely depends on.
    """
    for kind, fact_id in reversed(applied):
        if kind == "cut":
            trial_skip, trial_minimum = skip - {fact_id}, set(minimum_only)
        else:
            trial_skip, trial_minimum = set(skip), minimum_only - {fact_id}
        trial = _build_timeline(
            state, today, skip=trial_skip, minimum_only=trial_minimum
        )
        if _lowest(trial)[0] >= 0:
            # Mutate in place: the caller still holds these and builds the
            # action list from them.
            skip.clear()
            skip.update(trial_skip)
            minimum_only.clear()
            minimum_only.update(trial_minimum)

    cut[:] = [m for m in cut if m.fact_id in skip]
    cells = _build_timeline(state, today, skip=skip, minimum_only=minimum_only)
    low, crunch = _lowest(cells)
    return cells, low, crunch


def build_plan(state: FinanceState, today: date) -> Plan:
    """Produce the 30-day plan.

    Resolution order when money is short: cut optional spend first, then drop
    credit-card payments to their minimum. If both are exhausted and the month
    still does not balance, say so — an unsolvable month is a real answer, and
    dressing it up as a solved one would be the most damaging thing here.
    """
    cells = _build_timeline(state, today, skip=set(), minimum_only=set())
    min_balance, crunch = _lowest(cells)

    cut: list[Movement] = []
    minimum_only: set[str] = set()
    skip: set[str] = set()
    applied: list[tuple[str, str]] = []

    while min_balance < 0:
        candidates = _relief_candidates(state, cells, crunch)
        pick = next((m for m in candidates if m.fact_id not in skip), None)
        if pick is not None:
            skip.add(pick.fact_id)
            cut.append(pick)
            applied.append(("cut", pick.fact_id))
        else:
            debts = _minimum_due_candidates(state, cells, crunch, minimum_only)
            if not debts:
                break
            minimum_only.add(debts[0].id)
            applied.append(("minimum", debts[0].id))
        cells = _build_timeline(state, today, skip=skip, minimum_only=minimum_only)
        min_balance, crunch = _lowest(cells)

    if min_balance >= 0:
        cells, min_balance, crunch = _restore_unneeded(
            state, today, applied, skip, minimum_only, cut
        )

    total_in = sum(c.total_in for c in cells)
    total_out = sum(c.total_out for c in cells)
    solvable = min_balance >= 0
    shortfall = 0 if solvable else -min_balance

    return Plan(
        start=today,
        timeline=cells,
        opening_balance=state.opening_balance,
        total_in=total_in,
        total_out=total_out,
        net=total_in - total_out,
        min_balance=min_balance,
        crunch_day=None if solvable else crunch,
        shortfall=shortfall,
        solvable=solvable,
        actions=_actions(state, cells, cut, minimum_only, shortfall, crunch),
        cut=cut,
        missing=state.missing(),
        unfunded=shortfall,
    )


def _outflow_days(cells: list[DayCell]) -> dict[str, int]:
    """How many days of the window each outgoing fact lands on."""
    counts: dict[str, int] = {}
    for cell in cells:
        for movement in cell.outflows:
            counts[movement.fact_id] = counts.get(movement.fact_id, 0) + 1
    return counts


def _actions(
    state: FinanceState,
    cells: list[DayCell],
    cut: list[Movement],
    minimum_only: set[str],
    shortfall: int,
    crunch: date,
) -> list[Action]:
    """Turn the solved timeline into things a person can do, in order."""
    actions: list[Action] = []

    for movement in cut:
        actions.append(
            Action(
                kind="cut_optional",
                label=f"Hold off on {movement.label}",
                detail=f"Frees ₹{movement.amount:,} before the tight point",
                amount=movement.amount,
                fact_id=movement.fact_id,
            )
        )

    for fact_id in minimum_only:
        fact = state.facts[fact_id]
        full = fact.planning_amount() or 0
        minimum = fact.minimum_due or 0
        actions.append(
            Action(
                kind="pay_minimum",
                label=f"Pay the minimum on {fact.label}",
                detail=(
                    f"₹{minimum:,} instead of ₹{full:,} this month. "
                    "Interest will build on the rest."
                ),
                amount=full - minimum,
                fact_id=fact_id,
            )
        )

    # Everything still being paid, in the order it falls due, so the plan reads
    # as a sequence of days rather than a pile of numbers.
    #
    # Spending the user never dated is spread over every day of the window (see
    # `_occurrences`), which would otherwise become thirty near-identical lines
    # of ₹166. Those collapse into one, because "₹5,000 across the month" is
    # what the user actually said.
    spread: dict[str, int] = {}
    for fact_id, count in _outflow_days(cells).items():
        if count >= WINDOW_DAYS:
            spread[fact_id] = 0

    for cell in cells:
        for movement in sorted(
            cell.outflows, key=lambda m: KIND_PRIORITY.get(m.kind, 9)
        ):
            if movement.fact_id in spread:
                spread[movement.fact_id] += movement.amount
                continue
            actions.append(
                Action(
                    kind="pay",
                    label=f"{cell.day.strftime('%-d %b')} — {movement.label}",
                    # No detail: the amount travels in its own field, and
                    # repeating it here printed every figure on screen twice.
                    detail="",
                    amount=movement.amount,
                    fact_id=movement.fact_id,
                )
            )

    for fact_id, total in spread.items():
        fact = state.facts.get(fact_id)
        if fact is None or total <= 0:
            continue
        actions.append(
            Action(
                kind="pay",
                label=f"{fact.label} — across the month",
                detail=f"₹{total:,} in total, spread over the 30 days",
                amount=total,
                fact_id=fact_id,
            )
        )

    if shortfall > 0:
        actions.insert(
            0,
            Action(
                kind="shortfall",
                label="This does not balance",
                detail=(
                    f"Even after every change above, you are ₹{shortfall:,} short "
                    f"around {crunch.strftime('%-d %b')}. That gap needs money "
                    "from somewhere outside this plan, or a payment moved with "
                    "the lender's agreement."
                ),
                amount=shortfall,
            ),
        )

    return actions


def project(state: FinanceState, today: date) -> Plan:
    """The month exactly as it stands, with nothing changed.

    This is what the calendar draws *while the conversation is still going*, so
    the user watches the shape of their month appear as they talk rather than
    waiting for a final plan. It deliberately applies no cuts and no minimums:
    a forecast is not advice, and showing relief the user has not agreed to
    would make the calendar disagree with what the agent is saying.
    """
    cells = _build_timeline(state, today, skip=set(), minimum_only=set())
    min_balance, crunch = _lowest(cells)
    total_in = sum(c.total_in for c in cells)
    total_out = sum(c.total_out for c in cells)
    solvable = min_balance >= 0
    shortfall = 0 if solvable else -min_balance
    return Plan(
        start=today,
        timeline=cells,
        opening_balance=state.opening_balance,
        total_in=total_in,
        total_out=total_out,
        net=total_in - total_out,
        min_balance=min_balance,
        crunch_day=None if solvable else crunch,
        shortfall=shortfall,
        solvable=solvable,
        actions=[],
        cut=[],
        missing=state.missing(),
        unfunded=shortfall,
    )
