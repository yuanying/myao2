"""Tests for LLMClient."""

from unittest.mock import MagicMock, patch

import pytest
from litellm.exceptions import AuthenticationError, RateLimitError

from myao2.config import LLMConfig
from myao2.infrastructure.llm import (
    LLMAuthenticationError,
    LLMClient,
    LLMError,
    LLMRateLimitError,
)


class TestLLMClient:
    """LLMClient tests."""

    @pytest.fixture
    def config(self) -> LLMConfig:
        """Create LLM config."""
        return LLMConfig(
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
        )

    @pytest.fixture
    def client(self, config: LLMConfig) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(config=config)

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock LiteLLM response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Hello! How can I help you?"
        return response

    def test_complete_success(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test successful completion."""
        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            result = client.complete([{"role": "user", "content": "Hello"}])

            assert result == "Hello! How can I help you?"
            mock_completion.assert_called_once()

    def test_complete_applies_config(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test that config parameters are applied."""
        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            client.complete([{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o"
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 1000

    def test_complete_kwargs_override(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test that kwargs can override config."""
        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            client.complete(
                [{"role": "user", "content": "Hello"}],
                max_tokens=500,
                temperature=0.5,
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["max_tokens"] == 500
            assert call_kwargs["temperature"] == 0.5

    def test_complete_authentication_error(self, client: LLMClient) -> None:
        """Test that authentication errors are converted."""
        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = AuthenticationError(
                message="Invalid API key",
                llm_provider="openai",
                model="gpt-4o",
            )

            with pytest.raises(LLMAuthenticationError):
                client.complete([{"role": "user", "content": "Hello"}])

    def test_complete_rate_limit_error(self, client: LLMClient) -> None:
        """Test that rate limit errors are converted."""
        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = RateLimitError(
                message="Rate limit exceeded",
                llm_provider="openai",
                model="gpt-4o",
            )

            with pytest.raises(LLMRateLimitError):
                client.complete([{"role": "user", "content": "Hello"}])

    def test_complete_generic_error(self, client: LLMClient) -> None:
        """Test that other errors are converted to LLMError."""
        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("Unknown error")

            with pytest.raises(LLMError):
                client.complete([{"role": "user", "content": "Hello"}])
