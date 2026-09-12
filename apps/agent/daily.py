"""
Daily.co REST helpers (scaffold).

Implement create/delete room + meeting tokens here when wiring real sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger


@dataclass(frozen=True)
class DailyRoomCredentials:
    room_url: str
    room_name: str
    expires_at: datetime
    user_token: str
    bot_token: str


async def create_room_and_tokens(*, ttl_seconds: int = 3600) -> DailyRoomCredentials:
    """
    Create a private Daily room and mint user + bot meeting tokens.

    Scaffold: returns placeholders. Replace with Daily REST calls using DAILY_API_KEY.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    room_name = "scaffold-room"
    logger.info("daily.create_room_and_tokens stub room_name={}", room_name)
    return DailyRoomCredentials(
        room_url=f"https://example.daily.co/{room_name}",
        room_name=room_name,
        expires_at=expires_at,
        user_token="scaffold-user-token",
        bot_token="scaffold-bot-token",
    )


async def delete_room(room_name: str) -> None:
    """Delete a Daily room (best effort). Scaffold: no-op."""
    logger.info("daily.delete_room stub room_name={}", room_name)
