"""Record settled conversation turns into the local store.

Two taps share one writer so user STT and agent LLM text can sit in different
places on the linear pipeline without a second source of truth.
"""

from __future__ import annotations

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    InterimTranscriptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

import store


class TranscriptWriter:
    """Monotonic seq + fire-and-forget appends for one session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._seq = 0

    async def add(self, role: str, text: str, *, interrupted: bool = False) -> None:
        text = text.strip()
        if not text:
            return
        self._seq += 1
        await store.append_turn(
            session_id=self.session_id,
            seq=self._seq,
            role=role,
            text=text,
            interrupted=interrupted,
        )


class UserTranscriptTap(FrameProcessor):
    """After STT: persist final user utterances."""

    def __init__(self, writer: TranscriptWriter) -> None:
        super().__init__()
        self._writer = writer

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, InterimTranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            # Settled even when `finalized` is still False (default).
            await self._writer.add("user", frame.text or "")

        await self.push_frame(frame, direction)


class AgentTranscriptTap(FrameProcessor):
    """After LLM: persist one agent turn per full response."""

    def __init__(self, writer: TranscriptWriter) -> None:
        super().__init__()
        self._writer = writer
        self._parts: list[str] = []
        self._open = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._parts = []
            self._open = True
        elif isinstance(frame, LLMTextFrame) and self._open:
            if frame.text:
                self._parts.append(frame.text)
        elif isinstance(frame, InterruptionFrame) and self._open:
            await self._flush(interrupted=True)
        elif isinstance(frame, LLMFullResponseEndFrame) and self._open:
            await self._flush(interrupted=False)

        await self.push_frame(frame, direction)

    async def _flush(self, *, interrupted: bool) -> None:
        text = "".join(self._parts)
        self._parts = []
        self._open = False
        await self._writer.add("agent", text, interrupted=interrupted)
