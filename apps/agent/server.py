"""FastAPI entry point for the Kubera voice agent service."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

import bot
import daily_rooms as daily
import store as db
from schemas import (
    ClientCredentials,
    CreateSessionRequest,
    MoneyItem,
    RoomInfo,
    SessionCreatedResponse,
    SessionHistoryResponse,
    SessionListItem,
    SessionStatus,
    SessionStatusResponse,
    TranscriptResponse,
    TranscriptTurn,
    error_payload,
)
from sessions import store
from tools import calendar_items, entries_from_rows, finance_from_rows


def _load_env() -> None:
    here = Path(__file__).resolve().parent
    for candidate in (here.parent.parent / ".env", here / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            break
    load_dotenv()


_load_env()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.configure(os.getenv("KUBERA_DB_PATH"))
    await db.init()
    try:
        yield
    finally:
        await db.shutdown()


app = FastAPI(title="Kubera Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _list_item(row: dict[str, Any]) -> SessionListItem:
    return SessionListItem(
        session_id=row["session_id"],
        status=row.get("status") or "ended",
        created_at=row.get("created_at") or "",
        ended_at=row.get("ended_at"),
        duration_seconds=row.get("duration_seconds"),
        ended_reason=row.get("ended_reason"),
        name=row.get("name"),
        tx_count=int(row.get("tx_count") or 0),
    )


def _session_day(created_at: str | None) -> date:
    parsed = _parse_dt(created_at)
    if parsed is None:
        return date.today()
    return parsed.date()


def _history_calendar(
    meta: dict[str, Any], txs: list[dict[str, Any]]
) -> tuple[list[MoneyItem], dict[str, Any]]:
    """Same rolling calendar and rail as the live RTVI snapshot."""
    cash = meta.get("cash")
    cash_i = int(cash) if cash is not None else None
    entries = entries_from_rows(txs)
    items = [
        MoneyItem(
            id=item["id"],
            direction=item["direction"],
            label=item["label"],
            amount=int(item["amount"]),
            day=item["day"],
        )
        for item in calendar_items(entries)
    ]
    view = finance_from_rows(
        today=_session_day(meta.get("created_at")),
        cash=cash_i,
        rows=txs,
    )
    return items, view


def _turns(rows: list[dict[str, Any]]) -> list[TranscriptTurn]:
    out: list[TranscriptTurn] = []
    for row in rows:
        role = row["role"]
        if role not in ("user", "agent"):
            continue
        out.append(
            TranscriptTurn(
                seq=row["seq"],
                role=role,
                text=row["text"],
                interrupted=bool(row.get("interrupted")),
                created_at=row["created_at"],
            )
        )
    return out


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    user_id: str | None = None,
) -> list[SessionListItem]:
    rows = await db.list_sessions(limit=limit, user_id=user_id)
    return [_list_item(row) for row in rows]


@app.post(
    "/sessions",
    response_model=SessionCreatedResponse,
    status_code=201,
    responses={
        503: {"model": None, "description": "Daily unavailable"},
        502: {"model": None, "description": "Room create failed"},
        500: {"model": None, "description": "Bot start failed"},
    },
)
async def create_session(
    body: CreateSessionRequest | None = None,
) -> SessionCreatedResponse | JSONResponse:
    body = body or CreateSessionRequest()
    user_id = body.client.user_id if body.client else None
    logger.info("POST /sessions user_id={}", user_id)

    try:
        creds = await daily.create_room_and_tokens()
    except Exception as exc:  # noqa: BLE001
        logger.exception("room create failed")
        return JSONResponse(
            status_code=502,
            content=error_payload(
                "room_create_failed",
                str(exc) or "Daily rejected room creation",
            ),
        )

    session = store.create(
        room_url=creds.room_url,
        room_name=creds.room_name,
        expires_at=creds.expires_at,
        user_token=creds.user_token,
        bot_token=creds.bot_token,
        user_id=user_id,
        status=SessionStatus.starting,
    )

    await db.record_session(
        session_id=session.session_id,
        user_id=user_id,
        room_name=session.room_name,
        room_url=session.room_url,
        status=SessionStatus.starting.value,
    )

    try:
        await bot.start_bot(
            session_id=session.session_id,
            room_url=session.room_url,
            token=session.bot_token,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("bot start failed session_id={}", session.session_id)
        store.set_status(session.session_id, SessionStatus.error)
        await db.end_session(
            session_id=session.session_id,
            status=SessionStatus.error.value,
            ended_reason="error",
        )
        await daily.delete_room(session.room_name)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "bot_start_failed",
                str(exc) or "Bot failed to start",
            ),
        )

    store.set_status(session.session_id, SessionStatus.ready)
    await db.set_session_status(
        session_id=session.session_id, status=SessionStatus.ready.value
    )

    return SessionCreatedResponse(
        session_id=session.session_id,
        status=SessionStatus.ready,
        room=RoomInfo(
            url=session.room_url,
            name=session.room_name,
            expires_at=session.expires_at,
        ),
        client=ClientCredentials(token=session.user_token),
    )


@app.get(
    "/sessions/{session_id}",
    response_model=SessionStatusResponse,
    responses={404: {"description": "Session not found"}},
)
async def get_session(session_id: str) -> SessionStatusResponse | JSONResponse:
    live = store.get(session_id)
    if live is not None:
        return SessionStatusResponse(
            session_id=live.session_id,
            status=live.status,
            room=RoomInfo(
                url=live.room_url,
                name=live.room_name,
                expires_at=live.expires_at,
            ),
            created_at=live.created_at,
        )

    row = await db.get_session(session_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )

    created = _parse_dt(row.get("created_at")) or datetime.now(timezone.utc)
    ended = _parse_dt(row.get("ended_at"))
    try:
        status = SessionStatus(row["status"])
    except ValueError:
        status = SessionStatus.ended

    return SessionStatusResponse(
        session_id=row["session_id"],
        status=status,
        room=RoomInfo(
            url=row.get("room_url") or "",
            name=row.get("room_name") or "",
            expires_at=created + timedelta(hours=1),
        ),
        created_at=created,
        ended_at=ended,
        duration_seconds=row.get("duration_seconds"),
    )


@app.get(
    "/sessions/{session_id}/transcript",
    response_model=TranscriptResponse,
    responses={404: {"description": "Session not found"}},
)
async def get_transcript(session_id: str) -> TranscriptResponse | JSONResponse:
    row = await db.get_session(session_id)
    if row is None and store.get(session_id) is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )
    turns = await db.list_transcript(session_id)
    return TranscriptResponse(session_id=session_id, turns=_turns(turns))


@app.get(
    "/sessions/{session_id}/history",
    response_model=SessionHistoryResponse,
    responses={404: {"description": "Session not found"}},
)
async def get_history(session_id: str) -> SessionHistoryResponse | JSONResponse:
    history = await db.session_history(session_id)
    if history is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )
    meta = history["session"]
    txs = history["transactions"]
    item = _list_item({**meta, "tx_count": len(txs)})
    money, view = _history_calendar(meta, txs)
    return SessionHistoryResponse(
        session=item,
        transcript=_turns(history["transcript"]),
        transactions=money,
        derived=view.get("derived"),
        cash=view.get("cash"),
        entries=view.get("entries") or [],
        missing=view.get("missing") or [],
        plan=view.get("plan"),
        advice=meta.get("advice") or view.get("advice"),
    )


@app.get(
    "/sessions/{session_id}/transactions",
    responses={404: {"description": "Nothing recorded for this session"}},
)
async def get_transactions(session_id: str) -> JSONResponse:
    session = await db.get_session(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )
    txs = await db.list_transactions(session_id)
    if not txs:
        return JSONResponse(
            status_code=404,
            content=error_payload(
                "no_transactions", f"No transactions recorded for {session_id}"
            ),
        )
    return JSONResponse(
        status_code=200,
        content={"session_id": session_id, "transactions": txs},
    )


@app.delete(
    "/sessions/{session_id}",
    responses={
        204: {"description": "Session ended"},
        404: {"description": "Session not found"},
    },
)
async def end_session(session_id: str) -> Response:
    session = store.get(session_id)
    if session is None:
        # Still mark durable row ended if it exists (idempotent hang-up).
        row = await db.get_session(session_id)
        if row is None:
            return JSONResponse(
                status_code=404,
                content=error_payload(
                    "session_not_found", f"Unknown session {session_id}"
                ),
            )
        await db.end_session(
            session_id=session_id, status="ended", ended_reason="user"
        )
        return Response(status_code=204)

    if session.status == SessionStatus.ended:
        return Response(status_code=204)

    store.set_status(session_id, SessionStatus.ending)
    await bot.cancel_bot(session_id=session_id)
    await daily.delete_room(session.room_name)
    store.set_status(session_id, SessionStatus.ended)
    await db.end_session(
        session_id=session_id,
        status=SessionStatus.ended.value,
        ended_reason="user",
    )
    logger.info("DELETE /sessions/{} ended", session_id)
    return Response(status_code=204)


def main() -> None:
    import uvicorn

    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "7860"))
    uvicorn.run("server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
