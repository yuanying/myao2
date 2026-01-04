"""Exception mapping utilities for strands-agents."""

from myao2.infrastructure.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def map_strands_exception(e: Exception) -> LLMError:
    """Map strands-agents exceptions to domain exceptions.

    Args:
        e: Exception from strands-agents

    Returns:
        Corresponding domain exception
    """
    error_message = str(e)
    error_message_lower = error_message.lower()

    # Authentication error detection
    if any(
        pattern in error_message_lower
        for pattern in ["authentication", "api key", "unauthorized"]
    ):
        return LLMAuthenticationError(error_message)

    # Rate limit error detection
    if any(
        pattern in error_message_lower
        for pattern in ["rate limit", "too many requests"]
    ):
        return LLMRateLimitError(error_message)

    # Timeout error detection
    if any(pattern in error_message_lower for pattern in ["timeout", "timed out"]):
        return LLMTimeoutError(error_message)

    # Model not found error detection
    if any(
        pattern in error_message_lower
        for pattern in ["model not found", "invalid model", "does not exist"]
    ):
        return LLMModelNotFoundError(error_message)

    # Generic error
    return LLMError(error_message)
