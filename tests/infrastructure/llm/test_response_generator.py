"""Tests for LiteLLMResponseGenerator."""

from unittest.mock import MagicMock

import pytest

from myao2.infrastructure.llm import LiteLLMResponseGenerator, LLMClient, LLMError


class TestLiteLLMResponseGenerator:
    """LiteLLMResponseGenerator tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock LLMClient."""
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = "Hello! Nice to meet you."
        return client

    @pytest.fixture
    def generator(self, mock_client: MagicMock) -> LiteLLMResponseGenerator:
        """Create generator instance."""
        return LiteLLMResponseGenerator(client=mock_client)

    def test_generate_basic(
        self, generator: LiteLLMResponseGenerator, mock_client: MagicMock
    ) -> None:
        """Test basic response generation."""
        result = generator.generate(
            user_message="Hello",
            system_prompt="You are a friendly bot.",
        )

        assert result == "Hello! Nice to meet you."
        mock_client.complete.assert_called_once()

    def test_generate_applies_system_prompt(
        self, generator: LiteLLMResponseGenerator, mock_client: MagicMock
    ) -> None:
        """Test that system prompt is included in messages."""
        generator.generate(
            user_message="Hello",
            system_prompt="You are a friendly bot.",
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a friendly bot."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_generate_propagates_error(
        self, generator: LiteLLMResponseGenerator, mock_client: MagicMock
    ) -> None:
        """Test that LLM errors are propagated."""
        mock_client.complete.side_effect = LLMError("API error")

        with pytest.raises(LLMError):
            generator.generate(
                user_message="Hello",
                system_prompt="You are a friendly bot.",
            )
