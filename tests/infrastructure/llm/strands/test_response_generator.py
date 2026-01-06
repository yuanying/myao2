"""Tests for StrandsResponseGenerator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from myao2.config.models import AgentConfig, PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.memo import Memo
from myao2.infrastructure.llm.exceptions import LLMError
from myao2.infrastructure.llm.strands.memo_tools import MemoToolsFactory
from myao2.infrastructure.llm.strands.response_generator import StrandsResponseGenerator


@pytest.fixture
def mock_model() -> MagicMock:
    """Create mock LiteLLMModel."""
    return MagicMock()


@pytest.fixture
def generator(mock_model: MagicMock) -> StrandsResponseGenerator:
    """Create generator instance."""
    return StrandsResponseGenerator(model=mock_model)


class TestStrandsResponseGenerator:
    """Tests for StrandsResponseGenerator.generate method."""

    async def test_generate_basic(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test basic response generation."""
        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Hello! Nice to meet you.")
            mock_agent_class.return_value = mock_agent

            result = await generator.generate(context=sample_context)

            assert result.text == "Hello! Nice to meet you."
            assert result.metrics is not None
            mock_agent.invoke_async.assert_awaited_once()

    async def test_generate_top_level_reply(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test generation for top-level reply."""
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
            target_thread_ts=None,
        )

        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Hello!")
            mock_agent_class.return_value = mock_agent

            result = await generator.generate(context=context)

            assert result.text == "Hello!"
            # Check that query prompt contains top-level instruction
            call_args = mock_agent.invoke_async.call_args
            query_prompt = call_args.args[0]
            assert "返信対象: トップレベル" in query_prompt
            assert "返信対象メッセージに返答してください" in query_prompt

    async def test_generate_thread_reply(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test generation for thread reply."""
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
                    text="Thread reply",
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

        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Thread response!")
            mock_agent_class.return_value = mock_agent

            result = await generator.generate(context=context)

            assert result.text == "Thread response!"
            # Check that query prompt contains thread instruction
            call_args = mock_agent.invoke_async.call_args
            query_prompt = call_args.args[0]
            assert "返信対象スレッド: 1234567890.000001" in query_prompt
            assert "返信対象スレッドに返答してください" in query_prompt

    async def test_generate_propagates_error(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that LLM errors are properly mapped."""
        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(side_effect=Exception("API error"))
            mock_agent_class.return_value = mock_agent

            with pytest.raises(LLMError):
                await generator.generate(context=sample_context)

    async def test_generate_agent_receives_system_prompt(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that Agent is created with correct system prompt."""
        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Response")
            mock_agent_class.return_value = mock_agent

            await generator.generate(context=sample_context)

            # Check Agent constructor was called with correct arguments
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs["model"] == mock_model
            assert "You are a friendly bot." in call_kwargs["system_prompt"]

    async def test_generate_agent_receives_query_prompt(
        self,
        generator: StrandsResponseGenerator,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that invoke_async is called with correct query prompt."""
        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Response")
            mock_agent_class.return_value = mock_agent

            await generator.generate(context=sample_context)

            # Check invoke_async was called
            mock_agent.invoke_async.assert_awaited_once()
            call_args = mock_agent.invoke_async.call_args.args
            query_prompt = call_args[0]
            # Query prompt should contain conversation section
            assert "## 現在の会話" in query_prompt


class TestBuildSystemPrompt:
    """Tests for StrandsResponseGenerator.build_system_prompt method."""

    def test_build_system_prompt_with_persona(
        self,
        generator: StrandsResponseGenerator,
        sample_context: Context,
    ) -> None:
        """Test that system prompt contains persona's system prompt."""
        result = generator.build_system_prompt(sample_context)

        assert "You are a friendly bot." in result

    def test_build_system_prompt_with_custom_persona(
        self,
        mock_model: MagicMock,
    ) -> None:
        """Test system prompt with custom persona."""
        generator = StrandsResponseGenerator(model=mock_model)
        persona = PersonaConfig(
            name="custom",
            system_prompt="You are a helpful assistant.",
        )
        context = Context(
            persona=persona,
            conversation_history=ChannelMessages(
                channel_id="C123", channel_name="test"
            ),
        )

        result = generator.build_system_prompt(context)

        assert "You are a helpful assistant." in result

    def test_build_system_prompt_with_agent_system_prompt(
        self,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes agent's system_prompt when provided."""
        agent_config = AgentConfig(
            model_id="openai/gpt-4o",
            system_prompt="Additional instructions for response generation.",
        )
        generator = StrandsResponseGenerator(
            model=mock_model,
            agent_config=agent_config,
        )

        result = generator.build_system_prompt(sample_context)

        # Should include both persona and agent system prompts
        assert "You are a friendly bot." in result
        assert "Additional instructions for response generation." in result

    def test_build_system_prompt_without_agent_system_prompt(
        self,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test system prompt when agent_config has no system_prompt."""
        agent_config = AgentConfig(
            model_id="openai/gpt-4o",
            # No system_prompt
        )
        generator = StrandsResponseGenerator(
            model=mock_model,
            agent_config=agent_config,
        )

        result = generator.build_system_prompt(sample_context)

        # Should only include persona system prompt
        assert "You are a friendly bot." in result


class TestBuildQueryPrompt:
    """Tests for StrandsResponseGenerator.build_query_prompt method."""

    def test_build_query_prompt_without_memories(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt without any memories."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        result = generator.build_query_prompt(context)

        # Should NOT include memory section when no memories
        assert "## 記憶" not in result
        # Should include current conversation section
        assert "## 現在の会話" in result
        assert "#general" in result

    def test_build_query_prompt_with_workspace_memories(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt with workspace memories."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            workspace_long_term_memory="Workspace history content.",
            workspace_short_term_memory="Workspace recent content.",
        )

        result = generator.build_query_prompt(context)

        # Should include workspace long-term memory section
        assert "## ワークスペースの概要" in result
        assert "Workspace history content." in result
        # Short-term memory should NOT be included
        assert "Workspace recent content." not in result

    def test_build_query_prompt_with_channel_memories(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt with channel memories."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
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

        result = generator.build_query_prompt(context)

        # Should include channel short-term memories only
        assert "## 各チャンネルの最近の出来事" in result
        assert "### #general" in result
        assert "Recent events in general." in result
        # Long-term memory should NOT be included
        assert "General channel history." not in result
        # Channel without short-term memory should not appear
        assert "### #random" not in result
        # Channel info section should NOT be included
        assert "## チャンネル情報" not in result

    def test_build_query_prompt_top_level_reply(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for top-level reply."""
        messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Hello!",
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
            target_thread_ts=None,
        )

        result = generator.build_query_prompt(context)

        # Should include top-level reply section
        assert "### 返信対象: トップレベル" in result
        assert "Hello!" in result
        # Should NOT include "### トップレベル" header (thread replies only)
        assert "### トップレベル" not in result.splitlines()
        # Should include instruction for top-level reply
        assert "返信対象メッセージに返答してください" in result

    def test_build_query_prompt_thread_reply(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for thread reply."""
        top_messages = [
            Message(
                id="1234567890.000001",
                channel=sample_channel,
                user=sample_user,
                text="Top level",
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
                    text="Thread reply",
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

        result = generator.build_query_prompt(context)

        # Should include thread reply section
        assert "### 返信対象スレッド: 1234567890.000001" in result
        assert "Thread reply" in result
        # Should include top level messages section
        assert "### トップレベル" in result
        assert "Top level" in result
        # Should include instruction for thread reply
        assert "返信対象スレッドに返答してください" in result


def create_test_memo(
    content: str = "Test memo",
    priority: int = 3,
    tags: list[str] | None = None,
    detail: str | None = None,
) -> Memo:
    """Create a test Memo instance."""
    now = datetime.now(timezone.utc)
    return Memo(
        id=uuid4(),
        content=content,
        priority=priority,
        tags=tags or [],
        detail=detail,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_memo_tools_factory() -> Mock:
    """Create mock MemoToolsFactory."""
    factory = Mock(spec=MemoToolsFactory)
    factory.tools = [Mock(), Mock()]  # 2 mock tools
    factory.get_invocation_state.return_value = {"memo_repository": Mock()}
    return factory


class TestStrandsResponseGeneratorWithTools:
    """Tests for StrandsResponseGenerator with tool integration."""

    async def test_generate_without_tools(
        self,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test generation without memo tools."""
        generator = StrandsResponseGenerator(model=mock_model)

        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Response")
            mock_agent_class.return_value = mock_agent

            result = await generator.generate(context=sample_context)

            assert result.text == "Response"
            # Agent should be created without tools
            call_kwargs = mock_agent_class.call_args.kwargs
            assert "tools" not in call_kwargs or call_kwargs.get("tools") == []

    async def test_generate_with_memo_tools(
        self,
        mock_model: MagicMock,
        sample_context: Context,
        mock_memo_tools_factory: Mock,
    ) -> None:
        """Test generation with memo tools."""
        generator = StrandsResponseGenerator(
            model=mock_model,
            memo_tools_factory=mock_memo_tools_factory,
        )

        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Response with tools")
            mock_agent_class.return_value = mock_agent

            result = await generator.generate(context=sample_context)

            assert result.text == "Response with tools"
            # Agent should be created with tools
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs["tools"] == mock_memo_tools_factory.tools

    async def test_agent_receives_invocation_state(
        self,
        mock_model: MagicMock,
        sample_context: Context,
        mock_memo_tools_factory: Mock,
    ) -> None:
        """Test that Agent.invoke_async receives invocation_state."""
        generator = StrandsResponseGenerator(
            model=mock_model,
            memo_tools_factory=mock_memo_tools_factory,
        )

        with patch(
            "myao2.infrastructure.llm.strands.response_generator.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(return_value="Response")
            mock_agent_class.return_value = mock_agent

            await generator.generate(context=sample_context)

            # invoke_async should be called with invocation_state as kwargs
            mock_agent.invoke_async.assert_awaited_once()
            call_kwargs = mock_agent.invoke_async.call_args.kwargs
            assert "memo_repository" in call_kwargs


class TestBuildQueryPromptWithMemos:
    """Tests for build_query_prompt with memo fields."""

    def test_build_query_prompt_without_memos(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt without memos (section still displayed for guidelines)."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        result = generator.build_query_prompt(context)

        # Should ALWAYS include memo section for guidelines (even without memos)
        assert "## メモ管理" in result
        assert "### メモ管理ガイドライン" in result
        # But should NOT include specific memo lists
        assert "### 重要なメモ（優先度4以上）" not in result
        assert "### 直近のメモ" not in result

    def test_build_query_prompt_with_high_priority_memos_only(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt with high priority memos only."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        memos = [
            create_test_memo("Important memo content", priority=5, tags=["user"]),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            high_priority_memos=memos,
        )

        result = generator.build_query_prompt(context)

        # Should include memo section
        assert "## メモ管理" in result
        assert "### 重要なメモ（優先度4以上）" in result
        assert "Important memo content" in result
        assert "優先度: 5" in result
        assert "タグ: user" in result

    def test_build_query_prompt_with_recent_memos_only(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt with recent memos only."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        memos = [
            create_test_memo("Recent memo content", priority=3),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            recent_memos=memos,
        )

        result = generator.build_query_prompt(context)

        # Should include memo section
        assert "## メモ管理" in result
        assert "### 直近のメモ" in result
        assert "Recent memo content" in result

    def test_build_query_prompt_with_both_memos(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt with both high priority and recent memos."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        high_priority = [
            create_test_memo("High priority memo", priority=5, tags=["important"]),
        ]
        recent = [
            create_test_memo("Recent memo", priority=3),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            high_priority_memos=high_priority,
            recent_memos=recent,
        )

        result = generator.build_query_prompt(context)

        # Should include both sections
        assert "### 重要なメモ（優先度4以上）" in result
        assert "### 直近のメモ" in result
        assert "High priority memo" in result
        assert "Recent memo" in result

    def test_build_query_prompt_shows_detail_marker(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test that detail marker is shown for memos with details."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        memos = [
            create_test_memo(
                "Memo with detail",
                priority=5,
                detail="This is the detailed content",
            ),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            high_priority_memos=memos,
        )

        result = generator.build_query_prompt(context)

        # Should show detail marker
        assert "[詳細あり]" in result

    def test_build_query_prompt_includes_guidelines(
        self,
        generator: StrandsResponseGenerator,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test that memo guidelines are included."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        memos = [
            create_test_memo("Test memo", priority=5),
        ]
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            high_priority_memos=memos,
        )

        result = generator.build_query_prompt(context)

        # Should include guidelines
        assert "### メモ管理ガイドライン" in result
        assert "いつメモすべきか" in result
        assert "優先度の付け方" in result
        assert "主語を明記" in result
