"""Tests for StrandsMemorySummarizer."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myao2.config.models import AgentConfig, MemoryConfig, PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.infrastructure.llm.exceptions import LLMError
from myao2.infrastructure.llm.strands.memory_summarizer import StrandsMemorySummarizer


@pytest.fixture
def mock_model() -> MagicMock:
    """Create mock LiteLLMModel."""
    return MagicMock()


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
    mock_model: MagicMock, memory_config: MemoryConfig
) -> StrandsMemorySummarizer:
    """Create summarizer instance."""
    return StrandsMemorySummarizer(model=mock_model, config=memory_config)


def create_mock_result(text: str) -> MagicMock:
    """Create a mock Agent result."""
    result = MagicMock()
    result.__str__ = MagicMock(return_value=text)
    return result


class TestStrandsMemorySummarizer:
    """Tests for StrandsMemorySummarizer.summarize method."""

    async def test_summarize_thread_scope(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test summarize with THREAD scope."""
        thread_ts = "1234567890.000001"
        messages = [
            Message(
                id="1234567890.000002",
                channel=sample_channel,
                user=sample_user,
                text="Thread message",
                timestamp=timestamp,
                thread_ts=thread_ts,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            thread_messages={thread_ts: messages},
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=thread_ts,
        )

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Thread summary")
            )
            mock_agent_class.return_value = mock_agent

            result = await summarizer.summarize(
                context=context,
                scope=MemoryScope.THREAD,
                memory_type=MemoryType.SHORT_TERM,
            )

            assert result == "Thread summary"
            mock_agent.invoke_async.assert_awaited_once()

    async def test_summarize_channel_short_term(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test summarize with CHANNEL scope and SHORT_TERM type."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Channel message",
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

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Channel short-term summary")
            )
            mock_agent_class.return_value = mock_agent

            result = await summarizer.summarize(
                context=context,
                scope=MemoryScope.CHANNEL,
                memory_type=MemoryType.SHORT_TERM,
            )

            assert result == "Channel short-term summary"

    async def test_summarize_channel_long_term(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test summarize with CHANNEL scope and LONG_TERM type."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory=None,
                short_term_memory="Recent channel events",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Channel long-term summary")
            )
            mock_agent_class.return_value = mock_agent

            result = await summarizer.summarize(
                context=context,
                scope=MemoryScope.CHANNEL,
                memory_type=MemoryType.LONG_TERM,
                existing_memory="Previous history",
            )

            assert result == "Channel long-term summary"

    async def test_summarize_workspace_short_term(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test summarize with WORKSPACE scope and SHORT_TERM type."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory=None,
                short_term_memory="General channel events",
            ),
            "C456": ChannelMemory(
                channel_id="C456",
                channel_name="random",
                long_term_memory=None,
                short_term_memory="Random channel events",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Workspace short-term summary")
            )
            mock_agent_class.return_value = mock_agent

            result = await summarizer.summarize(
                context=context,
                scope=MemoryScope.WORKSPACE,
                memory_type=MemoryType.SHORT_TERM,
            )

            assert result == "Workspace short-term summary"

    async def test_summarize_workspace_long_term(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test summarize with WORKSPACE scope and LONG_TERM type."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="General history",
                short_term_memory=None,
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Workspace long-term summary")
            )
            mock_agent_class.return_value = mock_agent

            result = await summarizer.summarize(
                context=context,
                scope=MemoryScope.WORKSPACE,
                memory_type=MemoryType.LONG_TERM,
                existing_memory="Previous workspace history",
            )

            assert result == "Workspace long-term summary"

    async def test_summarize_no_content_returns_existing_memory(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test summarize returns existing memory when no content to summarize."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
        )

        result = await summarizer.summarize(
            context=context,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
            existing_memory="Existing memory content",
        )

        assert result == "Existing memory content"

    async def test_summarize_no_content_returns_empty_string(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test summarize returns empty string when no content and no existing."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
        )

        result = await summarizer.summarize(
            context=context,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        assert result == ""

    async def test_summarize_error_mapping(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test that LLM errors are properly mapped."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Test",
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

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(side_effect=Exception("API error"))
            mock_agent_class.return_value = mock_agent

            with pytest.raises(LLMError):
                await summarizer.summarize(
                    context=context,
                    scope=MemoryScope.CHANNEL,
                    memory_type=MemoryType.SHORT_TERM,
                )

    async def test_summarize_agent_receives_model(
        self,
        summarizer: StrandsMemorySummarizer,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test that Agent is created with correct model."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Test",
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

        with patch(
            "myao2.infrastructure.llm.strands.memory_summarizer.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result("Summary")
            )
            mock_agent_class.return_value = mock_agent

            await summarizer.summarize(
                context=context,
                scope=MemoryScope.CHANNEL,
                memory_type=MemoryType.SHORT_TERM,
            )

            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs["model"] == mock_model


class TestBuildSystemPrompt:
    """Tests for StrandsMemorySummarizer.build_system_prompt method."""

    def test_includes_persona_system_prompt(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test that system prompt contains persona's system prompt."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.THREAD, MemoryType.SHORT_TERM
        )

        assert "You are a friendly bot." in result

    def test_includes_agent_system_prompt(
        self,
        mock_model: MagicMock,
        memory_config: MemoryConfig,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes agent's system_prompt when provided."""
        agent_config = AgentConfig(
            model_id="openai/gpt-4o",
            system_prompt="Additional memory instructions.",
        )
        summarizer = StrandsMemorySummarizer(
            model=mock_model,
            config=memory_config,
            agent_config=agent_config,
        )

        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.THREAD, MemoryType.SHORT_TERM
        )

        assert "You are a friendly bot." in result
        assert "Additional memory instructions." in result

    def test_includes_memory_type_long_term_guidelines(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes long-term memory guidelines."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.CHANNEL, MemoryType.LONG_TERM
        )

        assert "長期記憶" in result

    def test_includes_memory_type_short_term_guidelines(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes short-term memory guidelines."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.CHANNEL, MemoryType.SHORT_TERM
        )

        assert "短期記憶" in result

    def test_includes_scope_thread_guidelines(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes thread scope guidelines."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.THREAD, MemoryType.SHORT_TERM
        )

        assert "スレッド" in result

    def test_includes_scope_channel_guidelines(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes channel scope guidelines."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.CHANNEL, MemoryType.SHORT_TERM
        )

        assert "チャンネル" in result

    def test_includes_scope_workspace_guidelines(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes workspace scope guidelines."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.WORKSPACE, MemoryType.SHORT_TERM
        )

        assert "ワークスペース" in result

    def test_includes_basic_rules(
        self,
        summarizer: StrandsMemorySummarizer,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes basic summarization rules."""
        result = summarizer.build_system_prompt(
            sample_context, MemoryScope.THREAD, MemoryType.SHORT_TERM
        )

        assert "要約" in result
        assert "箇条書き" in result


class TestBuildQueryPrompt:
    """Tests for StrandsMemorySummarizer.build_query_prompt method."""

    def test_thread_scope_query(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for thread scope."""
        thread_ts = "1234567890.000001"
        messages = [
            Message(
                id="1234567890.000002",
                channel=sample_channel,
                user=sample_user,
                text="Thread message content",
                timestamp=timestamp,
                thread_ts=thread_ts,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            thread_messages={thread_ts: messages},
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=thread_ts,
        )

        result = summarizer.build_query_prompt(
            context, MemoryScope.THREAD, MemoryType.SHORT_TERM, None
        )

        assert "要約対象スレッド" in result
        assert thread_ts in result
        assert "Thread message content" in result

    def test_channel_short_term_query(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for channel short-term memory."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Channel message content",
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

        result = summarizer.build_query_prompt(
            context, MemoryScope.CHANNEL, MemoryType.SHORT_TERM, None
        )

        assert "チャンネル会話履歴" in result
        assert "Channel message content" in result
        assert f"#{sample_channel.name}" in result

    def test_channel_long_term_with_existing_memory(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt for channel long-term with existing memory."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory=None,
                short_term_memory="Recent events to integrate",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        result = summarizer.build_query_prompt(
            context,
            MemoryScope.CHANNEL,
            MemoryType.LONG_TERM,
            existing_memory="Previous history content",
        )

        assert "既存のチャンネル長期記憶" in result
        assert "Previous history content" in result
        assert "統合対象" in result
        assert "Recent events to integrate" in result

    def test_workspace_short_term_query(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt for workspace short-term memory."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory=None,
                short_term_memory="General channel recent events",
            ),
            "C456": ChannelMemory(
                channel_id="C456",
                channel_name="random",
                long_term_memory=None,
                short_term_memory="Random channel recent events",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        result = summarizer.build_query_prompt(
            context, MemoryScope.WORKSPACE, MemoryType.SHORT_TERM, None
        )

        assert "各チャンネルの短期記憶" in result
        assert "#general" in result
        assert "General channel recent events" in result
        assert "#random" in result
        assert "Random channel recent events" in result

    def test_workspace_long_term_query(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt for workspace long-term memory."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="General channel history",
                short_term_memory=None,
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            channel_memories=channel_memories,
        )

        result = summarizer.build_query_prompt(
            context,
            MemoryScope.WORKSPACE,
            MemoryType.LONG_TERM,
            existing_memory="Previous workspace history",
        )

        assert "既存のワークスペース長期記憶" in result
        assert "Previous workspace history" in result
        assert "#general" in result
        assert "General channel history" in result

    def test_thread_scope_with_memories(
        self,
        summarizer: StrandsMemorySummarizer,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for thread scope includes workspace/channel memories."""
        thread_ts = "1234567890.000001"
        messages = [
            Message(
                id="1234567890.000002",
                channel=sample_channel,
                user=sample_user,
                text="Thread message",
                timestamp=timestamp,
                thread_ts=thread_ts,
                mentions=[],
            ),
        ]
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            thread_messages={thread_ts: messages},
        )
        channel_memories = {
            sample_channel.id: ChannelMemory(
                channel_id=sample_channel.id,
                channel_name=sample_channel.name,
                long_term_memory="Channel history",
                short_term_memory="Channel recent",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=thread_ts,
            workspace_long_term_memory="Workspace history",
            workspace_short_term_memory="Workspace recent",
            channel_memories=channel_memories,
        )

        result = summarizer.build_query_prompt(
            context, MemoryScope.THREAD, MemoryType.SHORT_TERM, None
        )

        assert "ワークスペースの歴史" in result
        assert "Workspace history" in result
        assert "ワークスペースの最近の出来事" in result
        assert "Workspace recent" in result
