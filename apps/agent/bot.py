"""
Pipecat voice bot entry point (scaffold).

Wire DailyTransport + STT/LLM/TTS pipeline here when implementing the agent.
"""

from __future__ import annotations

from loguru import logger


async def start_bot(*, session_id: str, room_url: str, token: str) -> None:
    """
    Join a Daily room and run the voice pipeline for a session.

    Scaffold: logs only. Later:
        DailyTransport(room_url, token, ...) + Pipeline([...])
    """
    logger.info(
        "bot.start_bot stub session_id={} room_url={} token_present={}",
        session_id,
        room_url,
        bool(token),
    )


async def cancel_bot(*, session_id: str) -> None:
    """Cancel a running bot pipeline. Scaffold: no-op."""
    logger.info("bot.cancel_bot stub session_id={}", session_id)


# Back-compat alias for earlier scaffold
async def run_bot(room_url: str, token: str) -> None:
    await start_bot(session_id="adhoc", room_url=room_url, token=token)


if __name__ == "__main__":
    import asyncio
    import os

    asyncio.run(
        start_bot(
            session_id="local",
            room_url=os.getenv("DAILY_ROOM_URL", ""),
            token=os.getenv("DAILY_TOKEN", ""),
        )
    )
