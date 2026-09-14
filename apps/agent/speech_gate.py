"""Hold a short audio pre-roll and open the STT gate on VAD speech.

Sarvam manual endpointing only transcribes after speech_start, so audio
that reaches STT before that frame loses the first word. This processor
emits speech_start, then the pre-roll, then live audio, and drops
non-speech so tones never become transcripts.
"""

from __future__ import annotations

from collections import deque

from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADState
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    StartFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SpeechAudioGate(FrameProcessor):
    def __init__(self, vad_analyzer: VADAnalyzer, *, prefix_secs: float = 0.3):
        super().__init__()
        self._vad = vad_analyzer
        self._prefix_secs = prefix_secs
        self._speaking = False
        self._prefix: deque[InputAudioRawFrame] = deque()
        self._prefix_bytes = 0
        self._prefix_limit = 0

    def _set_rate(self, sample_rate: int, num_channels: int = 1) -> None:
        if self._vad.sample_rate != sample_rate:
            self._vad.set_sample_rate(sample_rate)
        self._prefix_limit = int(
            self._prefix_secs * sample_rate * 2 * num_channels
        )

    def _hold(self, frame: InputAudioRawFrame) -> None:
        self._prefix.append(frame)
        self._prefix_bytes += len(frame.audio)
        while self._prefix_limit and self._prefix_bytes > self._prefix_limit:
            dropped = self._prefix.popleft()
            self._prefix_bytes -= len(dropped.audio)

    def _clear_prefix(self) -> None:
        self._prefix.clear()
        self._prefix_bytes = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, StartFrame):
            if frame.audio_in_sample_rate:
                self._set_rate(frame.audio_in_sample_rate)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            if self._speaking:
                self._speaking = False
                await self.push_frame(
                    VADUserStoppedSpeakingFrame(stop_secs=self._vad.params.stop_secs),
                    direction,
                )
            self._clear_prefix()
            await self.push_frame(frame, direction)
            return

        if not isinstance(frame, InputAudioRawFrame):
            await self.push_frame(frame, direction)
            return

        if self._vad.sample_rate == 0:
            self._set_rate(frame.sample_rate, frame.num_channels)

        state = await self._vad.analyze_audio(frame.audio)

        if not self._speaking:
            self._hold(frame)
            if state == VADState.SPEAKING:
                self._speaking = True
                await self.push_frame(
                    VADUserStartedSpeakingFrame(
                        start_secs=self._vad.params.start_secs
                    ),
                    direction,
                )
                for held in self._prefix:
                    await self.push_frame(held, direction)
                self._clear_prefix()
            return

        await self.push_frame(frame, direction)
        if state == VADState.QUIET:
            self._speaking = False
            await self.push_frame(
                VADUserStoppedSpeakingFrame(stop_secs=self._vad.params.stop_secs),
                direction,
            )
            self._clear_prefix()
