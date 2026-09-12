"""Daily.co REST helpers for room + meeting token lifecycle."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp
from loguru import logger
from pipecat.transports.daily.utils import (
    DailyMeetingTokenParams,
    DailyMeetingTokenProperties,
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)


@dataclass(frozen=True)
class DailyRoomCredentials:
    room_url: str
    room_name: str
    expires_at: datetime
    user_token: str
    bot_token: str


def _api_key() -> str:
    key = os.getenv("DAILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DAILY_API_KEY is not set")
    return key


def _api_url() -> str:
    return os.getenv("DAILY_API_URL", "https://api.daily.co/v1").rstrip("/")


async def create_room_and_tokens(*, ttl_seconds: int = 3600) -> DailyRoomCredentials:
    """Create a private Daily room and mint user + bot meeting tokens."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    room_name = f"kubera-{uuid.uuid4().hex[:12]}"
    exp = time.time() + ttl_seconds

    async with aiohttp.ClientSession() as session:
        helper = DailyRESTHelper(
            daily_api_key=_api_key(),
            daily_api_url=_api_url(),
            aiohttp_session=session,
        )

        room = await helper.create_room(
            DailyRoomParams(
                name=room_name,
                privacy="private",
                properties=DailyRoomProperties(
                    exp=exp,
                    eject_at_room_exp=True,
                    enable_chat=False,
                    start_video_off=True,
                    max_participants=2,
                ),
            )
        )

        user_token = await helper.get_token(
            room_url=room.url,
            expiry_time=float(ttl_seconds),
            owner=False,
            eject_at_token_exp=True,
            params=DailyMeetingTokenParams(
                properties=DailyMeetingTokenProperties(
                    user_name="You",
                    start_video_off=True,
                    start_audio_off=False,
                )
            ),
        )

        bot_token = await helper.get_token(
            room_url=room.url,
            expiry_time=float(ttl_seconds),
            owner=True,
            eject_at_token_exp=True,
            params=DailyMeetingTokenParams(
                properties=DailyMeetingTokenProperties(
                    user_name="Kubera",
                    start_video_off=True,
                    start_audio_off=False,
                )
            ),
        )

    logger.info("daily room created name={} url={}", room.name, room.url)
    return DailyRoomCredentials(
        room_url=room.url,
        room_name=room.name,
        expires_at=expires_at,
        user_token=user_token,
        bot_token=bot_token,
    )


async def delete_room(room_name: str) -> None:
    """Delete a Daily room (best effort)."""
    if not room_name:
        return
    try:
        async with aiohttp.ClientSession() as session:
            helper = DailyRESTHelper(
                daily_api_key=_api_key(),
                daily_api_url=_api_url(),
                aiohttp_session=session,
            )
            await helper.delete_room_by_name(room_name)
            logger.info("daily room deleted name={}", room_name)
    except Exception as exc:  # noqa: BLE001 — best effort cleanup
        logger.warning("daily room delete failed name={} err={}", room_name, exc)
