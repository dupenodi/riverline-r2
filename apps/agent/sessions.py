"""In-memory session registry (scaffold — replace with durable store later)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from schemas import SessionStatus


@dataclass
class Session:
    session_id: str
    status: SessionStatus
    room_url: str
    room_name: str
    expires_at: datetime
    user_token: str
    bot_token: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        *,
        room_url: str,
        room_name: str,
        expires_at: datetime,
        user_token: str,
        bot_token: str,
        user_id: str | None = None,
        status: SessionStatus = SessionStatus.starting,
    ) -> Session:
        session = Session(
            session_id=str(uuid4()),
            status=status,
            room_url=room_url,
            room_name=room_name,
            expires_at=expires_at,
            user_token=user_token,
            bot_token=bot_token,
            user_id=user_id,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def set_status(self, session_id: str, status: SessionStatus) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.status = status
        return session


store = SessionStore()
