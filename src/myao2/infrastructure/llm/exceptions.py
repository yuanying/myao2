"""LLM-related exceptions."""


class LLMError(Exception):
    """Base exception for LLM-related errors."""


class LLMRateLimitError(LLMError):
    """Rate limit exceeded error."""


class LLMAuthenticationError(LLMError):
    """Authentication error (invalid API key, etc.)."""


class LLMTimeoutError(LLMError):
    """Timeout error (request took too long)."""


class LLMModelNotFoundError(LLMError):
    """Model not found error (invalid or unsupported model)."""
