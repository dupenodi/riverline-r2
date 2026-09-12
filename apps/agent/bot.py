"""
Kubera conversational voice bot (Pipecat + Daily).

Follows Pipecat's official Sarvam realtime example:
https://github.com/pipecat-ai/pipecat/blob/main/examples/voice/voice-sarvam-realtime.py

Pipeline: Daily → SarvamRealtimeSTT (manual endpointing) → OpenRouter LLM → Sarvam TTS.
"""

from __future__ import annotations

import asyncio
import os
import statistics
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndWorkerFrame, LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.services.llm_service import LLMService
from pipecat.services.openrouter.llm import OpenRouterLLMService
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.workers.runner import WorkerRunner

from tools import FinanceTools

# session_id → running WorkerRunner + its host task
_running: dict[str, _RunningBot] = {}

SYSTEM_INSTRUCTION = """
You are Kubera. You help someone work out whether their money covers the next
30 days, out loud, on a call.

How to speak
- Short replies. This is heard, not read. One question at a time.
- Plain words, no jargon, no lists unless asked.
- English. If the user speaks Hindi, you may answer in Hindi.
- Calm and practical. Money stress is not a character flaw and you never imply
  it is.

How to work
- Record every number the user gives you with update_finances, straight away,
  including corrections. Several at once in a single call.
- NEVER do arithmetic. Do not add, subtract, or total anything in your head,
  and do not estimate what is left over. Call build_plan and read out what it
  gives you. Every figure you say aloud must come from a tool result.
- Do not invent numbers. If you did not hear it, ask. If you are unsure you
  heard it right, repeat it back.
- Say aloud only figures that appear in a tool result. If you want to state a
  balance, a total or what is left over, it must have come back from a tool.
- Never mention tools, recording, systems, fields or classifying. The user is
  having a conversation, not watching you work. If something fails, quietly fix
  it and carry on.
- When a number the user restates differs from what you recorded, ask which is
  right before moving on.
- Mark a figure as estimated when the user guesses or rounds, and say it back
  as an estimate, never as a fact.
- Ask about what is actually missing rather than working through a checklist.
  The tools tell you what is still needed.
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
    "Greet the user in one short sentence as Kubera, say you can help them see "
    "whether their money covers the next 30 days, and ask what is on their mind. "
    "Do not call any tool yet."
)

# Spoken verbatim if the LLM has not produced a greeting in time, so the user is
# never met with silence on a slow or failing first completion.
GREETING_FALLBACK = (
    "Hi, I'm Kubera. I can help you see whether your money covers the next "
    "30 days. What's on your mind?"
)

# How long to wait for the LLM greeting to reach TTS before speaking the fallback.
# A cold first completion (OpenRouter connection setup included) measures around
# four seconds, so this leaves headroom rather than racing it.
GREETING_TIMEOUT_SECS = 8.0

# Silence before Kubera checks in, and how many times it will do so before
# closing the call out rather than sitting on an open line forever. Money talk
# comes with long pauses, so the first check-in is deliberately patient.
USER_IDLE_TIMEOUT_SECS = 30.0
IDLE_NUDGES = [
    "Take your time — I'm still here whenever you're ready.",
    "I'll let you go for now. Start another call whenever you want to pick this up.",
]

# Pipeline-level idle guard: nothing flowing at all (browser killed, network gone)
# for this long tears the bot down instead of leaving it billing in an empty room.
PIPELINE_IDLE_TIMEOUT_SECS = 120.0

# Which LLM the turn loop runs on. Sarvam is the default: on this account it
# measured a 0.366s p50 time-to-first-token against 1.816s for the previous
# openai/gpt-4o-mini over OpenRouter, with a far tighter spread (1.3x
# max/min vs 4.1x) — and the LLM is ~85% of the user-perceived turn latency.
# OpenRouter stays wired up as the alternative; set LLM_PROVIDER=openrouter.
DEFAULT_LLM_PROVIDER = "sarvam"

# Sarvam's conversation-tuned model — the one variant they exclude from their
# reasoning set, which is what keeps its first token early.
DEFAULT_SARVAM_LLM_MODEL = "sarvam-105b-conversations"

# gpt-4.1-nano rather than the previous gpt-4o-mini default: same vendor
# family, but 0.818s p50 against 1.816s on the same measurement.
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4.1-nano"

# A spoken reply is listened to, not skimmed, so this is a backstop against a
# monologue rather than a shaping tool — the system prompt does the shaping.
MAX_RESPONSE_TOKENS = 300

DEFAULT_SARVAM_VOICE = "shubh"
DEFAULT_SARVAM_TTS_MODEL = "bulbul:v3"


@dataclass
class _RunningBot:
    task: asyncio.Task[Any]
    runner: WorkerRunner
    joined: asyncio.Event = field(default_factory=asyncio.Event)


def _require_env(*names: str) -> None:
    missing = [n for n in names if not os.getenv(n, "").strip()]
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))


def _build_llm() -> LLMService:
    """Create the turn-loop LLM for the configured provider."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()

    if provider == "sarvam":
        _require_env("SARVAM_API_KEY")
        model = os.getenv("SARVAM_LLM_MODEL", DEFAULT_SARVAM_LLM_MODEL)
        logger.info("llm provider=sarvam model={}", model)
        return SarvamLLMService(
            api_key=os.environ["SARVAM_API_KEY"],
            settings=SarvamLLMService.Settings(
                model=model,
                system_instruction=SYSTEM_INSTRUCTION,
                max_tokens=MAX_RESPONSE_TOKENS,
            ),
        )

    if provider == "openrouter":
        _require_env("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        logger.info("llm provider=openrouter model={}", model)
        return OpenRouterLLMService(
            api_key=os.environ["OPENROUTER_API_KEY"],
            settings=OpenRouterLLMService.Settings(
                model=model,
                system_instruction=SYSTEM_INSTRUCTION,
                max_tokens=MAX_RESPONSE_TOKENS,
            ),
        )

    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{provider}'. Expected 'sarvam' or 'openrouter'."
    )


