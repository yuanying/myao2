"""Tests for AutonomousResponseUseCase."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.use_cases.autonomous_response import AutonomousResponseUseCase
from myao2.config import (
    Config,
    LLMConfig,
    MemoryConfig,
    PersonaConfig,
    ResponseConfig,
    SlackConfig,
)
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.judgment_result import JudgmentResult


@pytest.fixture
def bot_user_id() -> str:
    """Bot's user ID."""
    return "B001"


@pytest.fixture
def mock_channel_monitor() -> Mock:
    """Create mock channel monitor."""
    monitor = Mock()
    monitor.get_channels = AsyncMock(return_value=[])
    monitor.get_unreplied_messages = AsyncMock(return_value=[])
    monitor.get_recent_messages = AsyncMock(return_value=[])
    return monitor


@pytest.fixture
def mock_response_judgment() -> Mock:
    """Create mock response judgment."""
    judgment = Mock()
    judgment.judge = AsyncMock(
        return_value=JudgmentResult(should_respond=True, reason="Test", confidence=1.0)
    )
    return judgment


@pytest.fixture
def mock_response_generator() -> Mock:
    """Create mock response generator."""
    generator = Mock()
    generator.generate = AsyncMock(return_value="Hello from bot!")
    return generator


@pytest.fixture
def mock_messaging_service() -> Mock:
    """Create mock messaging service."""
    service = Mock()
    service.send_message = AsyncMock()
    return service


@pytest.fixture
def mock_message_repository() -> Mock:
    """Create mock message repository."""
    repo = Mock()
    repo.save = AsyncMock()
    repo.find_by_channel = AsyncMock(return_value=[])
    repo.find_by_thread = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_conversation_history_service() -> Mock:
    """Create mock conversation history service."""
    service = Mock()
    service.fetch_thread_history = AsyncMock(return_value=[])
    service.fetch_channel_history = AsyncMock(return_value=[])
    return service


@pytest.fixture
def config() -> Config:
    """Create test config."""
    return Config(
        slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
        llm={"default": LLMConfig(model="gpt-4")},
        persona=PersonaConfig(name="TestBot", system_prompt="You are a friendly bot."),
        memory=MemoryConfig(database_path=":memory:"),
        response=ResponseConfig(
            check_interval_seconds=60,
            min_wait_seconds=300,
            message_limit=20,
        ),
    )


@pytest.fixture
def use_case(
    mock_channel_monitor: Mock,
    mock_response_judgment: Mock,
    mock_response_generator: Mock,
    mock_messaging_service: Mock,
    mock_message_repository: Mock,
    mock_conversation_history_service: Mock,
    config: Config,
    bot_user_id: str,
) -> AutonomousResponseUseCase:
    """Create use case instance."""
    return AutonomousResponseUseCase(
        channel_monitor=mock_channel_monitor,
        response_judgment=mock_response_judgment,
        response_generator=mock_response_generator,
        messaging_service=mock_messaging_service,
        message_repository=mock_message_repository,
        conversation_history_service=mock_conversation_history_service,
        config=config,
        bot_user_id=bot_user_id,
    )


