"""Tests for LiteLLMResponseGenerator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMessages
from myao2.infrastructure.llm import LiteLLMResponseGenerator, LLMClient, LLMError


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.complete = AsyncMock(return_value="Hello! Nice to meet you.")
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


def create_empty_channel_messages(
    channel_id: str = "C123", channel_name: str = "general"
) -> ChannelMessages:
    """Create an empty ChannelMessages instance."""
    return ChannelMessages(channel_id=channel_id, channel_name=channel_name)


@pytest.fixture
def sample_context(persona_config: PersonaConfig) -> Context:
    """Create test context with no history."""
    return Context(
        persona=persona_config,
        conversation_history=create_empty_channel_messages(),
    )


class TestLiteLLMResponseGenerator:
    """LiteLLMResponseGenerator tests."""

    async def test_generate_basic(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test basic response generation."""
        result = await generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        assert result == "Hello! Nice to meet you."
        mock_client.complete.assert_awaited_once()

    async def test_generate_sends_only_system_message(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that only system message is sent to LLM."""
        await generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Only one system message should be sent
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    async def test_generate_includes_persona_in_system_prompt(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that persona system prompt is included."""
        await generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        assert "You are a friendly bot." in system_content

    async def test_generate_includes_current_message_in_system_prompt(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that current user message is included in system prompt."""
        await generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        assert "返答すべきメッセージ" in system_content
        assert "testuser: Hello" in system_content
        assert "2024-01-01 12:00:00" in system_content

    async def test_generate_includes_conversation_history(
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
        """Test generation with conversation history included in system prompt."""
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
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=history,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        await generator.generate(
            user_message=user_message,
            context=context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Only one system message
        assert len(messages) == 1
        # History should be in system prompt
        assert "会話履歴" in system_content
        assert "testuser: Hi there!" in system_content
        assert "myao: Hello! How can I help?" in system_content

    async def test_generate_includes_instruction_at_end(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that instruction is included at the end of system prompt."""
        await generator.generate(
            user_message=user_message,
            context=sample_context,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        assert "上記の会話履歴と参考情報を元に" in system_content
        assert "自然な返答を生成してください" in system_content

    async def test_generate_propagates_error(
        self,
        generator: LiteLLMResponseGenerator,
        mock_client: MagicMock,
        user_message: Message,
        sample_context: Context,
    ) -> None:
        """Test that LLM errors are propagated."""
        mock_client.complete.side_effect = LLMError("API error")

        with pytest.raises(LLMError):
            await generator.generate(
                user_message=user_message,
                context=sample_context,
            )

