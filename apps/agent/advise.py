"""Advice for the rail and the spoken recap.

Numbers come from the projection. Wording is written for this ledger.
If Sarvam is available, it rewrites the bullets; otherwise a data-backed
draft is shown. The payoff line is always engine-owned.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date
from typing import Any, Sequence

import httpx
from loguru import logger

from cashflow import (
    Entry,
    Projection,
    is_inflow,
    planning_amount,
)

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

ADVICE_PROMPT = """You write short, specific 30-day money advice.
The JSON is the only source of numbers and labels. Do not invent either.
Write 3 to 5 bullets. One sentence each. Indian English. No markdown.
Talk about THIS ledger: what to delay, shrink, substitute, or collect, and why.
Cheaper substitutes for flex (free plan instead of paid) are allowed.
No loans. No investing. Do not mention tools.
Do not write a payoff about the lowest balance or staying above zero.
Reply with JSON only: {"points":["...","..."]}
"""


def rupees(amount: int) -> str:
    return f"₹{amount:,}".replace(",", ",")


def short_date(iso: str) -> str:
    try:
        year, month, day = (int(part) for part in iso.split("-"))
    except ValueError:
        return iso
    if not 1 <= month <= 12:
        return iso
    return f"{day} {_MONTHS[month - 1]}"


def picture(
    today: date,
    cash: int,
    entries: Sequence[Entry],
    proj: Projection,
) -> dict[str, Any]:
    """Compact ledger the writer (model or draft) is allowed to use."""
    hits: dict[str, list[date]] = defaultdict(list)
    for day in proj.days:
        for move in (*day.outflows, *day.inflows):
            hits[move.entry_id].append(day.date)

    items: list[dict[str, Any]] = []
    for entry in entries:
        amount = planning_amount(entry)
        if amount is None:
            continue
        when = hits.get(entry.id) or []
        row: dict[str, Any] = {
            "id": entry.id,
            "label": entry.label,
            "kind": entry.kind,
            "amount": amount,
            "cadence": entry.cadence,
            "in": is_inflow(entry),
        }
        if when:
            row["date"] = when[0].isoformat()
            row["times"] = len(when)
            if len(when) > 1:
                row["total"] = amount * len(when)
        items.append(row)

    heavy: list[dict[str, Any]] = []
    for day in proj.days:
        out = sum(m.amount for m in day.outflows)
        if out <= 0:
            continue
        if out < max(cash // 4, 3000) and day.closing >= 0:
            continue
        heavy.append(
            {
                "date": day.date.isoformat(),
                "out": out,
                "closing": day.closing,
                "labels": [m.label for m in day.outflows],
            }
        )
        if len(heavy) == 4:
            break

    return {
        "today": today.isoformat(),
        "cash": cash,
        "lowest": proj.crunch.amount,
        "lowest_date": proj.crunch.date.isoformat(),
        "finish": proj.finish,
        "items": items,
        "heavy_days": heavy,
    }


def payoff_from(proj: Projection) -> dict[str, Any]:
    return {
        "lowest": proj.crunch.amount,
        "date": proj.crunch.date.isoformat(),
        "ok": proj.crunch.amount >= 0,
        "finish": proj.finish,
    }


def draft_points(brief: dict[str, Any]) -> list[str]:
    """Data-backed bullets when the model is not used. Still about THIS ledger."""
    points: list[str] = []
    items: list[dict[str, Any]] = list(brief.get("items") or [])
    cash = int(brief.get("cash") or 0)

    dailies = [row for row in items if row.get("cadence") == "daily" and row.get("total")]
    if dailies:
        names = " and ".join(
            f"{row['label']} {rupees(row['amount'])}/day" for row in dailies
        )
        total = sum(int(row["total"]) for row in dailies)
        line = f"{names} is {rupees(total)} over 30 days"
        if cash and total >= cash:
            line += f", more than the {rupees(cash)} you have today"
        points.append(line + ".")

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in items:
        if row.get("in") or row.get("cadence") in ("daily", "weekly"):
            continue
        if not row.get("date"):
            continue
        by_day[str(row["date"])].append(row)
    clusters = sorted(
        by_day.items(),
        key=lambda pair: -sum(int(r["amount"]) for r in pair[1]),
    )
    for day, group in clusters:
        if len(group) < 2:
            continue
        total = sum(int(r["amount"]) for r in group)
        labels = ", ".join(str(r["label"]) for r in group)
        points.append(
            f"{labels} all land on {short_date(day)} — {rupees(total)} that day."
        )
        break

    flex = [row for row in items if row.get("kind") == "flex"]
    for row in flex[:2]:
        when = f" on {short_date(row['date'])}" if row.get("date") else ""
        points.append(
            f"{row['label']} {rupees(int(row['amount']))}{when} is optional — "
            "cut it or use a cheaper version if the week before looks tight."
        )

    incomes = [
        row
        for row in items
        if row.get("in") and row.get("date")
    ]
    heavy = list(brief.get("heavy_days") or [])
    if incomes and heavy:
        inc = incomes[0]
        first_heavy = str(heavy[0]["date"])
        if str(inc["date"]) > first_heavy:
            points.append(
                f"{inc['label']} {rupees(int(inc['amount']))} arrives "
                f"{short_date(str(inc['date']))}, after the heavy day on "
                f"{short_date(first_heavy)}. Optional spend before that can wait."
            )

    weekly = [row for row in items if row.get("cadence") == "weekly" and row.get("total")]
    for row in weekly[:1]:
        points.append(
            f"{row['label']} {rupees(int(row['amount']))} weekly is "
            f"{rupees(int(row['total']))} across the next 30 days."
        )

    unique: list[str] = []
    seen: set[str] = set()
    for line in points:
        if line in seen:
            continue
        seen.add(line)
        unique.append(line)
        if len(unique) == 4:
            break
    return unique


def advice_payload(
    today: date,
    cash: int,
    entries: Sequence[Entry],
    proj: Projection,
    points: list[str] | None = None,
) -> dict[str, Any]:
    brief = picture(today, cash, entries, proj)
    return {
        "points": list(points or draft_points(brief)),
        "payoff": payoff_from(proj),
        "brief": brief,
    }


async def rewrite_points(brief: dict[str, Any]) -> list[str] | None:
    """Ask Sarvam to write the bullets. None means keep the draft."""
    key = os.getenv("SARVAM_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("SARVAM_SUMMARY_MODEL", "sarvam-105b-conversations")
    body = {
        "today": brief.get("today"),
        "cash": brief.get("cash"),
        "lowest": brief.get("lowest"),
        "lowest_date": brief.get("lowest_date"),
        "finish": brief.get("finish"),
        "items": brief.get("items"),
        "heavy_days": brief.get("heavy_days"),
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                "https://api.sarvam.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "api-subscription-key": key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.5,
                    "max_tokens": 400,
                    "messages": [
                        {"role": "system", "content": ADVICE_PROMPT},
                        {"role": "user", "content": json.dumps(body, default=str)},
                    ],
                },
            )
        response.raise_for_status()
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception as exc:  # noqa: BLE001 — advice must not break the call
        logger.warning("advice rewrite failed: {}", exc)
        return None
    points = _parse_points(content)
    if not points:
        logger.warning("advice rewrite returned no points")
        return None
    return points


def _parse_points(raw: str) -> list[str]:
    text = raw.strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    blob = match.group(0) if match else text
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        lines = [
            re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
            for line in text.splitlines()
        ]
        return [line for line in lines if 12 <= len(line) <= 220][:5]
    rows = data.get("points") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, str):
            continue
        line = " ".join(row.split()).strip()
        if 12 <= len(line) <= 220:
            out.append(line)
        if len(out) == 5:
            break
    return out
