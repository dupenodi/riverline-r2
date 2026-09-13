"""Regenerate the card fixtures the web preview page renders.

    uv run python scripts/make_fixtures.py

The cards are a pure function of one snapshot, so they can be built and
eyeballed against recorded planner output instead of a forty-second phone call.
The output is real: it comes from the same `build_plan` the agent calls, so a
card that looks wrong here is wrong on a call too.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance import Fact, FinanceState
from plan import build_plan, project
from tools import snapshot

TODAY = date(2026, 9, 13)
OUT = Path(__file__).resolve().parents[2] / "web/src/lib/fixtures/snapshots.json"


def state(*facts: Fact) -> FinanceState:
    s = FinanceState()
    for fact in facts:
        s.upsert(fact)
    return s


def tight_but_solvable() -> FinanceState:
    """Salary lands after the rent — the case monthly totals get wrong.

    Also carries one of everything the schema has to survive: a range, an
    estimate, a weekly cadence, undated spending, a credit-card minimum, a
    one-off, and a figure the user restated.
    """
    s = state(
        Fact(id="cash", kind="balance", label="Money in hand", amount=35_000),
        Fact(id="salary", kind="income", label="Salary", amount=58_000, day=1),
        Fact(id="freelance", kind="income", label="Freelance invoice",
             amount=15_000, day_min=20, day_max=25, certainty="estimated"),
        Fact(id="rent", kind="essential", label="Rent", amount=22_000, day=20),
        Fact(id="power", kind="essential", label="Electricity", amount=2_400,
             day=24, certainty="estimated"),
        Fact(id="groceries", kind="essential", label="Groceries", amount=2_200,
             frequency="weekly"),
        Fact(id="food", kind="essential", label="Eating out", amount=5_000),
        Fact(id="car", kind="debt", label="Car EMI", amount=12_000, day=5),
        Fact(id="hdfc", kind="debt", label="HDFC credit card", amount=18_000,
             day=28, minimum_due=1_800),
        Fact(id="trip", kind="optional", label="Goa trip", amount=9_000, day=18),
        Fact(id="streaming", kind="optional", label="Streaming", amount=800, day=12),
        Fact(id="gift", kind="optional", label="Wedding gift", amount=6_000,
             day=22, frequency="one_time"),
    )
    # "Actually rent went up" — a correction, which leaves a conflict to confirm.
    s.upsert(Fact(id="rent", kind="essential", label="Rent", amount=24_000, day=20))
    return s


def mid_conversation() -> FinanceState:
    """Three facts in. Enough to draw the month, nowhere near a plan."""
    return state(
        Fact(id="cash", kind="balance", label="Money in hand", amount=12_400),
        Fact(id="rent", kind="essential", label="Rent", amount=24_000, day=20),
        Fact(id="car", kind="debt", label="Car EMI", amount=12_000, day=5),
    )


def does_not_balance() -> FinanceState:
    """No optional spend to cut and no card to drop to a minimum.

    The planner has nothing left to try, which is the answer — the one case
    where dressing the month up would do real damage.
    """
    return state(
        Fact(id="cash", kind="balance", label="Money in hand", amount=1_200),
        Fact(id="salary", kind="income", label="Salary", amount=28_000, day=1),
        Fact(id="rent", kind="essential", label="Rent", amount=26_000, day=18),
        Fact(id="loan", kind="debt", label="Personal loan EMI", amount=9_500, day=15),
        Fact(id="food", kind="essential", label="Groceries", amount=6_000),
    )


def main() -> None:
    fixtures = {
        "early": snapshot(
            mid_conversation(), None, project(mid_conversation(), TODAY)
        ),
        "tight": snapshot(
            tight_but_solvable(),
            build_plan(tight_but_solvable(), TODAY),
            project(tight_but_solvable(), TODAY),
        ),
        "unsolvable": snapshot(
            does_not_balance(),
            build_plan(does_not_balance(), TODAY),
            project(does_not_balance(), TODAY),
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n")

    for name, snap in fixtures.items():
        shown = snap["plan"] or snap["projection"]
        print(
            f"{name:12} solvable={shown['solvable']!s:5} "
            f"low={shown['min_balance']:>8,} cut={[m['label'] for m in shown['cut']]}"
        )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
