"""Tests for LLMMemorySummarizer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.config.models import MemoryConfig, PersonaConfig
from myao2.domain.entities import Channel, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.infrastructure.llm import LLMClient, LLMError
from myao2.infrastructure.llm.memory_summarizer import LLMMemorySummarizer


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.complete = AsyncMock(return_value="- 要約された記憶内容")
    return client


@pytest.fixture
def memory_config() -> MemoryConfig:
    """Create test memory config."""
    return MemoryConfig(
        database_path=":memory:",
        long_term_summary_max_tokens=500,
        short_term_summary_max_tokens=300,
    )


@pytest.fixture
def summarizer(
    mock_client: MagicMock, memory_config: MemoryConfig
) -> LLMMemorySummarizer:
    """Create summarizer instance."""
    return LLMMemorySummarizer(client=mock_client, config=memory_config)


@pytest.fixture
def sample_user() -> User:
    """Create test user."""
    return User(id="U123", name="testuser", is_bot=False)


@pytest.fixture
def sample_channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_thread_messages(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> list[Message]:
    """Create test thread messages."""
    thread_ts = "1234567890.000001"
    return [
        Message(
            id="1234567890.000010",
            channel=sample_channel,
            user=sample_user,
            text="スレッド内の返信1",
            timestamp=datetime(2024, 1, 1, 12, 10, 0, tzinfo=timezone.utc),
            thread_ts=thread_ts,
            mentions=[],
        ),
        Message(
            id="1234567890.000020",
            channel=sample_channel,
            user=sample_user,
            text="スレッド内の返信2",
            timestamp=datetime(2024, 1, 1, 12, 15, 0, tzinfo=timezone.utc),
            thread_ts=thread_ts,
            mentions=[],
        ),
    ]


@pytest.fixture
def sample_top_level_messages(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> list[Message]:
    """Create test top-level messages."""
    return [
        Message(
            id="1234567890.000001",
            channel=sample_channel,
            user=sample_user,
            text="こんにちは",
            timestamp=timestamp,
            thread_ts=None,
            mentions=[],
        ),
        Message(
            id="1234567890.000002",
            channel=sample_channel,
            user=sample_user,
            text="今日の天気はどうですか？",
            timestamp=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
            thread_ts=None,
            mentions=[],
        ),
    ]


@pytest.fixture
def context_with_thread_messages(
    sample_channel: Channel,
    sample_top_level_messages: list[Message],
    sample_thread_messages: list[Message],
) -> Context:
    """Create context with thread messages for thread scope tests."""
    thread_ts = "1234567890.000001"
    return Context(
        persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
        conversation_history=ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=sample_top_level_messages,
            thread_messages={thread_ts: sample_thread_messages},
        ),
        workspace_long_term_memory="ワークスペースの長期記憶",
        workspace_short_term_memory="ワークスペースの短期記憶",
        channel_memories={
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory="チャンネルの長期記憶",
                short_term_memory="チャンネルの短期記憶",
            )
        },
        thread_memories={},
        target_thread_ts=thread_ts,
    )


@pytest.fixture
def context_with_channel_messages(
    sample_channel: Channel,
    sample_top_level_messages: list[Message],
    sample_thread_messages: list[Message],
) -> Context:
    """Create context with channel messages for channel scope tests."""
    thread_ts = "1234567890.000001"
    return Context(
        persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
        conversation_history=ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=sample_top_level_messages,
            thread_messages={thread_ts: sample_thread_messages},
        ),
        workspace_long_term_memory="ワークスペースの長期記憶",
        workspace_short_term_memory="ワークスペースの短期記憶",
        channel_memories={
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory="チャンネルの長期記憶",
                short_term_memory="チャンネルの短期記憶",
            )
        },
        thread_memories={},
        target_thread_ts=None,
    )


@pytest.fixture
def context_with_channel_memories(sample_channel: Channel) -> Context:
    """Create context with channel memories for workspace scope tests."""
    other_channel = Channel(id="C456", name="random")
    return Context(
        persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
        conversation_history=ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        ),
        workspace_long_term_memory=None,
        workspace_short_term_memory=None,
        channel_memories={
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory="generalチャンネルの長期記憶",
                short_term_memory="generalチャンネルの短期記憶",
            ),
            other_channel.id: ChannelMemory(
                channel_id=other_channel.id,
                channel_name=other_channel.name,
                long_term_memory="randomチャンネルの長期記憶",
                short_term_memory="randomチャンネルの短期記憶",
            ),
        },
        thread_memories={},
        target_thread_ts=None,
    )


class TestLLMMemorySummarizerThreadScope:
    """Tests for THREAD scope summarization."""

    async def test_summarize_thread_uses_target_thread_messages(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that thread scope uses messages from target_thread_ts."""
        result = await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        assert result == "- 要約された記憶内容"
        mock_client.complete.assert_awaited_once()

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should only have system message (no user message)
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

        system_content = messages[0]["content"]
        # Should contain thread messages
        assert "スレッド内の返信1" in system_content
        assert "スレッド内の返信2" in system_content
        # Should contain summary instruction
        assert "要約対象スレッド" in system_content

    async def test_summarize_thread_includes_persona_system_prompt(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that thread scope includes persona system prompt."""
        await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include persona system prompt
        assert "Test prompt" in system_content

    async def test_summarize_thread_includes_workspace_memories(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that thread scope includes workspace memories (long/short-term)."""
        await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include workspace memory
        assert "ワークスペースの長期記憶" in system_content
        assert "ワークスペースの短期記憶" in system_content

    async def test_summarize_thread_includes_channel_memory(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that thread scope includes channel memory."""
        await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include channel memory
        assert "チャンネルの長期記憶" in system_content

    async def test_summarize_thread_no_target_returns_empty(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test that thread scope with no target_thread_ts returns empty."""
        context_no_target = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
            target_thread_ts=None,
        )

        result = await summarizer.summarize(
            context=context_no_target,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        assert result == ""
        mock_client.complete.assert_not_awaited()


class TestLLMMemorySummarizerChannelScope:
    """Tests for CHANNEL scope summarization."""

    async def test_summarize_channel_short_term_uses_messages(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that channel short-term uses all messages (top-level + threads)."""
        result = await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
        )

        assert result == "- 要約された記憶内容"
        mock_client.complete.assert_awaited_once()

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should only have system message
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

        system_content = messages[0]["content"]
        # Should contain top-level messages
        assert "こんにちは" in system_content
        assert "今日の天気はどうですか？" in system_content
        # Should contain thread messages
        assert "スレッド内の返信1" in system_content
        assert "スレッド内の返信2" in system_content

    async def test_summarize_channel_short_term_includes_persona(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that channel short-term includes persona system prompt."""
        await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include persona
        assert "Test prompt" in system_content

    async def test_summarize_channel_short_term_includes_workspace_memory(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that channel short-term includes workspace memory."""
        await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include workspace memory (long-term only for channel scope)
        assert "ワークスペースの長期記憶" in system_content

    async def test_summarize_channel_long_term_uses_short_term_memory(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that channel long-term merges short-term into existing long-term."""
        existing = "- 既存のチャンネル長期記憶"

        await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should contain short-term memory (not messages)
        assert "チャンネルの短期記憶" in system_content
        # Should contain existing long-term memory
        assert existing in system_content
        # Should NOT contain raw messages
        assert "こんにちは" not in system_content

    async def test_summarize_channel_long_term_no_short_term_returns_existing(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test that channel long-term without short-term returns existing."""
        context_no_short_term = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
            channel_memories={
                sample_channel.id: ChannelMemory(
                    channel_id=sample_channel.id,
                    channel_name=sample_channel.name,
                    long_term_memory="既存の長期記憶",
                    short_term_memory=None,
                )
            },
        )
        existing = "- 既存のチャンネル長期記憶"

        result = await summarizer.summarize(
            context=context_no_short_term,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing,
        )

        assert result == existing
        mock_client.complete.assert_not_awaited()

    async def test_summarize_channel_empty_messages_returns_existing(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test that empty channel messages returns existing memory."""
        empty_context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
        )
        existing = "- 既存のチャンネル記憶"

        result = await summarizer.summarize(
            context=empty_context,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory=existing,
        )

        assert result == existing
        mock_client.complete.assert_not_awaited()


class TestLLMMemorySummarizerWorkspaceScope:
    """Tests for WORKSPACE scope summarization."""

    async def test_summarize_workspace_short_term_uses_channel_short_term(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_memories: Context,
    ) -> None:
        """Test that workspace short-term uses only channel short-term memories."""
        result = await summarizer.summarize(
            context=context_with_channel_memories,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
        )

        assert result == "- 要約された記憶内容"
        mock_client.complete.assert_awaited_once()

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should only have system message
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

        system_content = messages[0]["content"]
        # Should contain channel short-term memories
        assert "generalチャンネルの短期記憶" in system_content
        assert "randomチャンネルの短期記憶" in system_content
        # Should NOT contain channel long-term memories
        assert "generalチャンネルの長期記憶" not in system_content

    async def test_summarize_workspace_short_term_includes_persona(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_memories: Context,
    ) -> None:
        """Test that workspace short-term includes persona system prompt."""
        await summarizer.summarize(
            context=context_with_channel_memories,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should include persona
        assert "Test prompt" in system_content

    async def test_summarize_workspace_long_term_uses_channel_long_term(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_memories: Context,
    ) -> None:
        """Test that workspace long-term uses only channel long-term memories."""
        existing = "- 既存のワークスペース長期記憶"

        await summarizer.summarize(
            context=context_with_channel_memories,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_content = messages[0]["content"]

        # Should contain channel long-term memories
        assert "generalチャンネルの長期記憶" in system_content
        assert "randomチャンネルの長期記憶" in system_content
        # Should contain existing workspace long-term memory
        assert existing in system_content
        # Should NOT contain channel short-term memories
        assert "generalチャンネルの短期記憶" not in system_content

    async def test_summarize_workspace_long_term_no_channel_long_term_returns_existing(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test workspace long-term without channel long-term returns existing."""
        context_no_long_term = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
            channel_memories={
                sample_channel.id: ChannelMemory(
                    channel_id=sample_channel.id,
                    channel_name=sample_channel.name,
                    long_term_memory=None,
                    short_term_memory="短期記憶のみ",
                )
            },
        )
        existing = "- 既存のワークスペース長期記憶"

        result = await summarizer.summarize(
            context=context_no_long_term,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing,
        )

        assert result == existing
        mock_client.complete.assert_not_awaited()

    async def test_workspace_short_term_no_channel_short_term_returns_existing(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test workspace short-term w/o channel short-term returns existing."""
        context_no_short_term = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
            channel_memories={
                sample_channel.id: ChannelMemory(
                    channel_id=sample_channel.id,
                    channel_name=sample_channel.name,
                    long_term_memory="長期記憶のみ",
                    short_term_memory=None,
                )
            },
        )
        existing = "- 既存のワークスペース短期記憶"

        result = await summarizer.summarize(
            context=context_no_short_term,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory=existing,
        )

        assert result == existing
        mock_client.complete.assert_not_awaited()

    async def test_summarize_workspace_no_channel_memories_returns_existing(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        sample_channel: Channel,
    ) -> None:
        """Test workspace scope with no channel memories returns existing."""
        empty_context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test prompt"),
            conversation_history=ChannelMessages(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
            ),
            channel_memories={},
        )
        existing = "- 既存のワークスペース記憶"

        result = await summarizer.summarize(
            context=empty_context,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing,
        )

        assert result == existing
        mock_client.complete.assert_not_awaited()


class TestLLMMemorySummarizerMemoryType:
    """Tests for memory type handling."""

    async def test_long_term_max_tokens(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that long-term memory uses correct max_tokens."""
        await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.LONG_TERM,
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 500

    async def test_short_term_max_tokens(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that short-term memory uses correct max_tokens."""
        await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_kwargs = mock_client.complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 300


class TestLLMMemorySummarizerLLMMessageFormat:
    """Tests for LLM message format (system-only)."""

    async def test_llm_message_format_is_system_only(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_thread_messages: Context,
    ) -> None:
        """Test that LLM messages contain only system role (no user)."""
        await summarizer.summarize(
            context=context_with_thread_messages,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should have exactly 1 message
        assert len(messages) == 1
        # Should only have system role
        assert messages[0]["role"] == "system"
        # Should not have user message
        assert all(msg["role"] != "user" for msg in messages)

    async def test_channel_scope_llm_message_format(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test channel scope uses system-only format."""
        await summarizer.summarize(
            context=context_with_channel_messages,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    async def test_workspace_scope_llm_message_format(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_memories: Context,
    ) -> None:
        """Test workspace scope uses system-only format."""
        await summarizer.summarize(
            context=context_with_channel_memories,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
        )

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        assert len(messages) == 1
        assert messages[0]["role"] == "system"


class TestLLMMemorySummarizerErrorHandling:
    """Tests for error handling."""

    async def test_summarize_propagates_llm_error(
        self,
        summarizer: LLMMemorySummarizer,
        mock_client: MagicMock,
        context_with_channel_messages: Context,
    ) -> None:
        """Test that LLM errors are propagated."""
        mock_client.complete.side_effect = LLMError("API error")

        with pytest.raises(LLMError):
            await summarizer.summarize(
                context=context_with_channel_messages,
                scope=MemoryScope.CHANNEL,
                memory_type=MemoryType.LONG_TERM,
            )


class TestLLMMemorySummarizerTemplateRendering:
    """Tests for Jinja2 template rendering."""

    def test_template_renders_thread_prompt(
        self,
        summarizer: LLMMemorySummarizer,
    ) -> None:
        """Test that template renders thread prompt correctly."""
        channel = ChannelMemory(
            channel_id="C123",
            channel_name="general",
            long_term_memory="チャンネルの歴史",
            short_term_memory="チャンネルの最近の出来事",
        )
        context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test persona prompt"),
            conversation_history=ChannelMessages(
                channel_id="C123",
                channel_name="general",
                top_level_messages=[],
                thread_messages={},
            ),
            workspace_long_term_memory="WS長期記憶",
            channel_memories={"C123": channel},
            target_thread_ts="1234567890.000001",
        )

        rendered = summarizer._build_system_prompt(
            context=context,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory=None,
        )

        assert "Test persona prompt" in rendered
        assert "WS長期記憶" in rendered
        assert "要約対象スレッド" in rendered

    def test_template_renders_channel_short_term_prompt(
        self,
        summarizer: LLMMemorySummarizer,
    ) -> None:
        """Test that template renders channel short-term prompt correctly."""
        context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test persona prompt"),
            conversation_history=ChannelMessages(
                channel_id="C123",
                channel_name="general",
                top_level_messages=[],
                thread_messages={},
            ),
            workspace_long_term_memory="WS長期記憶",
        )

        rendered = summarizer._build_system_prompt(
            context=context,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory=None,
        )

        assert "Test persona prompt" in rendered
        assert "WS長期記憶" in rendered
        assert "チャンネル会話履歴" in rendered

    def test_template_renders_channel_long_term_prompt(
        self,
        summarizer: LLMMemorySummarizer,
    ) -> None:
        """Test that template renders channel long-term prompt correctly."""
        channel = ChannelMemory(
            channel_id="C123",
            channel_name="general",
            short_term_memory="チャンネル短期記憶",
        )
        context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test persona prompt"),
            conversation_history=ChannelMessages(
                channel_id="C123",
                channel_name="general",
            ),
            channel_memories={"C123": channel},
        )

        rendered = summarizer._build_system_prompt(
            context=context,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.LONG_TERM,
            existing_memory="既存の長期記憶",
        )

        assert "Test persona prompt" in rendered
        assert "既存の長期記憶" in rendered
        assert "チャンネル短期記憶" in rendered
        assert "統合対象" in rendered

    def test_template_renders_workspace_short_term_prompt(
        self,
        summarizer: LLMMemorySummarizer,
    ) -> None:
        """Test that template renders workspace short-term prompt correctly."""
        context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test persona prompt"),
            conversation_history=ChannelMessages(
                channel_id="",
                channel_name="",
            ),
            channel_memories={
                "C123": ChannelMemory(
                    channel_id="C123",
                    channel_name="general",
                    short_term_memory="general短期記憶",
                )
            },
        )

        rendered = summarizer._build_system_prompt(
            context=context,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory=None,
        )

        assert "Test persona prompt" in rendered
        assert "general短期記憶" in rendered
        assert "ワークスペース全体" in rendered

    def test_template_renders_workspace_long_term_prompt(
        self,
        summarizer: LLMMemorySummarizer,
    ) -> None:
        """Test that template renders workspace long-term prompt correctly."""
        context = Context(
            persona=PersonaConfig(name="TestBot", system_prompt="Test persona prompt"),
            conversation_history=ChannelMessages(
                channel_id="",
                channel_name="",
            ),
            channel_memories={
                "C123": ChannelMemory(
                    channel_id="C123",
                    channel_name="general",
                    long_term_memory="general長期記憶",
                )
            },
        )

        rendered = summarizer._build_system_prompt(
            context=context,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.LONG_TERM,
            existing_memory="既存のWS長期記憶",
        )

        assert "Test persona prompt" in rendered
        assert "既存のWS長期記憶" in rendered
        assert "general長期記憶" in rendered
        assert "統合対象" in rendered
