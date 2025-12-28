"""Tests for LiteLLMResponseGenerator."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.infrastructure.llm import LiteLLMResponseGenerator, LLMClient, LLMError


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = "Hello! Nice to meet you."
    return client


@pytest.fixture
def generator(mock_client: MagicMock) -> LiteLLMResponseGenerator:
    """Create generator instance."""
    return LiteLLMResponseGenerator(client=mock_client)


@pytest.fixture
def persona_config() -> PersonaConfig:
    """Create test persona config."""
    return PersonaConfig(
        name="myao",
        system_prompt="You are a friendly bot.",
    )


@pytest.fixture
def sample_user() -> User:
    """Create test user."""
    return User(id="U123", name="testuser", is_bot=False)


@pytest.fixture
def sample_bot() -> User:
    """Create test bot."""
    return User(id="B123", name="myao", is_bot=True)


@pytest.fixture
def sample_channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def user_message(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> Message:
    """Create test user message."""
    return Message(
        id="1234567890.123456",
        channel=sample_channel,
        user=sample_user,
        text="Hello",
        timestamp=timestamp,
        thread_ts=None,
        mentions=[],
    )


@pytest.fixture
def sample_context(persona_config: PersonaConfig) -> Context:
    """Create test context with no history."""
    return Context(
        persona=persona_config,
        conversation_history=[],
    )


class TestLiteLLMResponseGenerator:
    """LiteLLMResponseGenerator tests."""

    def test_generate_basic(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test basic response generation."""
        result = generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        assert result == "Hello! Nice to meet you."
        mock_client.complete.assert_called_once()

    def test_generate_uses_context_to_build_messages(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that Context.build_messages_for_llm is used."""
        generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should match Context.build_messages_for_llm output
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a friendly bot."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_generate_with_conversation_history(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_bot: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test generation with conversation history."""
        history = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hi there!",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="1234567890.000002",
                channel=sample_channel,
                user=sample_bot,
                text="Hello! How can I help?",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=history,
        )

        generator.generate(
            user_message=user_message,
            context=context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # system + 2 history + current user message
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hi there!"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Hello! How can I help?"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Hello"

    def test_generate_propagates_error(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that LLM errors are propagated."""
        mock_client.complete.side_effect = LLMError("API error")

        with pytest.raises(LLMError):
            generator.generate(
                user_message=user_message,
                context=sample_context,
            )