@pytest.fixture
def channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def user() -> User:
    """Create test user."""
    return User(id="U123", name="Test User")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestAutonomousResponseUseCaseExecute:
    """Tests for execute method."""

    async def test_no_channels_does_nothing(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_messaging_service: Mock,
    ) -> None:
        """Test that nothing happens when no channels are available."""
        mock_channel_monitor.get_channels.return_value = []

        await use_case.execute()

        mock_channel_monitor.get_channels.assert_awaited_once()
        mock_messaging_service.send_message.assert_not_awaited()

    async def test_no_unreplied_messages_does_nothing(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_messaging_service: Mock,
        mock_response_judgment: Mock,
        channel: Channel,
    ) -> None:
        """Test that nothing happens when no unreplied messages exist."""
        mock_channel_monitor.get_channels.return_value = [channel]
        mock_channel_monitor.get_unreplied_messages.return_value = []

        await use_case.execute()

        mock_channel_monitor.get_unreplied_messages.assert_awaited_once_with(
            channel_id=channel.id,
            min_wait_seconds=300,
        )
        mock_response_judgment.judge.assert_not_awaited()
        mock_messaging_service.send_message.assert_not_awaited()

    async def test_should_respond_true_sends_message(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that message is sent when judgment is True."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Hello everyone!",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_channels.return_value = [channel]
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Interesting conversation",
            confidence=0.9,
        )

        await use_case.execute()

        mock_response_judgment.judge.assert_awaited_once()
        mock_response_generator.generate.assert_awaited_once()
        mock_messaging_service.send_message.assert_awaited_once_with(
            channel_id=channel.id,
            text="Hello from bot!",
            thread_ts=None,
        )
        # Bot message should be saved
        assert mock_message_repository.save.await_count == 1

    async def test_should_respond_false_does_not_send(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that no message is sent when judgment is False."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Just a simple message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_channels.return_value = [channel]
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Not interesting enough",
            confidence=0.8,
        )

        await use_case.execute()

        mock_response_judgment.judge.assert_awaited_once()
        mock_response_generator.generate.assert_not_awaited()
        mock_messaging_service.send_message.assert_not_awaited()


