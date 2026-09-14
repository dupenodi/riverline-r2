"""Summarization fires every 6 turns on a dedicated cheap model."""

from context_summary import (
    DEFAULT_SUMMARY_MODEL,
    SUMMARY_EVERY_TURNS,
    auto_summarization_config,
)
from prompts import SUMMARY_PROMPT


def test_six_turns_means_twelve_messages() -> None:
    config = auto_summarization_config()
    assert SUMMARY_EVERY_TURNS == 6
    assert config.max_unsummarized_messages == 12
    assert config.summary_config.min_messages_after_summary == 4
    assert config.summary_config.llm is None


def test_summary_uses_v1_conversations_model() -> None:
    assert DEFAULT_SUMMARY_MODEL == "sarvam-105b-conversations"


def test_summary_prompt_does_not_invent_numbers() -> None:
    assert "Do not invent numbers" in SUMMARY_PROMPT
    assert auto_summarization_config().summary_config.summarization_prompt == SUMMARY_PROMPT
