"""Tests for Context entity."""

from datetime import datetime, timezone

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages


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
    thread_ts: str | None = None,
) -> Message:
    """Create a test message."""
    return Message(
        id=message_id,
        channel=channel,
        user=user,
        text=text,
        timestamp=timestamp,
        thread_ts=thread_ts,
        mentions=[],
    )


def create_empty_channel_messages(
    channel_id: str = "C123", channel_name: str = "general"
) -> ChannelMessages:
    """Create an empty ChannelMessages instance."""
    return ChannelMessages(channel_id=channel_id, channel_name=channel_name)


class TestContextCreation:
    """Tests for Context creation."""

    def test_creates_with_required_fields_only(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that Context can be created with only required fields."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        assert context.persona == persona_config
        assert context.conversation_history == channel_messages
        assert context.workspace_long_term_memory is None
        assert context.workspace_short_term_memory is None
        assert context.channel_memories == {}
        assert context.thread_memories == {}
        assert context.target_thread_ts is None

    def test_creates_with_conversation_history(
        self,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that Context can be created with conversation history."""
        msg = create_test_message(
            text="こんにちは",
            user=sample_user,
            channel=sample_channel,
            timestamp=timestamp,
        )
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=[msg],
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        assert context.conversation_history == channel_messages
        assert context.conversation_history.total_message_count == 1

    def test_creates_with_channel_memories(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that Context can be created with channel memories."""
        channel_messages = create_empty_channel_messages()
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="Long term content",
                short_term_memory="Short term content",
            ),
            "C456": ChannelMemory(
                channel_id="C456",
                channel_name="random",
                long_term_memory="Random channel history",
            ),
        }

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        assert len(context.channel_memories) == 2
        assert "C123" in context.channel_memories
        assert "C456" in context.channel_memories
        assert context.channel_memories["C123"].long_term_memory == "Long term content"

    def test_creates_with_thread_memories(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that Context can be created with thread memories."""
        channel_messages = create_empty_channel_messages()
        thread_memories = {
            "1234567890.000000": "Thread 1 summary",
            "1234567891.000000": "Thread 2 summary",
        }

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            thread_memories=thread_memories,
        )

        assert len(context.thread_memories) == 2
        assert context.thread_memories["1234567890.000000"] == "Thread 1 summary"
        assert context.thread_memories["1234567891.000000"] == "Thread 2 summary"

    def test_creates_with_target_thread_ts(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that Context can be created with target_thread_ts."""
        channel_messages = create_empty_channel_messages()
        target_thread_ts = "1234567890.000000"

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=target_thread_ts,
        )

        assert context.target_thread_ts == target_thread_ts


class TestContextImmutability:
    """Tests for Context immutability."""

    def test_context_is_frozen(self, persona_config: PersonaConfig) -> None:
        """Test that Context is immutable."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        with pytest.raises(AttributeError):
            context.persona = persona_config  # type: ignore[misc]

    def test_cannot_modify_conversation_history_attribute(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that conversation_history attribute cannot be replaced."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        with pytest.raises(AttributeError):
            context.conversation_history = channel_messages  # type: ignore[misc]

    def test_cannot_modify_channel_memories_attribute(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that channel_memories attribute cannot be replaced."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        with pytest.raises(AttributeError):
            context.channel_memories = {}  # type: ignore[misc]

    def test_cannot_modify_thread_memories_attribute(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that thread_memories attribute cannot be replaced."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        with pytest.raises(AttributeError):
            context.thread_memories = {}  # type: ignore[misc]

    def test_cannot_modify_memory_fields(self, persona_config: PersonaConfig) -> None:
        """Test that memory fields cannot be modified."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="test",
        )

        with pytest.raises(AttributeError):
            context.workspace_long_term_memory = "new"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            context.workspace_short_term_memory = "new"  # type: ignore[misc]

    def test_cannot_modify_target_thread_ts(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that target_thread_ts cannot be modified."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts="1234567890.000000",
        )

        with pytest.raises(AttributeError):
            context.target_thread_ts = "new"  # type: ignore[misc]


