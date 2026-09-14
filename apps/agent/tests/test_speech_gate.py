"""SpeechAudioGate holds pre-roll and only opens STT on speech."""

from __future__ import annotations

import pytest
from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADParams, VADState
from pipecat.frames.frames import (
    InputAudioRawFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from speech_gate import SpeechAudioGate


class FakeVAD(VADAnalyzer):
    def __init__(self) -> None:
        super().__init__(sample_rate=16000, params=VADParams(start_secs=0.1, stop_secs=1.5))
        self.state = VADState.QUIET

    def num_frames_required(self) -> int:
        return 1

    def voice_confidence(self, buffer: bytes) -> float:
        return 0.0

    async def analyze_audio(self, buffer: bytes) -> VADState:
        return self.state


def _pcm(n: int = 320) -> InputAudioRawFrame:
    return InputAudioRawFrame(audio=b"\x00" * n, sample_rate=16000, num_channels=1)


class _Gate(SpeechAudioGate):
    def __init__(self, vad: FakeVAD) -> None:
        super().__init__(vad, prefix_secs=0.3)
        self.out: list = []

    async def push_frame(self, frame, direction=None):  # noqa: ANN001
        self.out.append(frame)


@pytest.mark.asyncio
async def test_quiet_audio_is_not_forwarded() -> None:
    vad = FakeVAD()
    gate = _Gate(vad)
    down = FrameDirection.DOWNSTREAM
    await gate.process_frame(_pcm(), down)
    await gate.process_frame(_pcm(), down)
    assert gate.out == []


@pytest.mark.asyncio
async def test_speech_emits_start_then_pre_roll() -> None:
    vad = FakeVAD()
    gate = _Gate(vad)
    down = FrameDirection.DOWNSTREAM
    first = _pcm()
    second = _pcm()
    await gate.process_frame(first, down)
    vad.state = VADState.SPEAKING
    await gate.process_frame(second, down)

    assert isinstance(gate.out[0], VADUserStartedSpeakingFrame)
    assert gate.out[1] is first
    assert gate.out[2] is second


@pytest.mark.asyncio
async def test_silence_after_speech_emits_stop() -> None:
    vad = FakeVAD()
    gate = _Gate(vad)
    down = FrameDirection.DOWNSTREAM
    vad.state = VADState.SPEAKING
    await gate.process_frame(_pcm(), down)
    vad.state = VADState.QUIET
    tail = _pcm()
    await gate.process_frame(tail, down)

    assert gate.out[-2] is tail
    assert isinstance(gate.out[-1], VADUserStoppedSpeakingFrame)
