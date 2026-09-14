"""Tunable knobs. Defaults match the measured demo; override in .env."""

from __future__ import annotations

import os

# /v1 only — gemma4/glm5.2 are /v2 and break tools.
SARVAM_CONVERSATIONS = "sarvam-105b-conversations"


def env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return float(raw)


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def llm_model() -> str:
    return env_str("SARVAM_LLM_MODEL", SARVAM_CONVERSATIONS)


def summary_model() -> str:
    return env_str("SARVAM_SUMMARY_MODEL", SARVAM_CONVERSATIONS)


def tts_temperature() -> float:
    return env_float("SARVAM_TTS_TEMPERATURE", 0.8)


def pipeline_idle_secs() -> float:
    return env_float("PIPELINE_IDLE_SECS", 120.0)


def bot_join_timeout_secs() -> float:
    return env_float("BOT_JOIN_TIMEOUT_SECS", 15.0)


def daily_room_ttl_secs() -> int:
    return env_int("DAILY_ROOM_TTL_SECS", 3600)


def vad_confidence() -> float:
    return env_float("VAD_CONFIDENCE", 0.7)


def vad_start_secs() -> float:
    return env_float("VAD_START_SECS", 0.1)


def vad_stop_secs() -> float:
    return env_float("VAD_STOP_SECS", 1.5)
