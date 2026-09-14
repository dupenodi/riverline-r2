"""Session finance tools: extract facts, engine computes, snapshot published."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date
from typing import Any

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from advise import advice_payload, draft_points, picture, rewrite_points
from cashflow import (
    WINDOW_DAYS,
    Entry,
    Movement,
    Projection,
    issue_spans,
    missing as missing_fields,
    norm_label,
    planning_amount,
    planning_day,
    project,
    resolve_on_date,
    same_item,
    upsert,
)
from plan import Plan, build_plan

KINDS = ("income", "need", "debt", "flex", "owed")
CADENCES = ("monthly", "weekly", "daily", "once")
STATUSES = ("due", "paid", "unknown")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


class MoneyTools:
    def __init__(
        self,
        *,
        on_change: Callable[[dict[str, Any]], Awaitable[None]],
        persist_add: Callable[..., Awaitable[None]] | None = None,
        persist_remove: Callable[..., Awaitable[None]] | None = None,
        persist_name: Callable[..., Awaitable[None]] | None = None,
        persist_cash: Callable[..., Awaitable[None]] | None = None,
        persist_advice: Callable[..., Awaitable[None]] | None = None,
        session_id: str | None = None,
        today: date | None = None,
    ) -> None:
        self.entries: list[Entry] = []
        self.cash: int | None = None
        self.user_name: str | None = None
        self.version = 0
        self.today = today or date.today()
        self._conflicts: list[str] = []
        self._on_change = on_change
        self._persist_add = persist_add
        self._persist_remove = persist_remove
        self._persist_name = persist_name
        self._persist_cash = persist_cash
        self._persist_advice = persist_advice
        self._session_id = session_id
        self._advice_points: list[str] | None = None

    async def publish(self) -> None:
        await self._on_change(self.snapshot())

    def schemas(self) -> list[FunctionSchema]:
        item = {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Existing id to correct; omit to add.",
                },
                "kind": {
                    "type": "string",
                    "enum": list(KINDS),
                    "description": (
                        "Required to add. income or owed (money coming in, "
                        "including a friend paying them back), need, debt "
                        "(they must pay), or flex."
                    ),
                },
                "label": {
                    "type": "string",
                    "description": "Required to add. Short name.",
                },
                "amount": {"type": "integer", "description": "Rupees. Omit if a range."},
                "amount_min": {"type": "integer"},
                "amount_max": {"type": "integer"},
                "day": {"type": "integer", "description": "Day of month 1–31."},
                "in_days": {
                    "type": "integer",
                    "description": (
                        "Days from today. tomorrow=1, in 5 days=5. "
                        "Engine sets the date. Prefer this over day for "
                        "relative timing."
                    ),
                },
                "day_min": {"type": "integer"},
                "day_max": {"type": "integer"},
                "cadence": {
                    "type": "string",
                    "enum": list(CADENCES),
                    "description": "monthly, weekly, daily, or once. Daily needs amount, not a day.",
                },
                "status": {
                    "type": "string",
                    "enum": list(STATUSES),
                    "description": "paid = already gone this cycle; due = still owed; omit if unsure.",
                },
                "min_due": {
                    "type": "integer",
                    "description": "Credit card minimum due.",
                },
            },
        }
        return [
            FunctionSchema(
                name="record",
                description=(
                    "Save name, money they can spend today, and money items. "
                    "Batch several items in one call. Two amounts on two "
                    "dates are two items. Reuse id to patch; omit fields "
                    "you are not changing."
                ),
                properties={
                    "name": {"type": "string", "description": "First name, once."},
                    "cash": {
                        "type": "integer",
                        "description": (
                            "Rupees they can spend today: bank plus cash plus "
                            "wallet, combined."
                        ),
                    },
                    "items": {
                        "type": "array",
                        "description": "New or corrected entries.",
                        "items": item,
                    },
                },
                required=[],
                handler=self._handle_record,
            ),
            FunctionSchema(
                name="forget",
                description="Drop entries the user retracts.",
                properties={
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ids from record.",
                    },
                },
                required=["ids"],
                handler=self._handle_forget,
            ),
            FunctionSchema(
                name="recap",
                description=(
                    "Call once after they confirm they want the 30-day picture. "
                    "Returns headline, upcoming, advice, and payoff to speak. "
                    "Do not call while still collecting facts."
                ),
                properties={},
                required=[],
                handler=self._handle_recap,
            ),
        ]

    def snapshot(self) -> dict[str, Any]:
        gaps = missing_fields(self.cash, self.entries, self.today)
        derived = None
        plan = None
        speak: dict[str, Any] = {
            "cash": self.cash,
            "missing": gaps,
            "conflicts": list(self._conflicts),
        }
        if self.cash is not None:
            proj = project(self.today, self.cash, self.entries)
            built = build_plan(self.today, self.cash, self.entries)
            upcoming = _upcoming_from(proj)
            derived = derived_from_projection(proj)
            plan = _plan_payload(built)
            advice = advice_payload(
                self.today,
                self.cash,
                self.entries,
                proj,
                [] if self._advice_points is None else self._advice_points,
            )
            speak.update(
                {
                    "finish": proj.finish,
                    "crunch": proj.crunch.amount,
                    "crunch_date": proj.crunch.date.isoformat(),
                    "headline": {
                        "cash": self.cash,
                        "finish": proj.finish,
                        "lowest": proj.crunch.amount,
                        "lowest_date": proj.crunch.date.isoformat(),
                    },
                    "advice": {
                        "points": advice["points"],
                        "payoff": advice["payoff"],
                    },
                    "issues": [
                        {
                            "start": span.start.isoformat(),
                            "end": span.end.isoformat(),
                            "low": span.low,
                            "low_date": span.low_date.isoformat(),
                        }
                        for span in issue_spans(proj)
                    ],
                    "upcoming": upcoming,
                }
            )
        return {
            "type": "finance",
            "version": self.version,
            "name": self.user_name,
            "cash": self.cash,
            "entries": [asdict(e) for e in self.entries],
            "conflicts": list(self._conflicts),
            "missing": gaps,
            "derived": derived,
            "plan": plan,
            "advice": speak.get("advice"),
            "items": calendar_items(self.entries),
            "speak": speak,
        }

    async def _handle_record(self, params: FunctionCallParams) -> None:
        recorded: list[str] = []
        problems: list[str] = []
        args = params.arguments or {}

        name = args.get("name")
        if isinstance(name, str) and name.strip():
            cleaned = name.strip().split()[0][:40]
            if cleaned != self.user_name:
                self.user_name = cleaned
                self.version += 1
                if self._persist_name and self._session_id:
                    await self._persist_name(
                        session_id=self._session_id, name=cleaned
                    )

        if "cash" in args and args["cash"] is not None:
            try:
                cash_i = int(args["cash"])
            except (TypeError, ValueError):
                problems.append("cash must be whole rupees")
            else:
                if cash_i < 0:
                    problems.append("cash cannot be negative")
                elif cash_i != self.cash:
                    self.cash = cash_i
                    self.version += 1
                    if self._persist_cash and self._session_id:
                        await self._persist_cash(
                            session_id=self._session_id, cash=cash_i
                        )

        for raw in args.get("items") or []:
            if not isinstance(raw, dict):
                continue
            existing = _find_existing(self.entries, raw, self.today)
            raw_id = raw.get("id")
            by_id = (
                existing is not None
                and isinstance(raw_id, str)
                and raw_id.strip() == existing.id
            )
            if existing is not None:
                parsed, error = _overlay(existing, raw, self.today)
            else:
                parsed, error = _parse_entry(raw, self.today)
            if error or parsed is None:
                problems.append(error or "bad item")
                continue
            if (
                existing is not None
                and not by_id
                and existing.status == "due"
                and parsed.status == "due"
                and existing.amount is not None
                and parsed.amount is not None
                and parsed.amount != existing.amount
                and _same_when(existing, parsed)
            ):
                line = f"{existing.label}: {existing.amount} then {parsed.amount}"
                self._conflicts = _prune_conflicts(self._conflicts, existing.label)
                self._conflicts.append(line)
                continue
            if by_id:
                self._conflicts = _prune_conflicts(self._conflicts, parsed.label)
            self.entries = upsert(self.entries, parsed)
            kept = next(e for e in self.entries if e.id == parsed.id)
            recorded.append(kept.id)
            self.version += 1
            if self._persist_add and self._session_id:
                await self._persist_add(
                    session_id=self._session_id, item=_row(kept)
                )

        logger.info(
            "record args={} recorded={} cash={} entries={} problems={}",
            args,
            recorded,
            self.cash,
            [asdict(e) for e in self.entries],
            problems,
        )
        self._advice_points = None
        snap = self.snapshot()
        await self._on_change(snap)
        await self._persist_advice_now(snap)
        result = _llm_result(snap, recorded=recorded)
        if problems:
            result["instruction"] = (
                "Fix and call record again. Do not mention this to the user. "
                + " ".join(problems)
            )
        await params.result_callback(result)

    async def _handle_forget(self, params: FunctionCallParams) -> None:
        ids = {str(i) for i in (params.arguments.get("ids") or [])}
        removed: list[str] = []
        keep: list[Entry] = []
        for entry in self.entries:
            if entry.id in ids:
                removed.append(entry.id)
                self._conflicts = _prune_conflicts(self._conflicts, entry.label)
                self.version += 1
                if self._persist_remove and self._session_id:
                    await self._persist_remove(
                        session_id=self._session_id, item_id=entry.id
                    )
            else:
                keep.append(entry)
        self.entries = keep
        logger.info("forget removed={}", removed)
        self._advice_points = None
        snap = self.snapshot()
        await self._on_change(snap)
        await self._persist_advice_now(snap)
        await params.result_callback(_llm_result(snap, removed=removed))

    async def _handle_recap(self, params: FunctionCallParams) -> None:
        if self.cash is None:
            await params.result_callback(
                _llm_result(self.snapshot(), instruction="Need cash first.")
            )
            return
        proj = project(self.today, self.cash, self.entries)
        brief = picture(self.today, self.cash, self.entries, proj)
        written = await rewrite_points(brief)
        self._advice_points = list(written or draft_points(brief))
        self.version += 1
        snap = self.snapshot()
        await self._on_change(snap)
        await self._persist_advice_now(snap)
        await params.result_callback(_llm_result(snap))

    async def _persist_advice_now(self, snap: dict[str, Any]) -> None:
        if not self._persist_advice or not self._session_id:
            return
        advice = snap.get("advice")
        if not advice:
            return
        await self._persist_advice(session_id=self._session_id, advice=advice)


def _upcoming_from(proj: Projection) -> list[dict[str, Any]]:
    """One row per entry: daily cadence must not dump 30 rows into the LLM."""
    first: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    order: list[str] = []

    def add(when: date, move: Movement, *, overdue: bool) -> None:
        counts[move.entry_id] = counts.get(move.entry_id, 0) + 1
        if move.entry_id in first:
            return
        row: dict[str, Any] = {
            "id": move.entry_id,
            "label": move.label,
            "amount": move.amount,
            "kind": move.kind,
            "date": when.isoformat(),
        }
        if overdue:
            row["overdue"] = True
        first[move.entry_id] = row
        order.append(move.entry_id)

    for hit in proj.overdue:
        add(hit.date, hit.move, overdue=True)
    for day in proj.days:
        for move in (*day.outflows, *day.inflows):
            add(day.date, move, overdue=False)
    rows: list[dict[str, Any]] = []
    for entry_id in order:
        row = dict(first[entry_id])
        times = counts[entry_id]
        if times > 1:
            row["times"] = times
            row["total"] = row["amount"] * times
        rows.append(row)
    return rows


_INT_FIELDS = (
    "amount",
    "amount_min",
    "amount_max",
    "day",
    "day_min",
    "day_max",
    "min_due",
)


def _plan_payload(built: Plan) -> dict[str, Any]:
    """Gap math only. Spoken/rail advice is `advice`, not template steps."""
    return {
        "solvable": built.solvable,
        "gap": built.gap,
        "gap_date": built.gap_date.isoformat() if built.gap_date else None,
    }


def _llm_result(snap: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        **extra,
        "name": snap["name"],
        "cash": snap["cash"],
        "entries": snap["entries"],
        "missing": snap["missing"],
        "speak": snap["speak"],
        "conflicts": snap["conflicts"],
    }


def _prune_conflicts(conflicts: list[str], label: str) -> list[str]:
    prefix = f"{label}: "
    return [line for line in conflicts if not line.startswith(prefix)]


def _find_existing(
    entries: list[Entry], raw: dict[str, Any], today: date
) -> Entry | None:
    raw_id = raw.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        found = next((e for e in entries if e.id == raw_id.strip()), None)
        if found is not None:
            return found
    kind = raw.get("kind")
    label = raw.get("label")
    if kind not in KINDS or not isinstance(label, str) or not label.strip():
        return None
    incoming, error = _parse_entry({**raw, "id": "probe"}, today)
    if error or incoming is None:
        return next(
            (
                e
                for e in entries
                if e.kind == kind and norm_label(e.label) == norm_label(label)
            ),
            None,
        )
    return next((e for e in entries if same_item(e, incoming)), None)


def _same_when(a: Entry, b: Entry) -> bool:
    if a.on_date and b.on_date:
        return a.on_date == b.on_date
    if a.cadence == "once" and b.cadence == "once":
        ka, kb = a.on_date or a.day, b.on_date or b.day
        return ka == kb
    return a.day == b.day and a.cadence == b.cadence


def _validate_numbers(data: dict[str, Any], label: str) -> str | None:
    for key in ("amount", "amount_min", "amount_max", "min_due"):
        value = data.get(key)
        if value is not None and value < 0:
            return f"amount cannot be negative for {label}"
    for key in ("day", "day_min", "day_max"):
        value = data.get(key)
        if value is not None and not 1 <= value <= 31:
            return f"day must be 1–31 for {label}"
    return None


def _apply_timing(
    data: dict[str, Any], raw: dict[str, Any], today: date, label: str
) -> str | None:
    if "in_days" not in raw or raw["in_days"] is None:
        return None
    try:
        offset = int(raw["in_days"])
    except (TypeError, ValueError):
        return f"bad in_days for {label}"
    if offset < 0 or offset > WINDOW_DAYS:
        return f"in_days must be 0–{WINDOW_DAYS} for {label}"
    when = resolve_on_date(today, offset)
    data["on_date"] = when.isoformat()
    data["day"] = when.day
    if "cadence" not in raw or raw.get("cadence") in (None, ""):
        data["cadence"] = "once"
    return None


def _apply_range(data: dict[str, Any], raw: dict[str, Any]) -> None:
    if "amount" in raw and "amount_min" not in raw and "amount_max" not in raw:
        data["amount_min"] = None
        data["amount_max"] = None
    if (
        ("amount_min" in raw or "amount_max" in raw)
        and "amount" not in raw
    ):
        data["amount"] = None


def _overlay(
    existing: Entry, raw: dict[str, Any], today: date
) -> tuple[Entry | None, str | None]:
    data = asdict(existing)
    if "kind" in raw:
        kind = raw["kind"]
        if kind not in KINDS:
            return None, "kind must be income, need, debt, flex, or owed"
        data["kind"] = kind
    if "label" in raw:
        label = raw["label"]
        if not isinstance(label, str) or not label.strip():
            return None, "label is required"
        data["label"] = label.strip()[:80]
    if "cadence" in raw and raw["cadence"] is not None:
        if raw["cadence"] not in CADENCES:
            return None, f"bad cadence for {data['label']}"
        data["cadence"] = raw["cadence"]
    if "status" in raw and raw["status"] is not None:
        if raw["status"] not in STATUSES:
            return None, f"bad status for {data['label']}"
        data["status"] = raw["status"]
    try:
        for field in _INT_FIELDS:
            if field in raw:
                data[field] = _opt_int(raw[field])
    except (TypeError, ValueError):
        return None, f"bad number for {data['label']}"
    _apply_range(data, raw)
    error = _apply_timing(data, raw, today, data["label"])
    if error:
        return None, error
    error = _validate_numbers(data, data["label"])
    if error:
        return None, error
    data.pop("in_days", None)
    return Entry(**data), None


def _parse_entry(
    raw: dict[str, Any], today: date
) -> tuple[Entry | None, str | None]:
    kind = raw.get("kind")
    label = raw.get("label")
    if kind not in KINDS:
        return None, "kind must be income, need, debt, flex, or owed"
    if not isinstance(label, str) or not label.strip():
        return None, "label is required"
    cadence = raw.get("cadence") or "monthly"
    status = raw.get("status") or "unknown"
    if cadence not in CADENCES:
        return None, f"bad cadence for {label}"
    if status not in STATUSES:
        return None, f"bad status for {label}"
    try:
        amount = _opt_int(raw.get("amount"))
        amount_min = _opt_int(raw.get("amount_min"))
        amount_max = _opt_int(raw.get("amount_max"))
        day = _opt_int(raw.get("day"))
        day_min = _opt_int(raw.get("day_min"))
        day_max = _opt_int(raw.get("day_max"))
        min_due = _opt_int(raw.get("min_due"))
    except (TypeError, ValueError):
        return None, f"bad number for {label}"
    numbers = {
        "amount": amount,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "day": day,
        "day_min": day_min,
        "day_max": day_max,
        "min_due": min_due,
        "cadence": cadence,
        "on_date": None,
    }
    _apply_range(numbers, raw)
    error = _apply_timing(numbers, raw, today, label)
    if error:
        return None, error
    error = _validate_numbers(numbers, label)
    if error:
        return None, error
    raw_id = raw.get("id")
    entry_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else _new_id()
    return (
        Entry(
            id=entry_id,
            kind=kind,
            label=label.strip()[:80],
            amount=numbers["amount"],
            amount_min=numbers["amount_min"],
            amount_max=numbers["amount_max"],
            day=numbers["day"],
            day_min=day_min,
            day_max=day_max,
            cadence=numbers["cadence"],
            status=status,
            min_due=min_due,
            on_date=numbers.get("on_date"),
        ),
        None,
    )


def derived_from_projection(proj: Projection) -> dict[str, Any]:
    """Calendar payload pushed live and rebuilt for past calls."""
    return {
        "finish": proj.finish,
        "crunch": {
            "date": proj.crunch.date.isoformat(),
            "amount": proj.crunch.amount,
        },
        "days": [
            {
                "date": day.date.isoformat(),
                "in": sum(m.amount for m in day.inflows),
                "out": sum(m.amount for m in day.outflows),
                "closing": day.closing,
                "moves": [
                    {
                        "id": m.entry_id,
                        "label": m.label,
                        "amount": m.amount,
                        "kind": m.kind,
                    }
                    for m in (*day.outflows, *day.inflows)
                ],
            }
            for day in proj.days
        ],
        "overdue": [
            {
                "id": hit.move.entry_id,
                "label": hit.move.label,
                "amount": hit.move.amount,
                "kind": hit.move.kind,
                "date": hit.date.isoformat(),
            }
            for hit in proj.overdue
        ],
    }


def rebuild_derived(
    *,
    today: date,
    cash: int | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Recompute the live calendar from durable session rows."""
    view = finance_from_rows(today=today, cash=cash, rows=rows)
    return view["derived"]


