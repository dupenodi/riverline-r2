"""Simple money tools: record incoming / outgoing amounts with a day."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


class MoneyTools:
    """One session's money list, exposed as two tools."""

    def __init__(
        self,
        *,
        on_change: Callable[[dict[str, Any]], Awaitable[None]],
        persist_add: Callable[..., Awaitable[None]] | None = None,
        persist_remove: Callable[..., Awaitable[None]] | None = None,
        persist_name: Callable[..., Awaitable[None]] | None = None,
        session_id: str | None = None,
    ) -> None:
        self.items: list[dict[str, Any]] = []
        self.user_name: str | None = None
        self.version = 0
        self._on_change = on_change
        self._persist_add = persist_add
        self._persist_remove = persist_remove
        self._persist_name = persist_name
        self._session_id = session_id

    async def publish(self) -> None:
        await self._publish()

    def schemas(self) -> list[FunctionSchema]:
        return [
            FunctionSchema(
                name="add_money",
                description=(
                    "Record money coming in or going out on a day of the month. "
                    "Call as soon as you know the amount and the day. Several "
                    "items in one call is fine."
                ),
                properties={
                    "items": {
                        "type": "array",
                        "description": "Money items to record.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "direction": {
                                    "type": "string",
                                    "enum": ["incoming", "outgoing"],
                                    "description": (
                                        "incoming = salary, income, refunds. "
                                        "outgoing = EMI, loans, credit cards, "
                                        "bills, rent, spending."
                                    ),
                                },
                                "label": {
                                    "type": "string",
                                    "description": "Short name, e.g. 'Salary', 'HDFC EMI'.",
                                },
                                "amount": {
                                    "type": "integer",
                                    "description": "Amount in whole rupees.",
                                },
                                "day": {
                                    "type": "integer",
                                    "description": (
                                        "Day of the month it lands, 1–31. "
                                        "Ask if the user did not say."
                                    ),
                                },
                            },
                            "required": ["direction", "label", "amount", "day"],
                        },
                    },
                    "user_name": {
                        "type": "string",
                        "description": "User's first name, once they give it.",
                    },
                },
                required=["items"],
                handler=self._handle_add,
            ),
            FunctionSchema(
                name="remove_money",
                description="Forget an item the user retracts or corrected.",
                properties={
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ids returned by add_money.",
                    },
                },
                required=["ids"],
                handler=self._handle_remove,
            ),
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "transactions",
            "version": self.version,
            "name": self.user_name,
            "items": list(self.items),
        }

    async def _handle_add(self, params: FunctionCallParams) -> None:
        raw_items = params.arguments.get("items") or []
        name = params.arguments.get("user_name")
        recorded: list[str] = []
        problems: list[str] = []

        if isinstance(name, str) and name.strip():
            cleaned = name.strip().split()[0][:40]
            if cleaned != self.user_name:
                self.user_name = cleaned
                self.version += 1
                if self._persist_name and self._session_id:
                    await self._persist_name(
                        session_id=self._session_id, name=cleaned
                    )

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            direction = raw.get("direction")
            label = raw.get("label")
            amount = raw.get("amount")
            day_raw = raw.get("day")
            if direction not in ("incoming", "outgoing"):
                problems.append("direction must be incoming or outgoing")
                continue
            if not isinstance(label, str) or not label.strip():
                problems.append("label is required")
                continue
            try:
                amount_i = int(amount)
            except (TypeError, ValueError):
                problems.append(f"bad amount for {label}")
                continue
            if amount_i < 0:
                problems.append(f"amount must be positive for {label}")
                continue
            try:
                day_i = int(day_raw)
            except (TypeError, ValueError):
                problems.append(f"day is required for {label} (1–31)")
                continue
            if not 1 <= day_i <= 31:
                problems.append(f"day must be 1–31 for {label}")
                continue

            item = {
                "id": _new_id(),
                "direction": direction,
                "label": label.strip()[:80],
                "amount": amount_i,
                "day": day_i,
            }
            self.items.append(item)
            recorded.append(item["id"])
            self.version += 1
            if self._persist_add and self._session_id:
                await self._persist_add(session_id=self._session_id, item=item)

        logger.info("add_money recorded={} problems={}", recorded, problems)
        await self._publish()

        result: dict[str, Any] = {
            "recorded": recorded,
            "items": self.items,
        }
        if problems:
            result["could_not_record"] = problems
            result["instruction"] = (
                "Fix the bad items and call add_money again. Do not mention "
                "this to the user. If day is missing, ask which day of the "
                "month it lands."
            )
        await params.result_callback(result)

    async def _handle_remove(self, params: FunctionCallParams) -> None:
        ids = [str(i) for i in (params.arguments.get("ids") or [])]
        removed: list[str] = []
        keep: list[dict[str, Any]] = []
        for item in self.items:
            if item["id"] in ids:
                removed.append(item["id"])
                self.version += 1
                if self._persist_remove and self._session_id:
                    await self._persist_remove(
                        session_id=self._session_id, item_id=item["id"]
                    )
            else:
                keep.append(item)
        self.items = keep

        logger.info("remove_money removed={}", removed)
        await self._publish()
        await params.result_callback({"removed": removed, "items": self.items})

    async def _publish(self) -> None:
        await self._on_change(self.snapshot())
