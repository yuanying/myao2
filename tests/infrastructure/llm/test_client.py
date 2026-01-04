"""Tests for LLMClient."""

from unittest.mock import AsyncMock, MagicMock, patch

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

    async def test_complete_success(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test successful completion."""
        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ) as mock_completion:
            result = await client.complete([{"role": "user", "content": "Hello"}])

            assert result == "Hello! How can I help you?"
            mock_completion.assert_awaited_once()

    async def test_complete_applies_config(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test that config parameters are applied."""
        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ) as mock_completion:
            await client.complete([{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o"
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 1000

    async def test_complete_kwargs_override(
        self, client: LLMClient, mock_response: MagicMock
    ) -> None:
        """Test that kwargs can override config."""
        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ) as mock_completion:
            await client.complete(
                [{"role": "user", "content": "Hello"}],
                max_tokens=500,
                temperature=0.5,
            )

            call_kwargs = mock_completion.call_args.kwargs
            assert call_kwargs["max_tokens"] == 500
            assert call_kwargs["temperature"] == 0.5

    async def test_complete_authentication_error(self, client: LLMClient) -> None:
        """Test that authentication errors are converted."""
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = AuthenticationError(
                message="Invalid API key",
                llm_provider="openai",
                model="gpt-4o",
            )

            with pytest.raises(LLMAuthenticationError):
                await client.complete([{"role": "user", "content": "Hello"}])

    async def test_complete_rate_limit_error(self, client: LLMClient) -> None:
        """Test that rate limit errors are converted."""
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = RateLimitError(
                message="Rate limit exceeded",
                llm_provider="openai",
                model="gpt-4o",
            )

            with pytest.raises(LLMRateLimitError):
                await client.complete([{"role": "user", "content": "Hello"}])

    async def test_complete_generic_error(self, client: LLMClient) -> None:
        """Test that other errors are converted to LLMError."""
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = Exception("Unknown error")

            with pytest.raises(LLMError):
                await client.complete([{"role": "user", "content": "Hello"}])


class TestLLMClientLogging:
    """LLMClient logging tests."""

    @pytest.fixture
    def config(self) -> LLMConfig:
        """Create LLM config."""
        return LLMConfig(
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
        )

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock LiteLLM response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Test response"
        return response

    async def test_complete_logs_at_info_when_debug_llm_messages_true(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test logs at INFO level when debug_llm_messages=True."""
        import logging

        caplog.set_level(logging.INFO)
        client = LLMClient(config=config, debug_llm_messages=True)

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete(
                [{"role": "system", "content": "You are helpful."}],
                caller="test_caller",
            )

        # Check request log
        assert "=== LLM Request [test_caller] ===" in caplog.text
        assert "Model: gpt-4o" in caplog.text
        assert "[0] role=system" in caplog.text
        assert "content: You are helpful." in caplog.text
        # Check response log
        assert "=== LLM Response [test_caller] ===" in caplog.text
        assert "Test response" in caplog.text

    async def test_complete_logs_at_debug_when_debug_disabled_and_debug_enabled(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test logs at DEBUG level when debug_llm_messages=False and DEBUG."""
        import logging

        caplog.set_level(logging.DEBUG)
        client = LLMClient(config=config, debug_llm_messages=False)

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete(
                [{"role": "user", "content": "Hello"}],
                caller="test_caller",
            )

        # Check that logs are present (at DEBUG level)
        assert "=== LLM Request [test_caller] ===" in caplog.text
        assert "=== LLM Response [test_caller] ===" in caplog.text

    async def test_complete_no_logs_when_debug_disabled_and_info_level(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test no logs when debug_llm_messages=False and level is INFO."""
        import logging

        caplog.set_level(logging.INFO)
        client = LLMClient(config=config, debug_llm_messages=False)

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete(
                [{"role": "user", "content": "Hello"}],
                caller="test_caller",
            )

        # Request/Response logs should NOT be present
        assert "=== LLM Request" not in caplog.text
        assert "=== LLM Response" not in caplog.text

    async def test_complete_logs_include_caller(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that caller is included in log messages."""
        import logging

        caplog.set_level(logging.INFO)
        client = LLMClient(config=config, debug_llm_messages=True)

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete(
                [{"role": "user", "content": "Hello"}],
                caller="response_generator",
            )

        assert "[response_generator]" in caplog.text

    async def test_complete_logs_default_caller_when_not_specified(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that default caller 'unknown' is used when not specified."""
        import logging

        caplog.set_level(logging.INFO)
        client = LLMClient(config=config, debug_llm_messages=True)

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete([{"role": "user", "content": "Hello"}])

        assert "[unknown]" in caplog.text

    async def test_complete_logs_multiple_messages(
        self,
        config: LLMConfig,
        mock_response: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that all messages are logged."""
        import logging

        caplog.set_level(logging.INFO)
        client = LLMClient(config=config, debug_llm_messages=True)

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
        ]

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            await client.complete(messages, caller="test")

        assert "[0] role=system" in caplog.text
        assert "content: System prompt" in caplog.text
        assert "[1] role=user" in caplog.text
        assert "content: User message" in caplog.text
