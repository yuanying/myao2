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


class TestContextCreation:
    """Tests for Context creation."""

    def test_creates_with_persona_only(self, persona_config: PersonaConfig) -> None:
        """Test that Context can be created with only persona."""
        context = Context(persona=persona_config)

        assert context.persona == persona_config
        assert context.conversation_history == []
        assert context.other_channel_messages == {}

    def test_creates_with_conversation_history(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that Context can be created with conversation history."""
        history = [
            create_test_message(
                text="こんにちは",
                user=sample_user,
                channel=sample_channel,
                timestamp=timestamp,
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=history,
        )

        assert context.conversation_history == history

    def test_creates_with_other_channel_messages(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that Context can be created with other channel messages."""
        random_channel = Channel(id="C456", name="random")
        other_messages = {
            "random": [
                create_test_message(
                    text="今日は暑いね",
                    user=sample_user,
                    channel=random_channel,
                    timestamp=timestamp,
                ),
            ],
        }
        context = Context(
            persona=persona_config,
            conversation_history=[],
            other_channel_messages=other_messages,
        )

        assert context.other_channel_messages == other_messages


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

    def test_cannot_modify_conversation_history_attribute(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that conversation_history attribute cannot be replaced."""
        context = Context(persona=persona_config, conversation_history=[])

        with pytest.raises(AttributeError):
            context.conversation_history = []  # type: ignore[misc]

    def test_cannot_modify_other_channel_messages_attribute(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that other_channel_messages attribute cannot be replaced."""
        context = Context(persona=persona_config)

        with pytest.raises(AttributeError):
            context.other_channel_messages = {}  # type: ignore[misc]

    def test_cannot_modify_memory_fields(self, persona_config: PersonaConfig) -> None:
        """Test that memory fields cannot be modified."""
        context = Context(
            persona=persona_config,
            workspace_long_term_memory="test",
        )

        with pytest.raises(AttributeError):
            context.workspace_long_term_memory = "new"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            context.workspace_short_term_memory = "new"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            context.channel_long_term_memory = "new"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            context.channel_short_term_memory = "new"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            context.thread_memory = "new"  # type: ignore[misc]


class TestContextMemoryFields:
    """Tests for Context memory fields."""

    def test_context_without_memory_fields(self, persona_config: PersonaConfig) -> None:
        """Test that Context without memory fields has all None values."""
        context = Context(persona=persona_config)

        assert context.workspace_long_term_memory is None
        assert context.workspace_short_term_memory is None
        assert context.channel_long_term_memory is None
        assert context.channel_short_term_memory is None
        assert context.thread_memory is None

    def test_context_with_all_memory_fields(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that Context can be created with all memory fields."""
        context = Context(
            persona=persona_config,
            workspace_long_term_memory="ワークスペースの歴史...",
            workspace_short_term_memory="直近のワークスペースでの出来事...",
            channel_long_term_memory="チャンネルの歴史...",
            channel_short_term_memory="直近のチャンネルでの出来事...",
            thread_memory="スレッドの要約...",
        )

        assert context.workspace_long_term_memory == "ワークスペースの歴史..."
        assert (
            context.workspace_short_term_memory == "直近のワークスペースでの出来事..."
        )
        assert context.channel_long_term_memory == "チャンネルの歴史..."
        assert context.channel_short_term_memory == "直近のチャンネルでの出来事..."
        assert context.thread_memory == "スレッドの要約..."

    def test_context_with_partial_memory_fields(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that Context can be created with partial memory fields."""
        context = Context(
            persona=persona_config,
            workspace_long_term_memory="ワークスペースの歴史...",
            thread_memory="スレッドの要約...",
        )

        assert context.workspace_long_term_memory == "ワークスペースの歴史..."
        assert context.workspace_short_term_memory is None
        assert context.channel_long_term_memory is None
        assert context.channel_short_term_memory is None
        assert context.thread_memory == "スレッドの要約..."


class TestOtherChannelMessages:
    """Tests for other_channel_messages field."""

    def test_other_channel_messages_default_empty_dict(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that other_channel_messages defaults to empty dict."""
        context = Context(persona=persona_config, conversation_history=[])
        assert context.other_channel_messages == {}

    def test_other_channel_messages_with_multiple_channels(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test that other_channel_messages can hold multiple channels."""
        random_channel = Channel(id="C456", name="random")
        dev_channel = Channel(id="C789", name="dev")

        other_messages = {
            "random": [
                create_test_message(
                    text="今日は暑いね",
                    user=sample_user,
                    channel=random_channel,
                    timestamp=timestamp,
                    message_id="msg001",
                ),
            ],
            "dev": [
                create_test_message(
                    text="PRレビューお願いします",
                    user=sample_user,
                    channel=dev_channel,
                    timestamp=timestamp,
                    message_id="msg002",
                ),
            ],
        }
        context = Context(
            persona=persona_config,
            conversation_history=[],
            other_channel_messages=other_messages,
        )

        assert len(context.other_channel_messages) == 2
        assert "random" in context.other_channel_messages
        assert "dev" in context.other_channel_messages
        assert len(context.other_channel_messages["random"]) == 1
        assert len(context.other_channel_messages["dev"]) == 1
