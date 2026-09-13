"""The two tools the agent has, and the snapshot the UI renders.

Deliberately two. Every extra tool is another round trip on the critical path
between the user finishing a sentence and hearing a reply, so flexibility lives
in the item schema rather than in more functions.

Two things that are not tools, and why:

- Reading state back. The model needs it on every turn, so it is returned as
  the *result* of every write instead. A `get_state` tool would put a second
  round trip on the latency path to fetch something we already have.
- Anything that draws a card. Cards are derived from state by `snapshot()`, so
  they cannot drift out of step with the conversation — there is nothing for
  the model to forget to update.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date
from typing import Any

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from finance import FactError, FinanceState, fact_from_item
from plan import Plan, build_plan, project

ITEM_PROPERTIES: dict[str, Any] = {
    "id": {
        "type": "string",
        "description": (
            "Short stable snake_case identifier, e.g. 'rent', 'hdfc_card', "
            "'salary'. Re-use the same id to correct or update something "
            "already recorded — that is how corrections work. Re-use it too "
            "when the user names the same thing differently ('electricity' "
            "and 'power bill' are one id)."
        ),
    },
    "kind": {
        "type": "string",
        "enum": ["balance", "income", "essential", "debt", "optional"],
        "description": (
            "balance = money on hand right now. income = money arriving. "
            "essential = must be paid (rent, utilities, groceries). "
            "debt = loan EMIs and credit cards. optional = discretionary "
            "spending that could be cut if the month is tight."
        ),
    },
    "label": {"type": "string", "description": "Short human name, e.g. 'Rent'."},
    "amount": {
        "type": "integer",
        "description": "Exact amount in whole rupees. Omit if the user gave a range.",
    },
    "amount_min": {"type": "integer", "description": "Low end of a range."},
    "amount_max": {"type": "integer", "description": "High end of a range."},
    "day": {
        "type": "integer",
        "description": "Day of month it lands, 1-31. Omit if the user was vague.",
    },
    "day_min": {"type": "integer", "description": "Earliest day, for 'first week'."},
    "day_max": {"type": "integer", "description": "Latest day, for 'first week'."},
    "frequency": {
        "type": "string",
        "enum": ["monthly", "weekly", "quarterly", "one_time"],
        "description": (
            "Defaults to monthly. Use one_time for a single upcoming expense "
            "such as a wedding gift."
        ),
    },
    "minimum_due": {
        "type": "integer",
        "description": (
            "Credit cards only: the minimum payment, when 'amount' is the full "
            "balance. Recording both is what lets the plan offer paying the "
            "minimum as a way out of a tight month."
        ),
    },
    "status": {
        "type": "string",
        "enum": ["due", "already_paid"],
        "description": (
            "Set already_paid when the user says they have already paid it this "
            "month, so it is not counted against them again."
        ),
    },
    "certainty": {
        "type": "string",
        "enum": ["known", "estimated"],
        "description": (
            "Use estimated when the user guessed or rounded ('about', 'roughly', "
            "'I think'). Estimated figures are shown differently so a guess is "
            "never presented as a fact."
        ),
    },
}

UPDATE_FINANCES_DESCRIPTION = (
    "Record or correct what you have learned about the user's money. Call this "
    "as soon as the user gives you a number — every number, including ones they "
    "correct or change. Record several items in one call rather than calling "
    "repeatedly. Never do arithmetic yourself: record what the user said and the "
    "plan will do the maths."
)

UPDATE_FINANCES_PROPERTIES: dict[str, Any] = {
    "items": {
        "type": "array",
        "description": "Facts to record or update.",
        "items": {
            "type": "object",
            "properties": ITEM_PROPERTIES,
            "required": ["id", "kind", "label"],
        },
    },
    "remove": {
        "type": "array",
        "description": "Ids to forget, when the user retracts something.",
        "items": {"type": "string"},
    },
    "user_name": {
        "type": "string",
        "description": (
            "The user's first name, once they have given it. Send it on the "
            "first call after they say it and never again. Carried here rather "
            "than in a tool of its own so introducing yourself costs no extra "
            "round trip."
        ),
    },
}

BUILD_PLAN_DESCRIPTION = (
    "Work out the 30-day plan and show it to the user. Call this once you know "
    "what money is on hand, what is coming in, and what has to go out. It "
    "returns the real numbers — read them out rather than estimating. If "
    "information is still missing it will say so; ask for that first."
)


CHECK_DAY_DESCRIPTION = (
    "Answer a question about one specific date — 'what will I have on the "
    "29th', 'can I afford something on the 5th', 'how much is left by the "
    "20th'. Returns the balance at the end of that day and what moves on it. "
    "Call this whenever the user asks about a particular day. Never try to "
    "work a date out yourself from the plan totals."
)

CHECK_DAY_PROPERTIES: dict[str, Any] = {
    "day": {
        "type": "integer",
        "description": (
            "Day of the month the user asked about, 1-31. The next occurrence "
            "of that day inside the 30-day window is the one that answers."
        ),
    },
}


class FinanceTools:
    """Holds one call's financial state and exposes it as tools.

    One instance per session. The UI is notified through `on_change` after every
    mutation, so the cards and the conversation can never describe different
    numbers.
    """

    def __init__(
        self,
        *,
        on_change: Callable[[dict[str, Any]], Awaitable[None]],
        today: Callable[[], date] = date.today,
    ) -> None:
        self.state = FinanceState()
        self.plan: Plan | None = None
        self.user_name: str | None = None
        self._on_change = on_change
        self._today = today

    async def publish(self) -> None:
        """Push the current state to the client.

        Called once when the call opens so the panel is live and honest from the
        first second — showing an empty month and what is still needed — rather
        than staying blank until the first number happens to be mentioned.
        """
        await self._publish()

    def schemas(self) -> list[FunctionSchema]:
        """Tool schemas with handlers bound, for `LLMContext(tools=...)`."""
        return [
            FunctionSchema(
                name="update_finances",
                description=UPDATE_FINANCES_DESCRIPTION,
                properties=UPDATE_FINANCES_PROPERTIES,
                required=[],
                handler=self._handle_update,
            ),
            FunctionSchema(
                name="build_plan",
                description=BUILD_PLAN_DESCRIPTION,
                properties={},
                required=[],
                handler=self._handle_build_plan,
            ),
            # A third tool, against the two-tool rule at the top of this file,
            # and worth the exception. Observed without it: asked "what will be
            # my balance on 29th?", the model answered "I don't have a specific
            # figure for the 29th — that would need to come from the plan tool"
            # — no answer, and the tooling leaked into the call. The day-by-day
            # numbers already exist in the timeline; nothing could reach them.
            FunctionSchema(
                name="check_day",
                description=CHECK_DAY_DESCRIPTION,
                properties=CHECK_DAY_PROPERTIES,
                required=["day"],
                handler=self._handle_check_day,
            ),
        ]

    def _timeline(self) -> Plan | None:
        """The best day-by-day picture available right now.

        The finished plan if there is one, otherwise the live projection, so a
        date question can be answered mid-conversation rather than only after
        the user has asked for a plan.
        """
        if self.plan is not None:
            return self.plan
        if not self.state.of_kind("balance"):
            return None
        return project(self.state, self._today())

    async def _handle_check_day(self, params: FunctionCallParams) -> None:
        raw = params.arguments.get("day")
        try:
            day = int(raw)
        except (TypeError, ValueError):
            day = 0

        if not 1 <= day <= 31:
            await params.result_callback(
                {
                    "ready": False,
                    "instruction": (
                        "That is not a day of the month. Ask which date they "
                        "mean."
                    ),
                }
            )
            return

        plan = self._timeline()
        if plan is None:
            await params.result_callback(
                {
                    "ready": False,
                    "still_missing": self.state.missing(),
                    "instruction": (
                        "You cannot answer a date question until you know what "
                        "they have on hand. Ask for that first, naturally, "
                        "without mentioning why."
                    ),
                }
            )
            return

        cell = next((c for c in plan.timeline if c.day.day == day), None)
        if cell is None:
            last = plan.timeline[-1].day if plan.timeline else self._today()
            await params.result_callback(
                {
                    "ready": False,
                    "window_ends": last.strftime("%-d %B"),
                    "instruction": (
                        "That date falls outside the 30 days this covers. Say "
                        "plainly how far ahead you can see, and offer the "
                        "nearest date you do have."
                    ),
                }
            )
            return

        lowest = min(plan.timeline, key=lambda c: c.closing_balance)
        result: dict[str, Any] = {
            "ready": True,
            "date": cell.day.strftime("%-d %B"),
            "balance_at_the_end_of_that_day": cell.closing_balance,
            "money_in_that_day": cell.total_in,
            "money_out_that_day": cell.total_out,
            "what_moves_that_day": [
                {"what": m.label, "amount": m.amount, "direction": "in" if m in cell.inflows else "out"}
                for m in cell.inflows + cell.outflows
            ],
            "is_the_tightest_day": cell.day == lowest.day,
            "say_no_number_that_is_not_in_this_result": True,
        }
        result["instruction"] = (
            "Read out balance_at_the_end_of_that_day and name what moves that "
            "day. Do not add or subtract anything yourself — every figure you "
            "say must be one of the values above."
        )
        logger.info(
            "check_day day={} date={} balance={}",
            day,
            cell.day.isoformat(),
            cell.closing_balance,
        )
        await params.result_callback(result)

    async def _handle_update(self, params: FunctionCallParams) -> None:
        items = params.arguments.get("items") or []
        removals = params.arguments.get("remove") or []
        name = params.arguments.get("user_name")

        recorded: list[str] = []
        problems: list[str] = []

        if isinstance(name, str) and name.strip():
            # Only the first word: models tend to send back the whole utterance
            # ("Priya, and I work in Pune"), and the panel wants a name, not a
            # sentence.
            cleaned = name.strip().split()[0][:40]
            if cleaned != self.user_name:
                self.user_name = cleaned
                self.state.touch()

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                fact = fact_from_item(item)
            except FactError as exc:
                # Returned to the model rather than raised: a mis-heard number
                # is something to ask about, not a dead call.
                problems.append(str(exc))
                continue
            except TypeError as exc:
                problems.append(f"could not record {item.get('label', 'that')}: {exc}")
                continue
            self.state.upsert(fact)
            recorded.append(fact.id)

        for fact_id in removals:
            if self.state.remove(str(fact_id)):
                recorded.append(f"-{fact_id}")

        if self.plan is not None and (recorded or removals):
            # Numbers changed, so the plan on screen is stale. Recompute rather
            # than leave the user looking at a plan built from old figures.
            self.plan = build_plan(self.state, self._today())

        logger.info(
            "update_finances recorded={} removed={} problems={}",
            recorded,
            list(removals),
            problems,
        )
        await self._publish()

        result: dict[str, Any] = {
            "recorded": recorded,
            "current_state": self.state.summary_for_llm(),
            "still_missing": self.state.missing(),
            "would_sharpen_the_plan": self.state.would_sharpen(),
        }
        if problems:
            result["could_not_record"] = problems
            # Observed: told only that something was wrong, the model explained
            # the failure to the user out loud ("the system needs me to classify
            # it") and then never retried, silently losing the figure. So the
            # instruction says exactly what to do and that the user must not
            # hear about it.
            result["instruction"] = (
                "Each message above says what was wrong and what the allowed "
                "values are. Call update_finances again immediately with those "
                "items fixed. Do not mention this to the user and do not "
                "apologise — just carry on. Only if the problem is a value you "
                "misheard should you ask the user, and then ask naturally, as "
                "though confirming."
            )
        if self.state.conflicts:
            result["needs_confirming"] = [
                f"{c.label}: was ₹{c.previous:,}, now ₹{c.current:,}"
                for c in self.state.conflicts
            ]
        await params.result_callback(result)

    async def _handle_build_plan(self, params: FunctionCallParams) -> None:
        missing = self.state.missing()
        if missing:
            # Refusing here rather than planning around holes: a plan built on
            # absent figures looks authoritative and is not.
            await params.result_callback(
                {
                    "ready": False,
                    "still_missing": missing,
                    "instruction": (
                        "Not enough information for a plan yet. Ask about the "
                        "first missing item, one question at a time."
                    ),
                }
            )
            return

        self.plan = build_plan(self.state, self._today())
        logger.info(
            "build_plan solvable={} shortfall={} cuts={}",
            self.plan.solvable,
            self.plan.shortfall,
            [m.fact_id for m in self.plan.cut],
        )
        await self._publish()
        await params.result_callback(spoken_plan(self.plan))

    async def _publish(self) -> None:
        # The projection is recomputed on every mutation so the calendar tracks
        # the conversation live; `self.plan` only appears once the user has
        # actually asked for a plan.
        #
        # Gated on a known balance, not on any fact at all. Without it the
        # opening balance is zero, and the very first expense the user mentions
        # would draw a calendar deep in the red — implying they have nothing,
        # which we have not been told.
        forecast = (
            project(self.state, self._today())
            if self.state.of_kind("balance")
            else None
        )
        await self._on_change(
            snapshot(self.state, self.plan, forecast, name=self.user_name)
        )


def spoken_plan(plan: Plan) -> dict[str, Any]:
    """The plan as the model should say it.

    Every figure is precomputed so the model reads rather than calculates, and
    the wording is steered away from the two failure modes that matter: claiming
    a tight month is fine, and dressing up an unsolvable one.
    """
    closing = plan.timeline[-1].closing_balance if plan.timeline else plan.opening_balance
    lowest = min(plan.timeline, key=lambda c: c.closing_balance) if plan.timeline else None
    result: dict[str, Any] = {
        "ready": True,
        "money_on_hand": plan.opening_balance,
        "coming_in": plan.total_in,
        "going_out": plan.total_out,
        "left_at_the_end": closing,
        "lowest_balance": plan.min_balance,
        "lowest_balance_day": lowest.day.strftime("%-d %B") if lowest else None,
        "solvable": plan.solvable,
        # Every number the model might reach for is here, precomputed. Observed
        # without this: it added the figures up itself, out loud, and got a
        # number that was wrong by ₹15,600.
        "say_no_number_that_is_not_in_this_result": True,
    }
    if plan.cut:
        result["you_would_need_to_hold_off_on"] = [
            {"what": m.label, "amount": m.amount} for m in plan.cut
        ]
    minimums = [a for a in plan.actions if a.kind == "pay_minimum"]
    if minimums:
        result["pay_only_the_minimum_on"] = [a.label for a in minimums]

    if plan.solvable:
        result["summary"] = (
            f"The month works out. The tightest point leaves ₹{plan.min_balance:,}."
        )
        result["instruction"] = (
            "Tell them it works, name the tightest point using lowest_balance "
            "and lowest_balance_day, and name anything they need to hold off "
            "on. Do not add up or subtract anything yourself — every figure you "
            "say must be one of the values above, read as it is. Then check "
            "they have followed it, and ask if anything looks wrong."
        )
    else:
        result["short_by"] = plan.shortfall
        result["tightest_day"] = plan.crunch_day.isoformat() if plan.crunch_day else None
        result["summary"] = (
            f"Even after every change available, the month is ₹{plan.shortfall:,} "
            f"short around {plan.crunch_day:%-d %B}." if plan.crunch_day else ""
        )
        result["instruction"] = (
            "Say plainly that this does not balance and name the gap. Do not "
            "suggest a loan, do not promise any lender will agree to anything, "
            "and do not imply the gap can be closed with what they have. It is "
            "fine to say the shortfall needs money from outside this plan, or a "
            "payment moved by agreement with whoever is owed."
        )
    return result


def snapshot(
    state: FinanceState,
    plan: Plan | None,
    projection: Plan | None = None,
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Everything the UI draws, as one versioned message.

    The client renders this and computes nothing. A second implementation of the
    maths in the browser could disagree with the tested one, and then the claim
    that the calculations are testable stops being true.

    `projection` is the month as it stands and updates on every turn; `plan` is
    the finished plan and stays null until the user asks for one. Keeping them
    apart is what stops the screen showing cuts the agent has not proposed.
    """
    return {
        "type": "finance_state",
        "version": state.version,
        "name": name,
        "facts": [asdict(f) for f in state.facts.values()],
        "totals": state.kind_totals(),
        "conflicts": [asdict(c) for c in state.conflicts],
        "missing": state.missing(),
        "would_sharpen": state.would_sharpen(),
        "projection": _plan_payload(projection) if projection else None,
        "plan": _plan_payload(plan) if plan else None,
    }


def _plan_payload(plan: Plan) -> dict[str, Any]:
    return {
        "start": plan.start.isoformat(),
        "opening_balance": plan.opening_balance,
        "total_in": plan.total_in,
        "total_out": plan.total_out,
        "net": plan.net,
        "min_balance": plan.min_balance,
        "crunch_day": plan.crunch_day.isoformat() if plan.crunch_day else None,
        "shortfall": plan.shortfall,
        "solvable": plan.solvable,
        "cut": [asdict(m) for m in plan.cut],
        "actions": [asdict(a) for a in plan.actions],
        "timeline": [
            {
                "day": cell.day.isoformat(),
                "index": cell.index,
                "in": cell.total_in,
                "out": cell.total_out,
                "balance": cell.closing_balance,
                "movements": [asdict(m) for m in cell.inflows + cell.outflows],
            }
            for cell in plan.timeline
        ],
    }