def _remote_participant_count(transport: DailyTransport) -> int:
    """Count everyone in the room who is not the bot itself."""
    try:
        participants = transport.participants()
    except Exception:  # noqa: BLE001 — client already torn down
        return 0
    return sum(1 for key in participants if key != "local")


def _log_latency_summary(session_id: str, samples: list[float]) -> None:
    """Log one headline latency line per call, so runs can be compared."""
    if not samples:
        return
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    logger.info(
        "call latency summary session_id={} turns={} p50={:.3f}s p95={:.3f}s "
        "min={:.3f}s max={:.3f}s",
        session_id,
        len(ordered),
        statistics.median(ordered),
        p95,
        ordered[0],
        ordered[-1],
    )


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

    # Official pattern: pipeline (Silero) drives turn boundaries; Sarvam
    # receives speech_start/speech_end. See voice-sarvam-realtime.py.
    stt = SarvamRealtimeSTTService(
        api_key=sarvam_key,
        endpointing="manual",
        settings=SarvamRealtimeSTTService.Settings(
            language_code=language_code,
            stream_type="balanced",
        ),
    )

    llm = _build_llm()

    tts = SarvamTTSService(
        api_key=sarvam_key,
        settings=SarvamTTSService.Settings(
            model=os.getenv("SARVAM_TTS_MODEL", DEFAULT_SARVAM_TTS_MODEL),
            voice=os.getenv("SARVAM_VOICE", DEFAULT_SARVAM_VOICE),
            # Keep the spoken language in step with what we ask Sarvam to hear.
            language=language_code,
        ),
    )

    # One financial state per call. Every mutation pushes a fresh snapshot to
    # the client, so the cards are always a view of the same numbers the agent
    # is talking about rather than a second copy that can drift.
    async def push_state(payload: dict) -> None:
        # `worker` is defined further down; this only ever runs from a tool
        # handler, which cannot fire before the pipeline is up.
        await worker.queue_frames(
            [RTVIServerMessageFrame(data={"type": "finance_state", "state": payload})]
        )

    finance = FinanceTools(on_change=push_state)

    context = LLMContext(tools=finance.schemas())
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_idle_timeout=USER_IDLE_TIMEOUT_SECS,
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

    # The number that decides whether the agent feels alive: the gap between the
    # user falling silent and Kubera making a sound. Pipecat measures it and,
    # with enable_metrics on, attributes it part by part — including function
    # call time once tools are in the loop.
    latency = UserBotLatencyObserver()
    turn_latencies: list[float] = []

    @latency.event_handler("on_latency_measured")
    async def on_latency_measured(observer, latency_seconds: float):
        turn_latencies.append(latency_seconds)
        logger.info(
            "turn latency session_id={} secs={:.3f}", session_id, latency_seconds
        )

    @latency.event_handler("on_latency_breakdown")
    async def on_latency_breakdown(observer, breakdown):
        for line in breakdown.turn_contribution_lines():
            logger.info("turn latency session_id={} | {}", session_id, line)

    @latency.event_handler("on_first_bot_speech_latency")
    async def on_first_bot_speech_latency(observer, latency_seconds: float):
        logger.info(
            "greeting latency session_id={} secs={:.3f}", session_id, latency_seconds
        )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[latency],
        idle_timeout_secs=PIPELINE_IDLE_TIMEOUT_SECS,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )

    await runner.add_workers(worker)

    greeted = False
    greeting_watchdog: asyncio.Task[Any] | None = None
    spoke_at_least_once = False
    idle_nudges_sent = 0

    async def _greeting_fallback() -> None:
        """Speak a fixed greeting if the LLM one never reaches TTS."""
        try:
            await asyncio.sleep(GREETING_TIMEOUT_SECS)
        except asyncio.CancelledError:
            return
        if spoke_at_least_once:
            return
        logger.warning(
            "greeting did not reach TTS in {}s, speaking fallback session_id={}",
            GREETING_TIMEOUT_SECS,
            session_id,
        )
        await worker.queue_frames([TTSSpeakFrame(text=GREETING_FALLBACK)])

    async def greet() -> None:
        """Kick off the conversation exactly once per session."""
        nonlocal greeted, greeting_watchdog
        if greeted:
            return
        greeted = True
        logger.info("greeting user session_id={}", session_id)
        context.add_message({"role": "developer", "content": GREETING_PROMPT})
        await worker.queue_frames([LLMRunFrame()])
        greeting_watchdog = asyncio.create_task(_greeting_fallback())

    @tts.event_handler("on_tts_request")
    async def on_tts_request(service, context_id: str, text: str):
        nonlocal spoke_at_least_once
        spoke_at_least_once = True
        if greeting_watchdog and not greeting_watchdog.done():
            greeting_watchdog.cancel()

    @transport.event_handler("on_joined")
    async def on_joined(transport, data):
        logger.info("bot joined room session_id={}", session_id)
        joined.set()
        # The user can win the race into the room. Daily only reports joins that
        # happen after ours, so anyone already here needs greeting from here.
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
        # Only tear down once the room is actually empty of humans.
        if remaining == 0:
            await runner.cancel()

    @user_aggregator.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(aggregator):
        nonlocal idle_nudges_sent
        if not greeted or idle_nudges_sent >= len(IDLE_NUDGES):
            return
        nudge = IDLE_NUDGES[idle_nudges_sent]
        idle_nudges_sent += 1
        last = idle_nudges_sent >= len(IDLE_NUDGES)
        logger.info(
            "user idle session_id={} nudge={} last={}", session_id, idle_nudges_sent, last
        )
        frames: list[Any] = [TTSSpeakFrame(text=nudge)]
        if last:
            # Tell the client this is a deliberate sign-off, not a dropped call,
            # then let the goodbye finish playing before the pipeline ends.
            frames.append(
                RTVIServerMessageFrame(
                    data={"type": "session_end", "reason": "idle"}
                )
            )
            frames.append(EndWorkerFrame(reason="user idle"))
        await worker.queue_frames(frames)

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
    try:
        await runner.run()
    finally:
        if greeting_watchdog and not greeting_watchdog.done():
            greeting_watchdog.cancel()
        _log_latency_summary(session_id, turn_latencies)
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
        # Unblock anyone waiting on a join that is never going to happen.
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
