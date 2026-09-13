"""FastAPI entry point for the Kubera voice agent service."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

import bot
import daily_rooms as daily
import store as db
from schemas import (
    CreateSessionRequest,
    SessionCreatedResponse,
    SessionStatus,
    SessionStatusResponse,
    ClientCredentials,
    RoomInfo,
    error_payload,
)
from sessions import store

def _load_env() -> None:
    """Load .env from monorepo root (local) and/or CWD (Docker env_file still wins)."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent.parent / ".env", here / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            break
    load_dotenv()


_load_env()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the local store for the life of the process."""
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
    """
    Start a voice session: create Daily room + tokens, start bot, return client creds.

    Scaffold: create Daily room + tokens, start Kubera bot, return client creds.
    """
    body = body or CreateSessionRequest()
    user_id = body.client.user_id if body.client else None
    logger.info("POST /sessions user_id={}", user_id)

    try:
        creds = await daily.create_room_and_tokens()
    except Exception as exc:  # noqa: BLE001 — scaffold boundary
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
        await db.set_session_status(
            session_id=session.session_id, status=SessionStatus.error.value
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
    session = store.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )

    return SessionStatusResponse(
        session_id=session.session_id,
        status=session.status,
        room=RoomInfo(
            url=session.room_url,
            name=session.room_name,
            expires_at=session.expires_at,
        ),
        created_at=session.created_at,
    )


@app.get(
    "/sessions/{session_id}/finance",
    responses={404: {"description": "Nothing recorded for this session"}},
)
async def get_finance(session_id: str) -> JSONResponse:
    """The last snapshot this session published.

    Read straight from the local store rather than from the bot, so it still
    answers after the call has ended and after the process has restarted — the
    numbers are the point of the call and they outlive the room.
    """
    payload = await db.latest_snapshot(session_id)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content=error_payload(
                "no_finance_state", f"No financial state recorded for {session_id}"
            ),
        )
    return JSONResponse(status_code=200, content=payload)


@app.delete(
    "/sessions/{session_id}",
    responses={
        204: {"description": "Session ended"},
        404: {"description": "Session not found"},
    },
)
async def end_session(session_id: str) -> Response:
    """End a session (idempotent if already ended)."""
    session = store.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("session_not_found", f"Unknown session {session_id}"),
        )

    if session.status == SessionStatus.ended:
        return Response(status_code=204)

    store.set_status(session_id, SessionStatus.ending)
    await bot.cancel_bot(session_id=session_id)
    await daily.delete_room(session.room_name)
    store.set_status(session_id, SessionStatus.ended)
    await db.set_session_status(
        session_id=session_id, status=SessionStatus.ended.value
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
