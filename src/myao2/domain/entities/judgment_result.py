"""Judgment result entity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgmentResult:
    """Response judgment result.

    Represents the result of determining whether the bot should respond
    to a conversation.

    Attributes:
        should_respond: Whether the bot should respond.
        reason: The reason for the judgment (for debugging/logging).
        confidence: Confidence level (0.0 - 1.0, optional).
    """

    should_respond: bool
    reason: str
    confidence: float = 1.0
