"""Pipecat context summarization: cheap model, every N turns."""

from __future__ import annotations

from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregatorParams,
)
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.utils.context.llm_context_summarization import (
    LLMAutoContextSummarizationConfig,
    LLMContextSummaryConfig,
)

from prompts import SUMMARY_PROMPT
from settings import SARVAM_CONVERSATIONS, summary_model

SUMMARY_EVERY_TURNS = 6  # turns; max_unsummarized = turns * 2 messages
DEFAULT_SUMMARY_MODEL = SARVAM_CONVERSATIONS


def auto_summarization_config(
    *, llm: SarvamLLMService | None = None
) -> LLMAutoContextSummarizationConfig:
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
    summarizer = SarvamLLMService(
        api_key=api_key,
        settings=SarvamLLMService.Settings(
            model=summary_model(),
        ),
    )
    return LLMAssistantAggregatorParams(
        enable_auto_context_summarization=True,
        auto_context_summarization_config=auto_summarization_config(llm=summarizer),
    )
