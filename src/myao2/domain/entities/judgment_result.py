"""Judgment result entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myao2.domain.entities.llm_metrics import LLMMetrics


@dataclass(frozen=True)
class JudgmentResult:
    """Response judgment result.

    Represents the result of determining whether the bot should respond
    to a conversation.

    Attributes:
        should_respond: Whether the bot should respond.
        reason: The reason for the judgment (for debugging/logging).
        confidence: Confidence level (0.0 - 1.0, optional).
        metrics: LLM invocation metrics (optional).
    """

    should_respond: bool
    reason: str
    confidence: float = 1.0
    metrics: LLMMetrics | None = None