class TestContextMemoryFields:
    """Tests for Context memory fields."""

    def test_context_without_memory_fields(self, persona_config: PersonaConfig) -> None:
        """Test that Context without memory fields has all None/empty values."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        assert context.workspace_long_term_memory is None
        assert context.workspace_short_term_memory is None
        assert context.channel_memories == {}
        assert context.thread_memories == {}
        assert context.target_thread_ts is None

    def test_context_with_all_memory_fields(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that Context can be created with all memory fields."""
        channel_messages = create_empty_channel_messages()
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="Channel history...",
                short_term_memory="Recent channel events...",
            ),
        }
        thread_memories = {
            "1234567890.000000": "Thread summary...",
        }

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="ワークスペースの歴史...",
            workspace_short_term_memory="直近のワークスペースでの出来事...",
            channel_memories=channel_memories,
            thread_memories=thread_memories,
            target_thread_ts="1234567890.000000",
        )

        assert context.workspace_long_term_memory == "ワークスペースの歴史..."
        assert (
            context.workspace_short_term_memory == "直近のワークスペースでの出来事..."
        )
        assert len(context.channel_memories) == 1
        assert context.channel_memories["C123"].long_term_memory == "Channel history..."
        assert len(context.thread_memories) == 1
        assert context.thread_memories["1234567890.000000"] == "Thread summary..."
        assert context.target_thread_ts == "1234567890.000000"

    def test_context_with_partial_memory_fields(
        self, persona_config: PersonaConfig
    ) -> None:
        """Test that Context can be created with partial memory fields."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="ワークスペースの歴史...",
            target_thread_ts="1234567890.000000",
        )

        assert context.workspace_long_term_memory == "ワークスペースの歴史..."
        assert context.workspace_short_term_memory is None
        assert context.channel_memories == {}
        assert context.thread_memories == {}
        assert context.target_thread_ts == "1234567890.000000"


class TestChannelMemories:
    """Tests for channel_memories field."""

    def test_channel_memories_default_empty_dict(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that channel_memories defaults to empty dict."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )
        assert context.channel_memories == {}

    def test_channel_memories_with_multiple_channels(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that channel_memories can hold multiple channels."""
        channel_messages = create_empty_channel_messages()
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="General channel history",
            ),
            "C456": ChannelMemory(
                channel_id="C456",
                channel_name="random",
                long_term_memory="Random channel history",
            ),
            "C789": ChannelMemory(
                channel_id="C789",
                channel_name="dev",
                short_term_memory="Recent dev activity",
            ),
        }

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        assert len(context.channel_memories) == 3
        assert "C123" in context.channel_memories
        assert "C456" in context.channel_memories
        assert "C789" in context.channel_memories
        assert (
            context.channel_memories["C123"].long_term_memory
            == "General channel history"
        )
        assert (
            context.channel_memories["C789"].short_term_memory == "Recent dev activity"
        )


class TestThreadMemories:
    """Tests for thread_memories field."""

    def test_thread_memories_default_empty_dict(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that thread_memories defaults to empty dict."""
        channel_messages = create_empty_channel_messages()
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )
        assert context.thread_memories == {}

    def test_thread_memories_with_multiple_threads(
        self,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that thread_memories can hold multiple thread summaries."""
        channel_messages = create_empty_channel_messages()
        thread_memories = {
            "1234567890.000000": "Bug fix discussion summary",
            "1234567891.000000": "Feature design summary",
            "1234567892.000000": "Code review summary",
        }

        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            thread_memories=thread_memories,
        )

        assert len(context.thread_memories) == 3
        assert (
            context.thread_memories["1234567890.000000"] == "Bug fix discussion summary"
        )
        assert context.thread_memories["1234567891.000000"] == "Feature design summary"
        assert context.thread_memories["1234567892.000000"] == "Code review summary"
