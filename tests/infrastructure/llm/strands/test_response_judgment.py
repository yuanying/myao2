"""Tests for StrandsResponseJudgment."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myao2.config.models import AgentConfig, PersonaConfig
from myao2.domain.entities import Channel, Context, JudgmentResult, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.infrastructure.llm.exceptions import LLMError
from myao2.infrastructure.llm.strands.models import JudgmentOutput
from myao2.infrastructure.llm.strands.response_judgment import StrandsResponseJudgment


@pytest.fixture
def mock_model() -> MagicMock:
    """Create mock LiteLLMModel."""
    return MagicMock()


@pytest.fixture
def judgment(mock_model: MagicMock) -> StrandsResponseJudgment:
    """Create judgment instance."""
    return StrandsResponseJudgment(model=mock_model)


def create_mock_result(
    should_respond: bool, reason: str, confidence: float
) -> MagicMock:
    """Create a mock Agent result with structured_output."""
    result = MagicMock()
    result.structured_output = JudgmentOutput(
        should_respond=should_respond,
        reason=reason,
        confidence=confidence,
    )
    return result


class TestStrandsResponseJudgment:
    """Tests for StrandsResponseJudgment.judge method."""

    async def test_judge_should_respond_true(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test judgment returns should_respond=True."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result(
                    should_respond=True,
                    reason="User is asking a question",
                    confidence=0.9,
                )
            )
            mock_agent_class.return_value = mock_agent

            result = await judgment.judge(context=sample_context)

            assert isinstance(result, JudgmentResult)
            assert result.should_respond is True
            assert result.reason == "User is asking a question"
            assert result.confidence == 0.9

    async def test_judge_should_respond_false(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test judgment returns should_respond=False."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result(
                    should_respond=False,
                    reason="This is a private conversation",
                    confidence=0.8,
                )
            )
            mock_agent_class.return_value = mock_agent

            result = await judgment.judge(context=sample_context)

            assert result.should_respond is False
            assert result.reason == "This is a private conversation"

    async def test_judge_returns_confidence(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test judgment returns confidence value correctly."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result(
                    should_respond=True,
                    reason="Moderate certainty",
                    confidence=0.65,
                )
            )
            mock_agent_class.return_value = mock_agent

            result = await judgment.judge(context=sample_context)

            assert result.confidence == 0.65

    async def test_judge_agent_receives_system_prompt(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that Agent is created with correct system prompt."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result(
                    should_respond=True, reason="test", confidence=0.9
                )
            )
            mock_agent_class.return_value = mock_agent

            await judgment.judge(context=sample_context)

            # Check Agent constructor was called with correct arguments
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs["model"] == mock_model
            assert "You are a friendly bot." in call_kwargs["system_prompt"]
            # Should contain judgment criteria
            assert "判断基準" in call_kwargs["system_prompt"]

    async def test_judge_uses_structured_output(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that invoke_async is called with structured_output_model."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(
                return_value=create_mock_result(
                    should_respond=True, reason="test", confidence=0.9
                )
            )
            mock_agent_class.return_value = mock_agent

            await judgment.judge(context=sample_context)

            # Check invoke_async was called with structured_output_model
            mock_agent.invoke_async.assert_awaited_once()
            call_kwargs = mock_agent.invoke_async.call_args.kwargs
            assert call_kwargs["structured_output_model"] == JudgmentOutput

    async def test_judge_propagates_error(
        self,
        judgment: StrandsResponseJudgment,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that LLM errors are properly mapped."""
        with patch(
            "myao2.infrastructure.llm.strands.response_judgment.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.invoke_async = AsyncMock(side_effect=Exception("API error"))
            mock_agent_class.return_value = mock_agent

            with pytest.raises(LLMError):
                await judgment.judge(context=sample_context)


class TestBuildSystemPrompt:
    """Tests for StrandsResponseJudgment.build_system_prompt method."""

    def test_build_system_prompt_with_persona(
        self,
        judgment: StrandsResponseJudgment,
        sample_context: Context,
    ) -> None:
        """Test that system prompt contains persona's system prompt."""
        result = judgment.build_system_prompt(sample_context)

        assert "You are a friendly bot." in result
        # Should contain judgment criteria
        assert "判断基準" in result
        assert "confidence" in result

    def test_build_system_prompt_with_custom_persona(
        self,
        mock_model: MagicMock,
    ) -> None:
        """Test system prompt with custom persona."""
        judgment = StrandsResponseJudgment(model=mock_model)
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

        result = judgment.build_system_prompt(context)

        assert "You are a helpful assistant." in result
        assert "判断基準" in result

    def test_build_system_prompt_with_agent_system_prompt(
        self,
        mock_model: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test system prompt includes agent's system_prompt when provided."""
        agent_config = AgentConfig(
            model_id="openai/gpt-4o",
            system_prompt="Additional instructions for judgment.",
        )
        judgment = StrandsResponseJudgment(
            model=mock_model,
            agent_config=agent_config,
        )

        result = judgment.build_system_prompt(sample_context)

        # Should include both persona and agent system prompts
        assert "You are a friendly bot." in result
        assert "Additional instructions for judgment." in result

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
        judgment = StrandsResponseJudgment(
            model=mock_model,
            agent_config=agent_config,
        )

        result = judgment.build_system_prompt(sample_context)

        # Should only include persona system prompt
        assert "You are a friendly bot." in result


class TestBuildQueryPrompt:
    """Tests for StrandsResponseJudgment.build_query_prompt method."""

    def test_build_query_prompt_without_memories(
        self,
        judgment: StrandsResponseJudgment,
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

        result = judgment.build_query_prompt(context)

        # Should NOT include memory section when no memories
        assert "## 記憶" not in result
        # Should include current conversation section
        assert "判定対象" in result
        assert "#general" in result

    def test_build_query_prompt_with_workspace_memories(
        self,
        judgment: StrandsResponseJudgment,
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

        result = judgment.build_query_prompt(context)

        # Should include workspace long-term memory section
        assert "## ワークスペースの概要" in result
        assert "Workspace history content." in result
        # Short-term memory should NOT be included in judgment
        assert "Workspace recent content." not in result

    def test_build_query_prompt_with_channel_memories(
        self,
        judgment: StrandsResponseJudgment,
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

        result = judgment.build_query_prompt(context)

        # Should include channel short-term memories only
        assert "## 各チャンネルの最近の出来事" in result
        assert "### #general" in result
        assert "Recent events in general." in result
        # Long-term memory should NOT be included in judgment
        assert "General channel history." not in result
        # Channel without short-term memory should not appear
        assert "### #random" not in result
        # Channel info section should NOT be included
        assert "## チャンネル情報" not in result

    def test_build_query_prompt_includes_current_time(
        self,
        judgment: StrandsResponseJudgment,
        persona_config: PersonaConfig,
        sample_channel: Channel,
    ) -> None:
        """Test query prompt includes current time."""
        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
        )

        result = judgment.build_query_prompt(context)

        assert "現在時刻:" in result
        # Should contain UTC time format
        assert "UTC" in result

    def test_build_query_prompt_top_level_judgment(
        self,
        judgment: StrandsResponseJudgment,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for top-level judgment."""
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

        result = judgment.build_query_prompt(context)

        # Should include top-level judgment section
        assert "## 判定対象: トップレベル会話" in result
        assert "Hello!" in result
        # Should include judgment instruction
        assert "応答すべきかを判断してください" in result

    def test_build_query_prompt_thread_judgment(
        self,
        judgment: StrandsResponseJudgment,
        persona_config: PersonaConfig,
        sample_channel: Channel,
        sample_user: User,
        timestamp: datetime,
    ) -> None:
        """Test query prompt for thread judgment."""
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

        result = judgment.build_query_prompt(context)

        # Should include thread judgment section
        assert "## 判定対象スレッド: 1234567890.000001" in result
        assert "Thread reply" in result
        # Should include top level messages section
        assert "### トップレベル" in result
        assert "Top level" in result
        # Should include judgment instruction
        assert "応答すべきかを判断してください" in result
