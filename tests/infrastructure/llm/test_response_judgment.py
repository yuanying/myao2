"""Tests for LLMResponseJudgment."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.infrastructure.llm import LLMClient, LLMError
from myao2.infrastructure.llm.response_judgment import LLMResponseJudgment


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.complete = AsyncMock(
        return_value='{"should_respond": true, "reason": "User needs help"}'
    )
    return client


@pytest.fixture
def judgment(mock_client: MagicMock) -> LLMResponseJudgment:
    """Create judgment instance."""
    return LLMResponseJudgment(client=mock_client)


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
def sample_channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_message(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> Message:
    """Create test message."""
    return Message(
        id="1234567890.123456",
        channel=sample_channel,
        user=sample_user,
        text="Hello, can someone help me?",
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
def sample_context(persona_config: PersonaConfig, target_message: Message) -> Context:
    """Create test context with target message in history."""
    channel_messages = ChannelMessages(
        channel_id="C123",
        channel_name="general",
        top_level_messages=[target_message],
    )
    return Context(
        persona=persona_config,
        conversation_history=channel_messages,
        target_thread_ts=None,
    )


@pytest.fixture
def target_message(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> Message:
    """Create target message to judge."""
    return Message(
        id="1234567890.999999",
        channel=sample_channel,
        user=sample_user,
        text="Can someone help me with this issue?",
        timestamp=timestamp,
        thread_ts=None,
        mentions=[],
    )


class TestLLMResponseJudgmentBasic:
    """Basic LLMResponseJudgment tests."""

    async def test_judge_should_respond_true(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test judgment when LLM returns should_respond=true."""
        mock_client.complete = AsyncMock(
            return_value='{"should_respond": true, "reason": "User needs help"}'
        )

        result = await judgment.judge(sample_context)

        assert result.should_respond is True
        assert result.reason == "User needs help"

    async def test_judge_should_respond_false(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test judgment when LLM returns should_respond=false."""
        mock_client.complete = AsyncMock(
            return_value='{"should_respond": false, "reason": "Active conversation"}'
        )

        result = await judgment.judge(sample_context)

        assert result.should_respond is False
        assert result.reason == "Active conversation"

    async def test_judge_calls_llm_client(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that judge calls LLM client."""
        await judgment.judge(sample_context)

        mock_client.complete.assert_awaited_once()


class TestLLMResponseJudgmentJsonParsing:
    """JSON parsing tests for LLMResponseJudgment."""

    async def test_parse_valid_json(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test parsing valid JSON response."""
        mock_client.complete = AsyncMock(
            return_value='{"should_respond": true, "reason": "Valid reason"}'
        )

        result = await judgment.judge(sample_context)

        assert result.should_respond is True
        assert result.reason == "Valid reason"

    async def test_parse_invalid_json_returns_false(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that invalid JSON returns should_respond=False."""
        mock_client.complete = AsyncMock(return_value="not valid json")

        result = await judgment.judge(sample_context)

        assert result.should_respond is False
        assert "parse" in result.reason.lower() or "failed" in result.reason.lower()

    async def test_parse_missing_should_respond_returns_false(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that missing should_respond field returns False."""
        mock_client.complete = AsyncMock(return_value='{"reason": "Some reason"}')

        result = await judgment.judge(sample_context)

        assert result.should_respond is False

    async def test_parse_json_with_extra_text(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test parsing JSON embedded in extra text."""
        response = (
            'Here is my response: {"should_respond": true, "reason": "Help needed"}'
        )
        mock_client.complete = AsyncMock(return_value=response)

        result = await judgment.judge(sample_context)

        # Should extract JSON from response
        assert result.should_respond is True
        assert result.reason == "Help needed"


class TestLLMResponseJudgmentErrorHandling:
    """Error handling tests for LLMResponseJudgment."""

    async def test_llm_error_returns_false(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that LLM errors return should_respond=False."""
        mock_client.complete = AsyncMock(side_effect=LLMError("API error"))

        result = await judgment.judge(sample_context)

        assert result.should_respond is False
        assert "error" in result.reason.lower()


class TestLLMResponseJudgmentPrompt:
    """Prompt construction tests for LLMResponseJudgment."""

    async def test_prompt_has_only_system_message(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that LLM is called with only system message (no user message)."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]

        # Should have exactly one message with role "system"
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    async def test_prompt_contains_current_time(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that prompt contains current time."""
        fixed_time = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

        with patch(
            "myao2.infrastructure.llm.response_judgment.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = fixed_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "2024-06-15" in system_prompt or "2024/06/15" in system_prompt

    async def test_prompt_contains_persona_name(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that prompt contains persona name."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "myao" in system_prompt

    async def test_prompt_contains_persona_system_prompt(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that prompt contains persona's system prompt."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        # Persona's system_prompt should be at the beginning
        assert "You are a friendly bot." in system_prompt

    async def test_prompt_contains_target_message_in_system_prompt(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that system prompt contains target message."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        # Should contain target message in system prompt
        assert "Can someone help me with this issue?" in system_prompt
        # Should contain judgment target section
        assert "判定対象" in system_prompt

    async def test_prompt_contains_message_timestamps(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that system prompt includes message timestamps."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        # Should contain timestamp from the target message
        assert "2024-01-01" in system_prompt or "12:00" in system_prompt

    async def test_prompt_contains_user_names(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that system prompt includes user names."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "testuser" in system_prompt

    async def test_prompt_contains_channel_name(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that system prompt includes channel name."""
        await judgment.judge(sample_context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "#general" in system_prompt


class TestLLMResponseJudgmentMemory:
    """Tests for memory inclusion in prompt."""

    async def test_prompt_contains_workspace_memory(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        persona_config: PersonaConfig,
        target_message: Message,
    ) -> None:
        """Test that prompt contains workspace memory."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[target_message],
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
            workspace_long_term_memory="Project A started in 2024",
            workspace_short_term_memory="Current sprint review",
        )

        await judgment.judge(context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "Project A started in 2024" in system_prompt
        assert "Current sprint review" in system_prompt

    async def test_prompt_contains_channel_memories(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        persona_config: PersonaConfig,
        target_message: Message,
    ) -> None:
        """Test that prompt contains channel memories."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[target_message],
        )
        channel_memories = {
            "C123": ChannelMemory(
                channel_id="C123",
                channel_name="general",
                long_term_memory="Team coordination channel",
                short_term_memory="Weekly standup scheduled",
            ),
        }
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
            channel_memories=channel_memories,
        )

        await judgment.judge(context)

        call_args = mock_client.complete.call_args
        messages = call_args.args[0]
        system_prompt = messages[0]["content"]

        assert "Team coordination channel" in system_prompt
        assert "Weekly standup scheduled" in system_prompt


class TestLLMResponseJudgmentConfidence:
    """Confidence parsing tests for LLMResponseJudgment."""

    async def test_confidence_parsed_from_response(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that confidence is correctly parsed from response."""
        response = (
            '{"should_respond": true, "reason": "Help needed", "confidence": 0.85}'
        )
        mock_client.complete = AsyncMock(return_value=response)

        result = await judgment.judge(sample_context)

        assert result.should_respond is True
        assert result.reason == "Help needed"
        assert result.confidence == 0.85

    async def test_confidence_defaults_to_1_0_when_missing(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that confidence defaults to 1.0 when not provided."""
        mock_client.complete = AsyncMock(
            return_value='{"should_respond": false, "reason": "Not interesting"}'
        )

        result = await judgment.judge(sample_context)

        assert result.should_respond is False
        assert result.confidence == 1.0

    async def test_confidence_clamped_to_max_1_0(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that confidence > 1.0 is clamped to 1.0."""
        response = '{"should_respond": true, "reason": "Very sure", "confidence": 1.5}'
        mock_client.complete = AsyncMock(return_value=response)

        result = await judgment.judge(sample_context)

        assert result.confidence == 1.0

    async def test_confidence_clamped_to_min_0_0(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that confidence < 0.0 is clamped to 0.0."""
        response = (
            '{"should_respond": false, "reason": "Uncertain", "confidence": -0.5}'
        )
        mock_client.complete = AsyncMock(return_value=response)

        result = await judgment.judge(sample_context)

        assert result.confidence == 0.0

    async def test_confidence_0_0_on_parse_failure(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        sample_context: Context,
    ) -> None:
        """Test that confidence is 0.0 when parsing fails."""
        mock_client.complete = AsyncMock(return_value="not valid json at all")

        result = await judgment.judge(sample_context)

        assert result.should_respond is False
        assert result.confidence == 0.0


class TestLLMResponseJudgmentMultipleMessages:
    """Tests with multiple messages in conversation."""

    async def test_multiple_messages_all_shown_in_system_prompt(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
    ) -> None:
        """Test that all messages are shown in system prompt."""
        user2 = User(id="U456", name="another_user", is_bot=False)

        # Create messages - all should be shown (not just the latest)
        history_messages = [
            Message(
                id="1",
                channel=sample_channel,
                user=sample_user,
                text="Hello everyone",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="2",
                channel=sample_channel,
                user=user2,
                text="Hi there!",
                timestamp=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="3",
                channel=sample_channel,
                user=sample_user,
                text="Can anyone help me?",
                timestamp=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
        ]

        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=history_messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
        )

        await judgment.judge(context)

        call_args = mock_client.complete.call_args
        llm_messages = call_args.args[0]
        system_prompt = llm_messages[0]["content"]

        # All user names should be present
        assert "testuser" in system_prompt
        assert "another_user" in system_prompt

        # All messages should be present (not just the latest)
        assert "Hello everyone" in system_prompt
        assert "Hi there!" in system_prompt
        assert "Can anyone help me?" in system_prompt


class TestLLMResponseJudgmentTemplateRendering:
    """Tests for Jinja2 template rendering."""

    def test_template_renders_persona_name(
        self,
        judgment: LLMResponseJudgment,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that template renders persona name correctly."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
        )
        rendered = judgment._template.render(
            persona=persona_config,
            current_time="2024-01-01 12:00:00 UTC",
            current_channel_name="general",
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=None,
            target_thread_messages=[],
            workspace_long_term_memory=None,
            workspace_short_term_memory=None,
            channel_memories=None,
        )
        assert "myao" in rendered

    def test_template_renders_current_time(
        self,
        judgment: LLMResponseJudgment,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that template renders current time correctly."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
        )
        rendered = judgment._template.render(
            persona=persona_config,
            current_time="2024-06-15 14:30:00 UTC",
            current_channel_name="general",
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=None,
            target_thread_messages=[],
            workspace_long_term_memory=None,
            workspace_short_term_memory=None,
            channel_memories=None,
        )
        assert "2024-06-15 14:30:00 UTC" in rendered

    def test_template_contains_judgment_criteria(
        self,
        judgment: LLMResponseJudgment,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that template contains all judgment criteria."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
        )
        rendered = judgment._template.render(
            persona=persona_config,
            current_time="2024-01-01 12:00:00 UTC",
            current_channel_name="general",
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=None,
            target_thread_messages=[],
            workspace_long_term_memory=None,
            workspace_short_term_memory=None,
            channel_memories=None,
        )
        assert "判断基準" in rendered
        assert "誰も反応していないメッセージがあるか" in rendered
        assert "困っている/寂しそうな状況か" in rendered
        assert "有用なアドバイスができそうか" in rendered

    def test_template_contains_json_format_instruction(
        self,
        judgment: LLMResponseJudgment,
        persona_config: PersonaConfig,
    ) -> None:
        """Test that template contains JSON format instructions."""
        channel_messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
        )
        rendered = judgment._template.render(
            persona=persona_config,
            current_time="2024-01-01 12:00:00 UTC",
            current_channel_name="general",
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=None,
            target_thread_messages=[],
            workspace_long_term_memory=None,
            workspace_short_term_memory=None,
            channel_memories=None,
        )
        assert "should_respond" in rendered
        assert "reason" in rendered
        assert "confidence" in rendered


class TestLLMResponseJudgmentThreadTarget:
    """Tests with thread target."""

    async def test_judge_with_thread_target(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
    ) -> None:
        """Test judgment with thread_ts target."""
        thread_ts = "1234567890.000001"

        thread_messages = [
            Message(
                id=thread_ts,
                channel=sample_channel,
                user=sample_user,
                text="Parent message",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="1234567890.000002",
                channel=sample_channel,
                user=sample_user,
                text="Thread reply needing help",
                timestamp=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                thread_ts=thread_ts,
                mentions=[],
            ),
        ]

        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=[],
            thread_messages={thread_ts: thread_messages},
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=thread_ts,
        )

        await judgment.judge(context)

        call_args = mock_client.complete.call_args
        llm_messages = call_args.args[0]
        system_prompt = llm_messages[0]["content"]

        # All thread messages should be shown (not just the latest)
        assert "Parent message" in system_prompt
        assert "Thread reply needing help" in system_prompt
        # Should indicate thread target
        assert "判定対象スレッド" in system_prompt
        assert thread_ts in system_prompt

    async def test_judge_with_top_level_target(
        self,
        judgment: LLMResponseJudgment,
        mock_client: MagicMock,
        persona_config: PersonaConfig,
        sample_user: User,
        sample_channel: Channel,
    ) -> None:
        """Test judgment with top-level target (no thread_ts)."""
        top_level_messages = [
            Message(
                id="1",
                channel=sample_channel,
                user=sample_user,
                text="First message",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="2",
                channel=sample_channel,
                user=sample_user,
                text="Second message",
                timestamp=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
        ]

        channel_messages = ChannelMessages(
            channel_id=sample_channel.id,
            channel_name=sample_channel.name,
            top_level_messages=top_level_messages,
        )
        context = Context(
            persona=persona_config,
            conversation_history=channel_messages,
            target_thread_ts=None,
        )

        await judgment.judge(context)

        call_args = mock_client.complete.call_args
        llm_messages = call_args.args[0]
        system_prompt = llm_messages[0]["content"]

        # All top-level messages should be shown
        assert "First message" in system_prompt
        assert "Second message" in system_prompt
        # Should indicate top-level target
        assert "判定対象: トップレベル会話" in system_prompt
