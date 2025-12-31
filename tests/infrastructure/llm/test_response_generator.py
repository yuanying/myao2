"""Tests for LiteLLMResponseGenerator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
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
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that current user message is included in system prompt."""
        # Create context with the user message in top_level_messages
        top_messages = [user_message]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=top_messages,
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

        # New template uses "返信対象: トップレベル" section
        assert "返信対象: トップレベル" in system_content
        assert "testuser:" in system_content
        assert "Hello" in system_content
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
        # History should be in system prompt (using new template format)
        assert "## 現在の会話" in system_content
        assert "testuser:" in system_content
        assert "Hi there!" in system_content
        assert "myao:" in system_content
        assert "Hello! How can I help?" in system_content

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

        # For empty context (no target_thread_ts), top-level instruction is used
        assert "上記の情報をもとに" in system_content
        assert "返信対象メッセージに返答してください" in system_content

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


class TestFormatTimestamp:
    """Tests for format_timestamp filter."""

    def test_format_timestamp_datetime(self) -> None:
        """Test formatting datetime object."""
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        result = LiteLLMResponseGenerator._format_timestamp(dt)
        assert result == "2024-01-15 14:30:45"

    def test_format_timestamp_without_timezone(self) -> None:
        """Test formatting datetime without timezone."""
        dt = datetime(2024, 12, 31, 23, 59, 59)
        result = LiteLLMResponseGenerator._format_timestamp(dt)
        assert result == "2024-12-31 23:59:59"


