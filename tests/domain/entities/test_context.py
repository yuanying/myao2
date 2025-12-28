"""Tests for Context entity."""

from datetime import datetime, timezone

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User


@pytest.fixture
def persona_config() -> PersonaConfig:
    """Create test persona config."""
    return PersonaConfig(
        name="myao",
        system_prompt="あなたは友達のように振る舞うチャットボットです。",
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


def create_test_message(
    text: str,
    user: User,
    channel: Channel,
    timestamp: datetime,
    message_id: str = "1234567890.123456",
) -> Message:
    """Create a test message."""
    return Message(
        id=message_id,
        channel=channel,
        user=user,
        text=text,
        timestamp=timestamp,
        thread_ts=None,
        mentions=[],
    )


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_returns_persona_system_prompt(self, persona_config: PersonaConfig) -> None:
        """Test that build_system_prompt returns persona's system prompt."""
        context = Context(
            persona=persona_config,
            conversation_history=[],
        )

        result = context.build_system_prompt()

        assert result == persona_config.system_prompt
        assert result == "あなたは友達のように振る舞うチャットボットです。"


class TestBuildMessagesForLlm:
    """Tests for build_messages_for_llm."""

    def test_no_history(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test with no conversation history."""
        context = Context(
            persona=persona_config,
            conversation_history=[],
        )
        user_message = create_test_message(
            text="@myao こんにちは",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
        )

        messages = context.build_messages_for_llm(user_message)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == persona_config.system_prompt
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "@myao こんにちは"

    def test_single_history(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test with single conversation history."""
        history_message = create_test_message(
            text="こんにちは！",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
            message_id="1234567890.000001",
        )
        context = Context(
            persona=persona_config,
            conversation_history=[history_message],
        )
        user_message = create_test_message(
            text="今日の調子はどう？",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
            message_id="1234567890.000002",
        )

        messages = context.build_messages_for_llm(user_message)

        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "こんにちは！"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "今日の調子はどう？"

    def test_multiple_history(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_bot: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test with multiple conversation history (user and bot)."""
        history = [
            create_test_message(
                text="こんにちは！",
                user=sample_user,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000001",
            ),
            create_test_message(
                text="こんにちは！何かお手伝いできることはありますか？",
                user=sample_bot,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000002",
            ),
            create_test_message(
                text="今日の調子はどう？",
                user=sample_user,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000003",
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=history,
        )
        user_message = create_test_message(
            text="何か面白い話ある？",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
            message_id="1234567890.000004",
        )

        messages = context.build_messages_for_llm(user_message)

        assert len(messages) == 5
        # System prompt
        assert messages[0]["role"] == "system"
        # History (oldest first)
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "こんにちは！"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == (
            "こんにちは！何かお手伝いできることはありますか？"
        )
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "今日の調子はどう？"
        # Current message
        assert messages[4]["role"] == "user"
        assert messages[4]["content"] == "何か面白い話ある？"

    def test_role_determination(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_bot: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that roles are correctly determined based on is_bot."""
        history = [
            create_test_message(
                text="User message",
                user=sample_user,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000001",
            ),
            create_test_message(
                text="Bot response",
                user=sample_bot,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000002",
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=history,
        )
        user_message = create_test_message(
            text="Another user message",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
        )

        messages = context.build_messages_for_llm(user_message)

        # User messages should have role="user"
        assert messages[1]["role"] == "user"
        # Bot messages should have role="assistant"
        assert messages[2]["role"] == "assistant"

    def test_message_order(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_bot: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that messages are in correct order: system -> history -> user."""
        history = [
            create_test_message(
                text="First",
                user=sample_user,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000001",
            ),
            create_test_message(
                text="Second",
                user=sample_bot,
                channel=sample_channel,
                timestamp=timestamp,
                message_id="1234567890.000002",
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=history,
        )
        user_message = create_test_message(
            text="Current",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
        )

        messages = context.build_messages_for_llm(user_message)

        # Order: system -> history[0] -> history[1] -> current
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "First"
        assert messages[2]["content"] == "Second"
        assert messages[3]["content"] == "Current"


class TestContextImmutability:
    """Tests for Context immutability."""

    def test_context_is_frozen(self, persona_config: PersonaConfig) -> None:
        """Test that Context is immutable."""
        context = Context(
            persona=persona_config,
            conversation_history=[],
        )

        with pytest.raises(AttributeError):
            context.persona = persona_config  # type: ignore[misc]