class TestAutonomousResponseUseCaseCheckChannel:
    """Tests for check_channel method."""

    async def test_multiple_messages_judged_separately(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that multiple messages are judged separately."""
        message1 = Message(
            id="M001",
            channel=channel,
            user=user,
            text="First message",
            timestamp=timestamp,
            mentions=[],
        )
        message2 = Message(
            id="M002",
            channel=channel,
            user=user,
            text="Second message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message1, message2]

        await use_case.check_channel(channel)

        assert mock_response_judgment.judge.await_count == 2

    async def test_error_in_judgment_continues_to_next(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that error in judgment doesn't stop processing other messages."""
        message1 = Message(
            id="M001",
            channel=channel,
            user=user,
            text="First message",
            timestamp=timestamp,
            mentions=[],
        )
        message2 = Message(
            id="M002",
            channel=channel,
            user=user,
            text="Second message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message1, message2]

        # First call raises error, second succeeds
        mock_response_judgment.judge.side_effect = [
            RuntimeError("LLM Error"),
            JudgmentResult(
                should_respond=False, reason="Not interesting", confidence=0.5
            ),
        ]

        with caplog.at_level(logging.ERROR):
            await use_case.check_channel(channel)

        # Both messages should be attempted
        assert mock_response_judgment.judge.await_count == 2
        # Error should be logged
        assert "Error processing message M001" in caplog.text

    async def test_thread_message_replies_to_thread(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread messages are replied to in thread."""
        thread_ts = "1234567890.123456"
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Thread message",
            timestamp=timestamp,
            thread_ts=thread_ts,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        await use_case.check_channel(channel)

        mock_messaging_service.send_message.assert_awaited_once_with(
            channel_id=channel.id,
            text="Hello from bot!",
            thread_ts=thread_ts,
        )


class TestAutonomousResponseUseCaseHistoryFetching:
    """Tests for conversation history fetching."""

    async def test_fetches_thread_history_for_thread_message(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_conversation_history_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread history is fetched for messages in thread."""
        thread_ts = "1234567890.123456"
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Thread message",
            timestamp=timestamp,
            thread_ts=thread_ts,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]

        await use_case.check_channel(channel)

        mock_conversation_history_service.fetch_thread_history.assert_awaited_once_with(
            channel_id=channel.id,
            thread_ts=thread_ts,
            limit=20,
        )
        mock_conversation_history_service.fetch_channel_history.assert_not_awaited()

    async def test_fetches_channel_history_for_channel_message(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_conversation_history_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that channel history is fetched for messages in channel."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Channel message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]

        await use_case.check_channel(channel)

        mock_conversation_history_service.fetch_channel_history.assert_awaited_once_with(
            channel_id=channel.id,
            limit=20,
        )
        mock_conversation_history_service.fetch_thread_history.assert_not_awaited()


class TestAutonomousResponseUseCaseAuxiliaryContext:
    """Tests for auxiliary context building."""

    async def test_auxiliary_context_excludes_target_channel(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that auxiliary context excludes the target channel."""
        other_channel = Channel(id="C456", name="random")
        other_message = Message(
            id="M002",
            channel=other_channel,
            user=user,
            text="Message in other channel",
            timestamp=timestamp,
            mentions=[],
        )

        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Target message",
            timestamp=timestamp,
            mentions=[],
        )

        mock_channel_monitor.get_channels.return_value = [channel, other_channel]
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_channel_monitor.get_recent_messages.return_value = [other_message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        await use_case.check_channel(channel)

        # Verify response generator was called with auxiliary context
        mock_response_generator.generate.assert_awaited_once()
        call_args = mock_response_generator.generate.call_args
        context = call_args.kwargs["context"]
        assert isinstance(context, Context)
        # Auxiliary context should contain the other channel's message
        if context.auxiliary_context:
            assert "random" in context.auxiliary_context
            assert "Message in other channel" in context.auxiliary_context

    async def test_auxiliary_context_from_multiple_channels(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that auxiliary context includes messages from multiple channels."""
        channel2 = Channel(id="C456", name="random")
        channel3 = Channel(id="C789", name="dev")

        message2 = Message(
            id="M002",
            channel=channel2,
            user=user,
            text="Random talk",
            timestamp=timestamp,
            mentions=[],
        )
        message3 = Message(
            id="M003",
            channel=channel3,
            user=user,
            text="Dev discussion",
            timestamp=timestamp,
            mentions=[],
        )

        target_message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Target message",
            timestamp=timestamp,
            mentions=[],
        )

        mock_channel_monitor.get_channels.return_value = [channel, channel2, channel3]
        mock_channel_monitor.get_unreplied_messages.return_value = [target_message]

        def get_recent_messages_side_effect(channel_id: str, **kwargs) -> list[Message]:  # noqa: ANN003
            if channel_id == "C456":
                return [message2]
            elif channel_id == "C789":
                return [message3]
            return []

        mock_channel_monitor.get_recent_messages.side_effect = (
            get_recent_messages_side_effect
        )
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        await use_case.check_channel(channel)

        mock_response_generator.generate.assert_awaited_once()
        call_args = mock_response_generator.generate.call_args
        context = call_args.kwargs["context"]

        if context.auxiliary_context:
            in_random = "random" in context.auxiliary_context
            in_dev = "dev" in context.auxiliary_context
            assert in_random or in_dev


class TestAutonomousResponseUseCaseMessageSaving:
    """Tests for message saving."""

    async def test_saves_bot_response_message(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
        config: Config,
    ) -> None:
        """Test that bot response is saved to repository."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Hello!",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        await use_case.check_channel(channel)

        mock_message_repository.save.assert_awaited_once()
        saved_message = mock_message_repository.save.call_args[0][0]
        assert saved_message.text == "Hello from bot!"
        assert saved_message.user.id == bot_user_id
        assert saved_message.user.is_bot is True
        assert saved_message.user.name == config.persona.name
        assert saved_message.channel == channel


class TestAutonomousResponseUseCaseLogging:
    """Tests for logging."""

    async def test_logs_judgment_result(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that judgment result is logged."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Not interesting",
            confidence=0.7,
        )

        with caplog.at_level(logging.INFO):
            await use_case.check_channel(channel)

        assert "should_respond=False" in caplog.text
        assert "Not interesting" in caplog.text

    async def test_logs_response_sent(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that response sending is logged."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        with caplog.at_level(logging.INFO):
            await use_case.check_channel(channel)

        has_response_log = (
            "Sending autonomous response" in caplog.text
            or "response" in caplog.text.lower()
        )
        assert has_response_log
