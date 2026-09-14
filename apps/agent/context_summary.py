"""Pipecat context summarization: cheap model, every N turns."""

from __future__ import annotations

import os

from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregatorParams,
)
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.utils.context.llm_context_summarization import (
    LLMAutoContextSummarizationConfig,
    LLMContextSummaryConfig,
)

from prompts import SUMMARY_PROMPT

# One turn = user + assistant. 6 turns → 12 messages.
SUMMARY_EVERY_TURNS = 6
# gemma4 / glm5.2 need Sarvam /v2 (beta). Conversations is /v1 and works.
DEFAULT_SUMMARY_MODEL = "sarvam-105b-conversations"


def auto_summarization_config(
    *, llm: SarvamLLMService | None = None
) -> LLMAutoContextSummarizationConfig:
    """Compress older history; keep the last two turns raw."""
    return LLMAutoContextSummarizationConfig(
        max_context_tokens=3500,
        max_unsummarized_messages=SUMMARY_EVERY_TURNS * 2,
        summary_config=LLMContextSummaryConfig(
            target_context_tokens=400,
            min_messages_after_summary=4,
            summarization_prompt=SUMMARY_PROMPT,
            llm=llm,
        ),
    )


def assistant_aggregator_params(*, api_key: str) -> LLMAssistantAggregatorParams:
    """Enable auto-summarization on a dedicated Sarvam /v1 model."""
    summarizer = SarvamLLMService(
        api_key=api_key,
        settings=SarvamLLMService.Settings(
            model=os.getenv("SARVAM_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL),
        ),
    )
    return LLMAssistantAggregatorParams(
        enable_auto_context_summarization=True,
        auto_context_summarization_config=auto_summarization_config(llm=summarizer),
    )
