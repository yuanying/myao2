"""Pydantic models for strands-agents structured output."""

from pydantic import BaseModel, Field


class JudgmentOutput(BaseModel):
    """Output model for response judgment.

    Used for strands-agents Structured Output to ensure type-safe JSON.
    """

    should_respond: bool = Field(description="Whether to respond")
    reason: str = Field(description="Reason for the judgment")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level (0.0-1.0)",
    )
