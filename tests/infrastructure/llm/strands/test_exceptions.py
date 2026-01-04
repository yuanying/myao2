"""Tests for strands exception mapping."""

import pytest

from myao2.infrastructure.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from myao2.infrastructure.llm.strands import map_strands_exception


class TestMapStrandsException:
    """Tests for map_strands_exception function."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "Authentication failed",
            "Invalid API key provided",
            "Unauthorized access",
            "authentication error occurred",
            "api key is invalid",
        ],
    )
    def test_map_authentication_error(self, error_message: str) -> None:
        """Test mapping of authentication errors."""
        exception = Exception(error_message)
        result = map_strands_exception(exception)

        assert isinstance(result, LLMAuthenticationError)
        assert str(result) == error_message

    @pytest.mark.parametrize(
        "error_message",
        [
            "Rate limit exceeded",
            "Too many requests",
            "rate limit reached",
            "too many requests per minute",
        ],
    )
    def test_map_rate_limit_error(self, error_message: str) -> None:
        """Test mapping of rate limit errors."""
        exception = Exception(error_message)
        result = map_strands_exception(exception)

        assert isinstance(result, LLMRateLimitError)
        assert str(result) == error_message

    @pytest.mark.parametrize(
        "error_message",
        [
            "Request timeout",
            "Connection timed out",
            "timeout error",
            "Request timed out after 30 seconds",
        ],
    )
    def test_map_timeout_error(self, error_message: str) -> None:
        """Test mapping of timeout errors."""
        exception = Exception(error_message)
        result = map_strands_exception(exception)

        assert isinstance(result, LLMTimeoutError)
        assert str(result) == error_message

    @pytest.mark.parametrize(
        "error_message",
        [
            "Model not found",
            "Invalid model specified",
            "Model does not exist",
            "model not found: gpt-5",
            "invalid model id",
        ],
    )
    def test_map_model_not_found_error(self, error_message: str) -> None:
        """Test mapping of model not found errors."""
        exception = Exception(error_message)
        result = map_strands_exception(exception)

        assert isinstance(result, LLMModelNotFoundError)
        assert str(result) == error_message

    @pytest.mark.parametrize(
        "error_message",
        [
            "Unknown error occurred",
            "Something went wrong",
            "Internal server error",
            "Connection refused",
        ],
    )
    def test_map_generic_error(self, error_message: str) -> None:
        """Test mapping of generic errors."""
        exception = Exception(error_message)
        result = map_strands_exception(exception)

        assert isinstance(result, LLMError)
        assert not isinstance(result, LLMAuthenticationError)
        assert not isinstance(result, LLMRateLimitError)
        assert not isinstance(result, LLMTimeoutError)
        assert not isinstance(result, LLMModelNotFoundError)
        assert str(result) == error_message

    def test_preserves_original_message(self) -> None:
        """Test that original error message is preserved."""
        original_message = "Detailed error: API key 'sk-xxx' is invalid"
        exception = Exception(original_message)
        result = map_strands_exception(exception)

        assert str(result) == original_message
