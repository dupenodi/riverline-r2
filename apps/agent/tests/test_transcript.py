"""Unit tests for the pipeline transcript taps."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from transcript import AgentTranscriptTap, TranscriptWriter, UserTranscriptTap


@dataclass
class FakeStore:
    turns: list[dict] = field(default_factory=list)

    async def append_turn(self, **kwargs) -> None:
        self.turns.append(kwargs)


@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    fake_store = FakeStore()
    import transcript as mod

    monkeypatch.setattr(mod, "store", fake_store)
    return fake_store


@pytest.mark.asyncio
async def test_user_tap_records_transcription(fake: FakeStore) -> None:
    from pipecat.frames.frames import TranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection

    writer = TranscriptWriter("s1")
    tap = UserTranscriptTap(writer)
    frame = TranscriptionFrame(text="I have 20k", user_id="u", timestamp="t")
    await tap.process_frame(frame, FrameDirection.DOWNSTREAM)

    assert len(fake.turns) == 1
    assert fake.turns[0]["role"] == "user"
    assert fake.turns[0]["text"] == "I have 20k"
    assert fake.turns[0]["seq"] == 1


@pytest.mark.asyncio
async def test_user_tap_ignores_interim(fake: FakeStore) -> None:
    from pipecat.frames.frames import InterimTranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection

    writer = TranscriptWriter("s1")
    tap = UserTranscriptTap(writer)
    frame = InterimTranscriptionFrame(text="I ha", user_id="u", timestamp="t")
    await tap.process_frame(frame, FrameDirection.DOWNSTREAM)

    assert fake.turns == []


@pytest.mark.asyncio
async def test_agent_tap_aggregates_one_turn(fake: FakeStore) -> None:
    from pipecat.frames.frames import (
        LLMFullResponseEndFrame,
        LLMFullResponseStartFrame,
        LLMTextFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection

    writer = TranscriptWriter("s1")
    tap = AgentTranscriptTap(writer)
    down = FrameDirection.DOWNSTREAM

    await tap.process_frame(LLMFullResponseStartFrame(), down)
    await tap.process_frame(LLMTextFrame(text="Hello "), down)
    await tap.process_frame(LLMTextFrame(text="Priya."), down)
    await tap.process_frame(LLMFullResponseEndFrame(), down)

    assert len(fake.turns) == 1
    assert fake.turns[0]["role"] == "agent"
    assert fake.turns[0]["text"] == "Hello Priya."
    assert fake.turns[0]["interrupted"] is False


@pytest.mark.asyncio
async def test_agent_tap_marks_interruption(fake: FakeStore) -> None:
    from pipecat.frames.frames import (
        InterruptionFrame,
        LLMFullResponseStartFrame,
        LLMTextFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection

    writer = TranscriptWriter("s1")
    tap = AgentTranscriptTap(writer)
    down = FrameDirection.DOWNSTREAM

    await tap.process_frame(LLMFullResponseStartFrame(), down)
    await tap.process_frame(LLMTextFrame(text="So your rent"), down)
    await tap.process_frame(InterruptionFrame(), down)

    assert len(fake.turns) == 1
    assert fake.turns[0]["interrupted"] is True
    assert fake.turns[0]["text"] == "So your rent"
