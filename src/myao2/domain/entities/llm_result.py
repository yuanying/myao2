"""LLM result entities."""

from dataclasses import dataclass

from myao2.domain.entities.llm_metrics import LLMMetrics


@dataclass(frozen=True)
class GenerationResult:
    """Response generation result.

    Represents the result of generating a response using an LLM.

    Attributes:
        text: The generated response text.
        metrics: LLM invocation metrics (optional).
    """

    text: str
    metrics: LLMMetrics | None = None


@dataclass(frozen=True)
class SummarizationResult:
    """Memory summarization result.

    Represents the result of generating a memory summary using an LLM.

    Attributes:
        text: The generated summary text.
        metrics: LLM invocation metrics (optional).
    """

    text: str
    metrics: LLMMetrics | None = None
