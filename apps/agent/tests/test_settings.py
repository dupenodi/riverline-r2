"""Env knobs fall back to the measured demo defaults."""

import os

from settings import (
    SARVAM_CONVERSATIONS,
    bot_join_timeout_secs,
    daily_room_ttl_secs,
    llm_model,
    pipeline_idle_secs,
    summary_model,
    vad_stop_secs,
)


def test_defaults() -> None:
    os.environ.pop("SARVAM_LLM_MODEL", None)
    os.environ.pop("PIPELINE_IDLE_SECS", None)
    os.environ.pop("DAILY_ROOM_TTL_SECS", None)
    assert llm_model() == SARVAM_CONVERSATIONS
    assert summary_model() == SARVAM_CONVERSATIONS
    assert pipeline_idle_secs() == 120.0
    assert bot_join_timeout_secs() == 15.0
    assert daily_room_ttl_secs() == 3600
    assert vad_stop_secs() == 1.5


def test_override() -> None:
    os.environ["SARVAM_LLM_MODEL"] = "other-model"
    os.environ["VAD_STOP_SECS"] = "2"
    try:
        assert llm_model() == "other-model"
        assert vad_stop_secs() == 2.0
    finally:
        os.environ.pop("SARVAM_LLM_MODEL", None)
        os.environ.pop("VAD_STOP_SECS", None)