class TestBuildSystemPromptWithMemory:
    """Tests for _build_system_prompt with memory integration."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock LLMClient."""
        client = MagicMock(spec=LLMClient)
        client.complete = AsyncMock(return_value="Response")
        return client

    @pytest.fixture
    def generator(self, mock_client: MagicMock) -> LiteLLMResponseGenerator:
        """Create generator instance."""
        return LiteLLMResponseGenerator(client=mock_client)

    @pytest.fixture
    def persona_config(self) -> PersonaConfig:
        """Create test persona config."""
        return PersonaConfig(
            name="myao",
            system_prompt="You are a friendly bot.",
        )

    @pytest.fixture
    def sample_user(self) -> User:
        """Create test user."""
        return User(id="U123", name="testuser", is_bot=False)

    @pytest.fixture
    def sample_channel(self) -> Channel:
        """Create test channel."""
        return Channel(id="C123", name="general")

    @pytest.fixture
    def timestamp(self) -> datetime:
        """Create test timestamp."""
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def user_message(
        self, sample_user: User, sample_channel: Channel, timestamp: datetime
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

    def test_build_system_prompt_without_memories(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building without any memories (backwards compatible)."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hi there!",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )
        user_msg = messages[0]

        result = generator._build_system_prompt(context, user_msg)

        # Should include persona prompt
        assert "You are a friendly bot." in result
        # Should include current conversation section
        assert "## 現在の会話" in result
        assert "#general" in result
        # For top-level reply, messages appear in "### 返信対象: トップレベル" only
        assert "### トップレベル" not in result
        assert "### 返信対象: トップレベル" in result
        assert "testuser:" in result
        assert "Hi there!" in result
        # Should NOT include memory sections when no memories
        assert "## 記憶" not in result
        # Should include final instruction (top-level reply)
        assert "上記の情報をもとに、返信対象メッセージに返答してください" in result

    def test_build_system_prompt_with_workspace_memory_only(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building with workspace memories only."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hi there!",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="Workspace long-term memory content.",
            workspace_short_term_memory="Workspace short-term memory content.",
        )
        user_msg = messages[0]

        result = generator._build_system_prompt(context, user_msg)

        # Should include memory section
        assert "## 記憶" in result
        assert "### ワークスペースの歴史" in result
        assert "Workspace long-term memory content." in result
        assert "### ワークスペースの最近の出来事" in result
        assert "Workspace short-term memory content." in result

    def test_build_system_prompt_with_channel_memories(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building with channel memories."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hi there!",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=messages,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="General channel history.",
                short_term_memory="Recent events in general.",
            ),
            "C456": ChannelMemory(
                channel_id="C456",
                channel_name="random",
                long_term_memory="Random channel history.",
                short_term_memory=None,
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )
        user_msg = messages[0]

        result = generator._build_system_prompt(context, user_msg)

        # Should include channel info section
        assert "## チャンネル情報" in result
        assert "あなたが参加しているチャンネルは以下です" in result
        assert "- #general" in result
        assert "- #random" in result
        # Should include channel memories
        assert "## 各チャンネルの記憶" in result
        assert "### #general" in result
        assert "General channel history." in result
        assert "Recent events in general." in result
        assert "### #random" in result
        assert "Random channel history." in result

    def test_build_system_prompt_thread_reply(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building for thread reply."""
        top_messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Top level message",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        thread_messages = {
            "1234567890.000001": [
                Message(
                    id="1234567890.000002",
                    channel=sample_channel,
                    user=sample_user,
                    text="Thread reply 1",
                    timestamp=timestamp,
                    thread_ts="1234567890.000001",
                    mentions=[],
                ),
                Message(
                    id="1234567890.000003",
                    channel=sample_channel,
                    user=sample_user,
                    text="Thread reply 2",
                    timestamp=timestamp,
                    thread_ts="1234567890.000001",
                    mentions=[],
                ),
            ],
        }
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=top_messages,
            thread_messages=thread_messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts="1234567890.000001",
        )
        user_msg = thread_messages["1234567890.000001"][1]

        result = generator._build_system_prompt(context, user_msg)

        # Target thread should NOT appear in "### スレッド:" section
        # (to avoid duplication)
        assert "### スレッド: 1234567890.000001" not in result
        # Should include target thread section only
        assert "### 返信対象スレッド: 1234567890.000001" in result
        assert "Thread reply 1" in result
        assert "Thread reply 2" in result
        # Should include thread-specific instruction
        assert "上記の情報をもとに、返信対象スレッドに返答してください" in result

    def test_build_system_prompt_top_level_reply(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building for top-level reply."""
        top_messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Top level message",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=top_messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,  # Top-level reply
        )
        user_msg = top_messages[0]

        result = generator._build_system_prompt(context, user_msg)

        # For top-level reply, "### トップレベル" section should NOT exist
        assert "### トップレベル" not in result
        # Messages should appear in "### 返信対象: トップレベル" section only
        assert "### 返信対象: トップレベル" in result
        assert "Top level message" in result
        # Should include top-level specific instruction
        assert "上記の情報をもとに、返信対象メッセージに返答してください" in result

    def test_build_system_prompt_with_all_memories(
        self,
        generator: LiteLLMResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test prompt building with all types of memories."""
        top_messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hello everyone!",
                timestamp=timestamp,
                thread_ts=None,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=top_messages,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="General history.",
                short_term_memory="Recent in general.",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="Workspace history.",
            workspace_short_term_memory="Workspace recent.",
            channel_memories=channel_memories,
            target_thread_ts=None,
        )
        user_msg = top_messages[0]

        result = generator._build_system_prompt(context, user_msg)

        # Verify order of sections (broad to narrow)
        persona_pos = result.find("You are a friendly bot.")
        memory_pos = result.find("## 記憶")
        ws_history_pos = result.find("### ワークスペースの歴史")
        ws_recent_pos = result.find("### ワークスペースの最近の出来事")
        channel_info_pos = result.find("## チャンネル情報")
        channel_memory_pos = result.find("## 各チャンネルの記憶")
        current_conv_pos = result.find("## 現在の会話")
        instruction_pos = result.find("上記の情報をもとに")

        # Assert correct ordering
        assert persona_pos < memory_pos
        assert memory_pos < ws_history_pos
        assert ws_history_pos < ws_recent_pos
        assert ws_recent_pos < channel_info_pos
        assert channel_info_pos < channel_memory_pos
        assert channel_memory_pos < current_conv_pos
        assert current_conv_pos < instruction_pos