def finance_from_rows(
    *,
    today: date,
    cash: int | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Entries, missing, plan, and derived for a stored session."""
    entries = entries_from_rows(rows)
    gaps = missing_fields(cash, entries, today)
    derived = None
    plan = None
    advice = None
    if cash is not None:
        proj = project(today, cash, entries)
        built = build_plan(today, cash, entries)
        derived = derived_from_projection(proj)
        plan = _plan_payload(built)
        advice = advice_payload(today, cash, entries, proj)
        advice = {"points": advice["points"], "payoff": advice["payoff"]}
    return {
        "entries": [asdict(e) for e in entries],
        "missing": gaps,
        "plan": plan,
        "advice": advice,
        "derived": derived,
        "cash": cash,
    }


def entries_from_rows(rows: list[dict[str, Any]]) -> list[Entry]:
    entries: list[Entry] = []
    for row in rows:
        kind = row.get("kind")
        if kind not in KINDS:
            kind = "income" if row.get("direction") == "incoming" else "need"
        cadence = row.get("cadence") if row.get("cadence") in CADENCES else "monthly"
        status = row.get("status") if row.get("status") in STATUSES else "unknown"
        entries.append(
            Entry(
                id=str(row["id"]),
                kind=kind,  # type: ignore[arg-type]
                label=str(row["label"]),
                amount=_opt_int(row.get("amount")),
                amount_min=_opt_int(row.get("amount_min")),
                amount_max=_opt_int(row.get("amount_max")),
                day=_opt_int(row.get("day")),
                day_min=_opt_int(row.get("day_min")),
                day_max=_opt_int(row.get("day_max")),
                cadence=cadence,  # type: ignore[arg-type]
                status=status,  # type: ignore[arg-type]
                min_due=_opt_int(row.get("min_due")),
                on_date=row.get("on_date") if isinstance(row.get("on_date"), str) else None,
            )
        )
    return entries


def calendar_items(entries: list[Entry]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in entries:
        if entry.status == "paid":
            continue
        amount = planning_amount(entry)
        day = planning_day(entry)
        if amount is None or day is None:
            continue
        items.append(
            {
                "id": entry.id,
                "direction": "incoming" if entry.kind in ("income", "owed") else "outgoing",
                "label": entry.label,
                "amount": amount,
                "day": day,
            }
        )
    return items


def _row(entry: Entry) -> dict[str, Any]:
    amount = planning_amount(entry)
    return {
        "id": entry.id,
        "kind": entry.kind,
        "direction": "incoming" if entry.kind in ("income", "owed") else "outgoing",
        "label": entry.label,
        "amount": 0 if amount is None else amount,
        "amount_min": entry.amount_min,
        "amount_max": entry.amount_max,
        "day": entry.day,
        "day_min": entry.day_min,
        "day_max": entry.day_max,
        "cadence": entry.cadence,
        "status": entry.status,
        "min_due": entry.min_due,
        "on_date": entry.on_date,
    }
