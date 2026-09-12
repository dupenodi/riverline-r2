"""Financial facts collected during a conversation.

The LLM never does arithmetic. It extracts facts from what the user says and
records them here; `plan.py` turns them into numbers. That split is what makes
the calculations testable, and it means the model has no arithmetic to invent.

Money is integer rupees throughout. No floats — rounding drift in a shortfall
calculation would be invisible and wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["balance", "income", "essential", "debt", "optional"]
Frequency = Literal["monthly", "weekly", "quarterly", "one_time"]
Certainty = Literal["known", "estimated"]
Status = Literal["due", "already_paid"]

# A `Literal` annotation is not enforced at runtime, so these are checked by
# hand. It matters: a model that answers kind="one_time" (a real observed case,
# confusing the field with `frequency`) would otherwise be accepted silently and
# then quietly fail to match anywhere the kind is tested — including the check
# that decides what can be cut when money is short.
ENUMS: dict[str, tuple[str, ...]] = {
    "kind": ("balance", "income", "essential", "debt", "optional"),
    "frequency": ("monthly", "weekly", "quarterly", "one_time"),
    "certainty": ("known", "estimated"),
    "status": ("due", "already_paid"),
}

# Sanity bounds. A number outside these is a mishearing ("five rupees rent") or
# a units slip, not a real figure — the agent is told to re-ask rather than the
# planner quietly producing a nonsense plan.
MAX_AMOUNT = 100_000_000  # ₹10 crore
# Zero is a real answer — "I have nothing until Friday" is the situation this
# is for. Negative is not: money owed is a debt fact, not a negative balance.
MIN_AMOUNT = 0


class FactError(ValueError):
    """A fact the agent should re-ask about rather than record."""


@dataclass(frozen=True)
class Fact:
    """One thing we know about the user's money.

    Amounts and days can each be a point value or a range. A range is not
    vagueness to be averaged away — it is resolved pessimistically at planning
    time, so an uncertain month is never presented as more comfortable than it
    might be. See `planning_amount` and `planning_day`.
    """

    id: str
    kind: Kind
    label: str
    amount: int | None = None
    amount_min: int | None = None
    amount_max: int | None = None
    day: int | None = None
    day_min: int | None = None
    day_max: int | None = None
    frequency: Frequency = "monthly"
    minimum_due: int | None = None
    status: Status = "due"
    certainty: Certainty = "known"

    def __post_init__(self) -> None:
        for name, allowed in ENUMS.items():
            value = getattr(self, name)
            if value not in allowed:
                raise FactError(
                    f"{self.label}: {name}={value!r} is not one of "
                    + ", ".join(allowed)
                )
        for name in ("amount", "amount_min", "amount_max", "minimum_due"):
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise FactError(f"{self.label}: {name} must be whole rupees")
            if not MIN_AMOUNT <= value <= MAX_AMOUNT:
                raise FactError(
                    f"{self.label}: {value} is outside the range this can plan with"
                )
        for name in ("day", "day_min", "day_max"):
            value = getattr(self, name)
            if value is not None and not 1 <= value <= 31:
                raise FactError(f"{self.label}: day {value} is not a day of the month")
        if (
            self.amount_min is not None
            and self.amount_max is not None
            and self.amount_min > self.amount_max
        ):
            raise FactError(f"{self.label}: amount range is inverted")
        if (
            self.day_min is not None
            and self.day_max is not None
            and self.day_min > self.day_max
        ):
            raise FactError(f"{self.label}: day range is inverted")
        if self.minimum_due is not None:
            known = self.planning_amount(pessimistic_high=True)
            if known is not None and self.minimum_due > known:
                raise FactError(
                    f"{self.label}: minimum due is larger than the full amount"
                )

    @property
    def is_income(self) -> bool:
        return self.kind == "income"

    @property
    def has_amount(self) -> bool:
        return (
            self.amount is not None
            or self.amount_min is not None
            or self.amount_max is not None
        )

    @property
    def has_day(self) -> bool:
        return self.day is not None or self.day_min is not None or self.day_max is not None

    def planning_amount(self, *, pessimistic_high: bool | None = None) -> int | None:
        """The figure to plan against.

        Ranges resolve against the user's interest, never toward the middle:
        money coming in is assumed to be the low end, money going out the high
        end. Averaging a range would produce a plan that is right on paper and
        breaks in the third week.
        """
        if self.amount is not None:
            return self.amount
        if pessimistic_high is None:
            pessimistic_high = not self.is_income
        candidates = [v for v in (self.amount_min, self.amount_max) if v is not None]
        if not candidates:
            return None
        return max(candidates) if pessimistic_high else min(candidates)

    def planning_day(self) -> int | None:
        """The day to plan against — again the least comfortable end.

        Income is assumed to arrive at the late end of its range and bills to
        fall due at the early end, because the gap between those two is exactly
        where a month goes wrong.
        """
        if self.day is not None:
            return self.day
        candidates = [v for v in (self.day_min, self.day_max) if v is not None]
        if not candidates:
            return None
        return max(candidates) if self.is_income else min(candidates)


@dataclass
class Conflict:
    """A known figure the user restated as something materially different.

    Recorded rather than blocked. The newer value wins — a correction is far
    more common than a contradiction — but the change stays visible so the
    agent can confirm which one the user meant, and the card can show both.
    """

    fact_id: str
    label: str
    previous: int
    current: int


# Below this, a restatement is a rounding of the same number rather than a
# different answer, and asking the user to confirm it would be noise.
CONFLICT_TOLERANCE = 0.05


@dataclass
class FinanceState:
    """Every fact gathered so far, keyed by a stable agent-chosen id."""

    facts: dict[str, Fact] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    version: int = 0

    def upsert(self, fact: Fact) -> None:
        """Record a fact, flagging a material change to a known amount."""
        existing = self.facts.get(fact.id)
        if existing is not None:
            self._note_conflict(existing, fact)
        self.facts[fact.id] = fact
        self.version += 1

    def remove(self, fact_id: str) -> bool:
        """Drop a fact the user retracted."""
        if self.facts.pop(fact_id, None) is None:
            return False
        self.conflicts = [c for c in self.conflicts if c.fact_id != fact_id]
        self.version += 1
        return True

    def resolve_conflict(self, fact_id: str) -> None:
        self.conflicts = [c for c in self.conflicts if c.fact_id != fact_id]

    def _note_conflict(self, existing: Fact, incoming: Fact) -> None:
        if existing.certainty != "known" or incoming.certainty != "known":
            return
        before = existing.planning_amount()
        after = incoming.planning_amount()
        if before is None or after is None or before == after:
            return
        if abs(after - before) <= max(1, int(before * CONFLICT_TOLERANCE)):
            return
        self.resolve_conflict(incoming.id)
        self.conflicts.append(
            Conflict(
                fact_id=incoming.id,
                label=incoming.label,
                previous=before,
                current=after,
            )
        )

    def of_kind(self, *kinds: Kind) -> list[Fact]:
        return [f for f in self.facts.values() if f.kind in kinds]

    @property
    def opening_balance(self) -> int:
        """Money in hand today. Absent means zero, and shows up as missing info."""
        return sum(
            f.planning_amount(pessimistic_high=False) or 0
            for f in self.of_kind("balance")
        )

    def missing(self) -> list[str]:
        """What genuinely blocks a plan.

        Deliberately narrow. An earlier version also demanded a due date for
        every expense, which deadlocked the conversation: a user who says "I
        spend about five thousand eating out" has given a completely plannable
        figure, and the agent sat there refusing to plan and asking which day
        they eat out. Undated spending is spread across the window instead —
        see `plan._occurrences` — and the date is asked for as a refinement,
        not a precondition.
        """
        gaps: list[str] = []
        if not self.of_kind("balance"):
            gaps.append("How much money you have on hand right now")
        if not self.of_kind("income"):
            gaps.append("What money is coming in, and when")
        if not self.of_kind("essential"):
            gaps.append("Your essential monthly expenses")
        for fact in self.facts.values():
            if fact.kind != "balance" and not fact.has_amount:
                gaps.append(f"How much {fact.label} is")
        return gaps

    def would_sharpen(self) -> list[str]:
        """Details that improve the plan but must never hold it up.

        A due date decides whether money lands before or after a bill, which is
        the whole game — but an approximate plan now beats an exact plan the
        user gave up waiting for.
        """
        return [
            f"When {fact.label} is due"
            for fact in self.facts.values()
            if fact.kind in ("debt", "essential")
            and not fact.has_day
            and fact.frequency not in ("weekly", "one_time")
        ]

    def summary_for_llm(self) -> str:
        """Current state, injected into the context after every change.

        Cheaper than a read-back tool: the model needs this on every turn, and a
        tool call would put a second round trip on the latency path to fetch
        something we already have.
        """
        if not self.facts:
            return "Nothing recorded yet."
        lines: list[str] = []
        for fact in sorted(self.facts.values(), key=lambda f: (f.kind, f.id)):
            bits = [f"[{fact.id}] {fact.label}: {_describe_amount(fact)}"]
            if fact.has_day:
                bits.append(_describe_day(fact))
            if fact.frequency != "monthly":
                bits.append(fact.frequency.replace("_", "-"))
            if fact.minimum_due is not None:
                bits.append(f"minimum ₹{fact.minimum_due:,}")
            if fact.status == "already_paid":
                bits.append("already paid this month")
            if fact.certainty == "estimated":
                bits.append("estimated")
            lines.append(f"- {fact.kind}: " + ", ".join(bits))
        if self.conflicts:
            lines.append("UNCONFIRMED CHANGES — ask which is right:")
            for c in self.conflicts:
                lines.append(f"- {c.label}: was ₹{c.previous:,}, now ₹{c.current:,}")
        return "\n".join(lines)


def _describe_amount(fact: Fact) -> str:
    if fact.amount is not None:
        return f"₹{fact.amount:,}"
    if fact.amount_min is not None and fact.amount_max is not None:
        return f"₹{fact.amount_min:,}-₹{fact.amount_max:,}"
    if fact.amount_max is not None:
        return f"up to ₹{fact.amount_max:,}"
    if fact.amount_min is not None:
        return f"at least ₹{fact.amount_min:,}"
    return "amount unknown"


def _describe_day(fact: Fact) -> str:
    if fact.day is not None:
        return f"day {fact.day}"
    if fact.day_min is not None and fact.day_max is not None:
        return f"day {fact.day_min}-{fact.day_max}"
    return f"day {fact.day_min or fact.day_max}"


def fact_from_item(item: dict) -> Fact:
    """Build a Fact from one tool-call item.

    Unknown keys are dropped rather than rejected: a model that invents a field
    name has still usually understood the number, and failing the call would
    cost the user a whole turn over spelling.
    """
    allowed = set(Fact.__dataclass_fields__)
    cleaned = {k: v for k, v in item.items() if k in allowed}
    for required in ("id", "kind", "label"):
        if not cleaned.get(required):
            raise FactError(f"missing {required}")
    return Fact(**cleaned)
