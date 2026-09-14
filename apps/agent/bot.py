"""
Kubera conversational voice bot (Pipecat + Daily).

Pipeline follows Pipecat's official Sarvam examples:
- STT: voice-sarvam-realtime.py (SarvamRealtimeSTTService, manual endpointing)
- LLM + tools: function-calling-sarvam.py (SarvamLLMService)
- TTS: SarvamTTSService (bulbul:v3)

Live captions are handled by PipelineWorker's RTVIObserver — no custom observers.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_context_summarizer import SummaryAppliedEvent
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.workers.runner import WorkerRunner

import store
from context_summary import assistant_aggregator_params
from prompts import GREETING_PROMPT, STT_PROMPT, get_system_instruction
from speech_gate import SpeechAudioGate
from tools import MoneyTools
from transcript import AgentTranscriptTap, TranscriptWriter, UserTranscriptTap

# session_id → running WorkerRunner + its host task
_running: dict[str, "_RunningBot"] = {}

PIPELINE_IDLE_TIMEOUT_SECS = 120.0


@dataclass
class _RunningBot:
    task: asyncio.Task[Any]
    runner: WorkerRunner
    joined: asyncio.Event = field(default_factory=asyncio.Event)


def _require_env(*names: str) -> None:
    missing = [n for n in names if not os.getenv(n, "").strip()]
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))


def _remote_participant_count(transport: DailyTransport) -> int:
    try:
        participants = transport.participants()
    except Exception:  # noqa: BLE001 — client already torn down
        return 0
    return sum(1 for key in participants if key != "local")


async def _run_pipeline(
    *,
    session_id: str,
    room_url: str,
    token: str,
    runner: WorkerRunner,
    joined: asyncio.Event,
) -> None:
    _require_env("SARVAM_API_KEY")
    sarvam_key = os.environ["SARVAM_API_KEY"]
    language_code = os.getenv("SARVAM_LANGUAGE", "en-IN")

    transport = DailyTransport(
        room_url,
        token,
        "Kubera",
        DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    # Sarvam closes idle realtime sockets at ~60s (close 1008). Our SpeechAudioGate
    # drops non-speech, so without pings the socket dies during agent talk / silence.
    # Pipecat sends {"event":"ping"} when keepalive_timeout is set.
    stt = SarvamRealtimeSTTService(
        api_key=sarvam_key,
        endpointing="manual",
        keepalive_timeout=30.0,
        keepalive_interval=5.0,
        settings=SarvamRealtimeSTTService.Settings(
            language_code=language_code,
            stream_type="balanced",
            mode="transcribe",
            prompt=STT_PROMPT,
        ),
    )

    # sarvam-105b uses /v2 (beta-gated). Conversations model uses /v1.
    llm = SarvamLLMService(
        api_key=sarvam_key,
        settings=SarvamLLMService.Settings(
            model="sarvam-105b-conversations",
            system_instruction=get_system_instruction(),
        ),
    )

    tts = SarvamTTSService(
        api_key=sarvam_key,
        text_aggregation_mode=TextAggregationMode.SENTENCE,
        settings=SarvamTTSService.Settings(
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            voice=os.getenv("SARVAM_VOICE", "rohan"),
            language=language_code,
            temperature=0.8,
        ),
    )

    async def push_state(payload: dict) -> None:
        await worker.queue_frames(
            [RTVIServerMessageFrame(data={"type": "transactions", "state": payload})]
        )

    money = MoneyTools(
        on_change=push_state,
        persist_add=store.add_transaction,
        persist_remove=store.remove_transaction,
        persist_name=store.set_session_name,
        persist_cash=store.set_session_cash,
        persist_advice=store.set_session_advice,
        session_id=session_id,
    )

    vad = SileroVADAnalyzer(
        params=VADParams(
            confidence=0.7,
            start_secs=0.1,
            stop_secs=1.5,
        ),
    )

    context = LLMContext(tools=money.schemas())
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(),
        assistant_params=assistant_aggregator_params(api_key=sarvam_key),
    )

    @assistant_aggregator.event_handler("on_summary_applied")
    async def on_summary_applied(aggregator, summarizer, event: SummaryAppliedEvent):
        logger.info(
            "context summarized session_id={} {} -> {} messages "
            "({} compressed, {} kept)",
            session_id,
            event.original_message_count,
            event.new_message_count,
            event.summarized_message_count,
            event.preserved_message_count,
        )

    turns = TranscriptWriter(session_id)

    pipeline = Pipeline(
        [
            transport.input(),
            SpeechAudioGate(vad),
            stt,
            UserTranscriptTap(turns),
            user_aggregator,
            llm,
            AgentTranscriptTap(turns),
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=PIPELINE_IDLE_TIMEOUT_SECS,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )

    await runner.add_workers(worker)

    greeted = False

    async def greet() -> None:
        nonlocal greeted
        if greeted:
            return
        greeted = True
        logger.info("greeting user session_id={}", session_id)
        await money.publish()
        context.add_message({"role": "developer", "content": GREETING_PROMPT})
        await worker.queue_frames([LLMRunFrame()])

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("client ready session_id={}", session_id)
        await money.publish()

    @transport.event_handler("on_joined")
    async def on_joined(transport, data):
        logger.info("bot joined room session_id={}", session_id)
        joined.set()
        if _remote_participant_count(transport) > 0:
            await greet()

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        logger.info("first participant joined session_id={}", session_id)
        await greet()

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        remaining = _remote_participant_count(transport)
        logger.info(
            "participant left session_id={} reason={} remaining={}",
            session_id,
            reason,
            remaining,
        )
        if remaining == 0:
            await runner.cancel()

    @worker.event_handler("on_idle_timeout")
    async def on_idle_timeout(worker):
        logger.warning("pipeline idle timeout session_id={}", session_id)

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker, frame):
        logger.error(
            "pipeline error session_id={} processor={} error={}",
            session_id,
            getattr(frame.processor, "name", "?"),
            frame.error,
        )

    logger.info("bot pipeline starting session_id={}", session_id)
    await runner.run()
    logger.info("bot pipeline finished session_id={}", session_id)


async def start_bot(
    *,
    session_id: str,
    room_url: str,
    token: str,
    join_timeout: float = 15.0,
) -> None:
    """Join a Daily room and run the voice pipeline for a session.

    Returns once the bot is actually in the room, so callers never hand a
    client credentials for a room nobody is waiting in.
    """
    if session_id in _running and not _running[session_id].task.done():
        raise RuntimeError(f"Bot already running for session {session_id}")

    # FastAPI already owns process signals; do not steal SIGINT from uvicorn.
    runner = WorkerRunner(handle_sigint=False)
    joined = asyncio.Event()
    task = asyncio.create_task(
        _run_pipeline(
            session_id=session_id,
            room_url=room_url,
            token=token,
            runner=runner,
            joined=joined,
        ),
        name=f"kubera-bot-{session_id}",
    )
    _running[session_id] = _RunningBot(task=task, runner=runner, joined=joined)

    def _cleanup(done: asyncio.Task[Any]) -> None:
        _running.pop(session_id, None)
        joined.set()
        if done.cancelled():
            logger.info("bot cancelled session_id={}", session_id)
            return
        exc = done.exception()
        if exc:
            logger.exception("bot crashed session_id={} err={}", session_id, exc)

    task.add_done_callback(_cleanup)

    try:
        await asyncio.wait_for(joined.wait(), timeout=join_timeout)
    except asyncio.TimeoutError:
        await cancel_bot(session_id=session_id)
        raise RuntimeError(
            f"Bot did not join the room within {join_timeout:.0f}s"
        ) from None

    if task.done():
        exc = task.exception()
        if exc:
            raise RuntimeError(f"Bot failed to start: {exc}") from exc
        raise RuntimeError("Bot exited before the call started")

    logger.info("bot.start_bot session_id={} room_url={}", session_id, room_url)


async def cancel_bot(*, session_id: str) -> None:
    """Cancel a running bot pipeline via the official WorkerRunner API."""
    handle = _running.get(session_id)
    if handle is None or handle.task.done():
        logger.info("bot.cancel_bot no-op session_id={}", session_id)
        return

    await handle.runner.cancel()
    try:
        await handle.task
    except asyncio.CancelledError:
        pass
    logger.info("bot.cancel_bot session_id={}", session_id)


async def run_bot(room_url: str, token: str) -> None:
    """Back-compat: run a one-off bot to completion."""
    runner = WorkerRunner(handle_sigint=True)
    await _run_pipeline(
        session_id="adhoc",
        room_url=room_url,
        token=token,
        runner=runner,
        joined=asyncio.Event(),
    )


if __name__ == "__main__":
    asyncio.run(
        run_bot(
            room_url=os.getenv("DAILY_ROOM_URL", ""),
            token=os.getenv("DAILY_TOKEN", ""),
        )
    )
