"""Request/response models for the agent session API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class SessionStatus(str, Enum):
    starting = "starting"
    ready = "ready"
    ending = "ending"
    ended = "ended"
    error = "error"


class ClientInfo(BaseModel):
    user_id: str | None = None


class CreateSessionRequest(BaseModel):
    client: ClientInfo | None = None


class RoomInfo(BaseModel):
    url: str
    name: str
    expires_at: datetime


class ClientCredentials(BaseModel):
    token: str


class SessionCreatedResponse(BaseModel):
    session_id: str
    status: SessionStatus
    room: RoomInfo
    client: ClientCredentials


class SessionStatusResponse(BaseModel):
    session_id: str
    status: SessionStatus
    room: RoomInfo
    created_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None


class SessionListItem(BaseModel):
    session_id: str
    status: str
    created_at: str
    ended_at: str | None = None
    duration_seconds: int | None = None
    ended_reason: str | None = None
    name: str | None = None
    tx_count: int = 0


class TranscriptTurn(BaseModel):
    seq: int
    role: Literal["user", "agent"]
    text: str
    interrupted: bool = False
    created_at: str


class MoneyItem(BaseModel):
    id: str
    direction: Literal["incoming", "outgoing"]
    label: str
    amount: int
    day: int | None = None
    created_at: str | None = None


class TranscriptResponse(BaseModel):
    session_id: str
    turns: list[TranscriptTurn]


class SessionHistoryResponse(BaseModel):
    session: SessionListItem
    transcript: list[TranscriptTurn]
    transactions: list[MoneyItem]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


ErrorCode = Literal[
    "daily_unavailable",
    "room_create_failed",
    "bot_start_failed",
    "session_not_found",
    "no_transactions",
]


def error_payload(
    code: ErrorCode,
    message: str,
    request_id: str | None = None,
) -> dict:
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id)
    ).model_dump()
