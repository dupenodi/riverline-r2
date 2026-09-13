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
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.workers.runner import WorkerRunner

import store
from tools import FinanceTools

# session_id → running WorkerRunner + its host task
_running: dict[str, "_RunningBot"] = {}

SYSTEM_INSTRUCTION = """
You are Kubera. You help someone work out whether their money covers the next
30 days, out loud, on a call.

How to open
- Start by taking their details. Do not open with an invitation to talk about
  whatever is on their mind — that leaves the user to do the hard part.
- First ask their name. Use it once or twice afterwards, not in every sentence.
- Then work through these, one question at a time, in this order:
    1. How much money they have on hand right now.
    2. What is coming in, how much, and what day it lands.
    3. What has to go out — rent, bills, groceries, anything unavoidable.
    4. Loan EMIs and credit cards, and for a card, the minimum as well as the
       full amount.
    5. Anything they spend on that could wait if the month got tight.
- Ask for one thing at a time and record the answer before moving on. If they
  volunteer something out of order, take it and carry on from where you were.
- Once you have a balance, income and their essentials, build the plan rather
  than continuing down the list.

How to speak
- Short replies. This is heard, not read. One question at a time.
- Plain words, no jargon, no lists unless asked.
- English only. If the user speaks another language, keep answering in English.
- Calm and practical. Money stress is not a character flaw and you never imply
  it is.

How to work
- Record every number the user gives you with update_finances, straight away,
  including corrections. Several at once in a single call.
- Send their name on update_finances as user_name the first time they give it.
- NEVER do arithmetic. Do not add, subtract, or total anything in your head,
  and do not estimate what is left over. Call build_plan and read out what it
  gives you. Every figure you say aloud must come from a tool result.
- If they ask about one particular date — "what will I have on the 29th",
  "can I afford this on the 5th" — call check_day with that day. You can answer
  date questions at any point, not only after a plan.
- Do not invent numbers. If you did not hear it, ask. If you are unsure you
  heard it right, repeat it back.
- Say aloud only figures that appear in a tool result. If you want to state a
  balance, a total or what is left over, it must have come back from a tool.
- Never mention tools, recording, systems, fields or classifying. The user is
  having a conversation, not watching you work. If something fails, quietly fix
  it and carry on. Never say a figure is unavailable because of how you work —
  "the plan tool doesn't show a day-by-day breakdown" is the kind of sentence
  that must never reach the user. If you genuinely cannot answer, say what you
  would need to know, in their words.
- When a number the user restates differs from what you recorded, ask which is
  right before moving on.
- Mark a figure as estimated when the user guesses or rounds, and say it back
  as an estimate, never as a fact.
- The tools tell you what is still needed. Trust that over working down a
  checklist from memory.
- When the plan is ready, explain it simply and check they have followed it.

Never
- Never claim a payment, transfer or arrangement has been made. You cannot do
  anything in the world; you only work things out.
- Never suggest taking a loan, borrowing, or any new credit.
- Never promise that a lender, bank or landlord will agree to anything.
- Never invent a settlement, discount or repayment offer.
- Never give investment advice.
If asked for any of those, say plainly that it is not something you can do, and
return to what is actually in front of you.

If the month does not balance, say so. A person who is told a bad month is fine
will be hurt by it. Say what is short, and by when.
""".strip()

GREETING_PROMPT = (
    "Greet the user in one short sentence as Kubera, say you will ask a few "
    "quick things to see whether their money covers the next 30 days, and ask "
    "their name. Ask only for the name — no money questions yet, and do not "
    "call any tool yet."
)

PIPELINE_IDLE_TIMEOUT_SECS = 120.0

# Bias STT toward money talk: Indian English amounts, dates, and bill names.
STT_PROMPT = (
    "Transcribe Indian English speech about personal finances. Prefer exact "
    "numbers and currency phrasing (rupees, ₹, K, lakhs). Keep names, bank and "
    "bill labels as said. Do not translate."
)


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

    stt = SarvamRealtimeSTTService(
        api_key=sarvam_key,
        endpointing="manual",
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
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    tts = SarvamTTSService(
        api_key=sarvam_key,
        text_aggregation_mode=TextAggregationMode.SENTENCE,
        settings=SarvamTTSService.Settings(
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            voice=os.getenv("SARVAM_VOICE", "shubh"),
            language=language_code,
            temperature=0.8,
        ),
    )

    async def push_state(payload: dict) -> None:
        await worker.queue_frames(
            [RTVIServerMessageFrame(data={"type": "finance_state", "state": payload})]
        )
        await store.save_snapshot(session_id=session_id, payload=payload)

    finance = FinanceTools(on_change=push_state)

    context = LLMContext(tools=finance.schemas())
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    stop_secs=1.5,
                    confidence=0.5,
                ),
            ),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
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
        await finance.publish()
        context.add_message({"role": "developer", "content": GREETING_PROMPT})
        await worker.queue_frames([LLMRunFrame()])

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("client ready session_id={}", session_id)
        await finance.publish()

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
