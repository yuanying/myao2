"""Tests for AutonomousResponseUseCase."""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.use_cases.autonomous_response import AutonomousResponseUseCase
from myao2.config import (
    Config,
    JudgmentSkipConfig,
    JudgmentSkipThreshold,
    LLMConfig,
    MemoryConfig,
    PersonaConfig,
    ResponseConfig,
    SlackConfig,
)
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMessages
from myao2.domain.entities.judgment_cache import JudgmentCache
from myao2.domain.entities.judgment_result import JudgmentResult
from myao2.domain.exceptions import ChannelNotAccessibleError


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
    repo.find_all_in_channel = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_judgment_cache_repository() -> Mock:
    """Create mock judgment cache repository."""
    repo = Mock()
    repo.save = AsyncMock()
    repo.find_by_scope = AsyncMock(return_value=None)
    repo.delete_by_scope = AsyncMock()
    repo.delete_expired = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_channel_repository() -> Mock:
    """Create mock channel repository."""
    repo = Mock()
    repo.delete = AsyncMock(return_value=True)
    repo.find_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_memory_repository() -> Mock:
    """Create mock memory repository."""
    repo = Mock()
    repo.find_by_scope_and_type = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_channel_sync_service() -> Mock:
    """Create mock channel sync service."""
    service = Mock()
    service.sync_with_cleanup = AsyncMock(return_value=([], []))
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
    mock_judgment_cache_repository: Mock,
    mock_channel_repository: Mock,
    mock_memory_repository: Mock,
    mock_channel_sync_service: Mock,
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
        judgment_cache_repository=mock_judgment_cache_repository,
        channel_repository=mock_channel_repository,
        memory_repository=mock_memory_repository,
        config=config,
        bot_user_id=bot_user_id,
        channel_sync_service=mock_channel_sync_service,
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
            max_message_age_seconds=43200,
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


class TestAutonomousResponseUseCaseContextBuilding:
    """Tests for context building."""

    async def test_context_uses_channel_messages_structure(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that context uses ChannelMessages structure."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Target message",
            timestamp=timestamp,
            mentions=[],
        )

        mock_channel_monitor.get_channels.return_value = [channel]
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=True,
            reason="Reply needed",
            confidence=0.9,
        )

        await use_case.check_channel(channel)

        # Verify response generator was called with ChannelMessages-based context
        mock_response_generator.generate.assert_awaited_once()
        call_args = mock_response_generator.generate.call_args
        context = call_args.kwargs["context"]
        assert isinstance(context, Context)
        # conversation_history should be ChannelMessages
        assert isinstance(context.conversation_history, ChannelMessages)
        assert context.conversation_history.channel_id == channel.id
        assert context.conversation_history.channel_name == channel.name


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


class TestAutonomousResponseUseCaseJudgmentSkip:
    """Tests for judgment skip functionality."""

    @pytest.fixture
    def config_with_skip(self) -> Config:
        """Create test config with judgment skip enabled."""
        return Config(
            slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
            llm={"default": LLMConfig(model="gpt-4")},
            persona=PersonaConfig(
                name="TestBot", system_prompt="You are a friendly bot."
            ),
            memory=MemoryConfig(database_path=":memory:"),
            response=ResponseConfig(
                check_interval_seconds=60,
                min_wait_seconds=300,
                message_limit=20,
                judgment_skip=JudgmentSkipConfig(
                    enabled=True,
                    thresholds=[
                        JudgmentSkipThreshold(min_confidence=0.9, skip_seconds=43200),
                        JudgmentSkipThreshold(min_confidence=0.7, skip_seconds=3600),
                    ],
                    default_skip_seconds=600,
                ),
            ),
        )

    @pytest.fixture
    def config_skip_disabled(self) -> Config:
        """Create test config with judgment skip disabled."""
        return Config(
            slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
            llm={"default": LLMConfig(model="gpt-4")},
            persona=PersonaConfig(
                name="TestBot", system_prompt="You are a friendly bot."
            ),
            memory=MemoryConfig(database_path=":memory:"),
            response=ResponseConfig(
                check_interval_seconds=60,
                min_wait_seconds=300,
                message_limit=20,
                judgment_skip=JudgmentSkipConfig(enabled=False),
            ),
        )

    @pytest.fixture
    def use_case_with_skip(
        self,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        mock_judgment_cache_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_repository: Mock,
        config_with_skip: Config,
        bot_user_id: str,
    ) -> AutonomousResponseUseCase:
        """Create use case instance with skip enabled."""
        return AutonomousResponseUseCase(
            channel_monitor=mock_channel_monitor,
            response_judgment=mock_response_judgment,
            response_generator=mock_response_generator,
            messaging_service=mock_messaging_service,
            message_repository=mock_message_repository,
            judgment_cache_repository=mock_judgment_cache_repository,
            channel_repository=mock_channel_repository,
            memory_repository=mock_memory_repository,
            config=config_with_skip,
            bot_user_id=bot_user_id,
        )

    @pytest.fixture
    def use_case_skip_disabled(
        self,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_response_generator: Mock,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        mock_judgment_cache_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_repository: Mock,
        config_skip_disabled: Config,
        bot_user_id: str,
    ) -> AutonomousResponseUseCase:
        """Create use case instance with skip disabled."""
        return AutonomousResponseUseCase(
            channel_monitor=mock_channel_monitor,
            response_judgment=mock_response_judgment,
            response_generator=mock_response_generator,
            messaging_service=mock_messaging_service,
            message_repository=mock_message_repository,
            judgment_cache_repository=mock_judgment_cache_repository,
            channel_repository=mock_channel_repository,
            memory_repository=mock_memory_repository,
            config=config_skip_disabled,
            bot_user_id=bot_user_id,
        )

    async def test_skip_disabled_always_judges(
        self,
        use_case_skip_disabled: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment is always performed when skip is disabled."""
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
            confidence=0.9,
        )

        await use_case_skip_disabled.check_channel(channel)

        # Judgment should be called even if cache exists
        mock_response_judgment.judge.assert_awaited_once()
        # Cache should not be saved when disabled
        mock_judgment_cache_repository.save.assert_not_awaited()

    async def test_no_cache_performs_judgment_and_saves_cache(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment is performed and cache is saved when no cache exists."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_judgment_cache_repository.find_by_scope.return_value = None
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Not interesting",
            confidence=0.85,
        )

        await use_case_with_skip.check_channel(channel)

        # Judgment should be called
        mock_response_judgment.judge.assert_awaited_once()
        # Cache should be saved
        mock_judgment_cache_repository.save.assert_awaited_once()

    async def test_valid_cache_skips_judgment(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment is skipped when valid cache exists."""
        message = Message(
            id="M001",  # Same as cached latest_message_ts
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]

        # Create a valid cache (future next_check_at, same message)
        valid_cache = JudgmentCache(
            channel_id=channel.id,
            thread_ts=None,
            should_respond=False,
            confidence=0.9,
            reason="Previously judged",
            latest_message_ts="M001",  # Same as message.id
            next_check_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_judgment_cache_repository.find_by_scope.return_value = valid_cache

        await use_case_with_skip.check_channel(channel)

        # Judgment should NOT be called (skipped)
        mock_response_judgment.judge.assert_not_awaited()

    async def test_expired_cache_performs_judgment(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment is performed when cache is expired."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]

        # Create an expired cache
        expired_cache = JudgmentCache(
            channel_id=channel.id,
            thread_ts=None,
            should_respond=False,
            confidence=0.9,
            reason="Previously judged",
            latest_message_ts="M001",
            next_check_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        mock_judgment_cache_repository.find_by_scope.return_value = expired_cache
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Re-judged",
            confidence=0.8,
        )

        await use_case_with_skip.check_channel(channel)

        # Judgment should be called (cache expired)
        mock_response_judgment.judge.assert_awaited_once()
        # New cache should be saved
        mock_judgment_cache_repository.save.assert_awaited_once()

    async def test_new_message_invalidates_cache(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that new message invalidates cache and triggers judgment."""
        message = Message(
            id="M002",  # Different from cached latest_message_ts
            channel=channel,
            user=user,
            text="New message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]

        # Create a cache with different message ID
        stale_cache = JudgmentCache(
            channel_id=channel.id,
            thread_ts=None,
            should_respond=False,
            confidence=0.9,
            reason="Previously judged",
            latest_message_ts="M001",  # Different from message.id
            # Still valid by time
            next_check_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_judgment_cache_repository.find_by_scope.return_value = stale_cache
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Re-judged due to new message",
            confidence=0.7,
        )

        await use_case_with_skip.check_channel(channel)

        # Judgment should be called (new message arrived)
        mock_response_judgment.judge.assert_awaited_once()

    async def test_high_confidence_gets_longer_skip(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that high confidence results in longer skip time."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_judgment_cache_repository.find_by_scope.return_value = None
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Very sure",
            confidence=0.95,  # >= 0.9 threshold
        )

        await use_case_with_skip.check_channel(channel)

        # Check that cache was saved with appropriate skip time
        mock_judgment_cache_repository.save.assert_awaited_once()
        saved_cache = mock_judgment_cache_repository.save.call_args[0][0]
        assert isinstance(saved_cache, JudgmentCache)
        # 0.95 confidence should get 43200 seconds (12 hours) skip
        expected_skip = timedelta(seconds=43200)
        actual_skip = saved_cache.next_check_at - saved_cache.created_at
        # Allow small tolerance for execution time
        assert abs(actual_skip.total_seconds() - expected_skip.total_seconds()) < 5

    async def test_medium_confidence_gets_medium_skip(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that medium confidence results in medium skip time."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_judgment_cache_repository.find_by_scope.return_value = None
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Somewhat sure",
            confidence=0.8,  # >= 0.7 but < 0.9 threshold
        )

        await use_case_with_skip.check_channel(channel)

        # Check that cache was saved with appropriate skip time
        mock_judgment_cache_repository.save.assert_awaited_once()
        saved_cache = mock_judgment_cache_repository.save.call_args[0][0]
        # 0.8 confidence should get 3600 seconds (1 hour) skip
        expected_skip = timedelta(seconds=3600)
        actual_skip = saved_cache.next_check_at - saved_cache.created_at
        assert abs(actual_skip.total_seconds() - expected_skip.total_seconds()) < 5

    async def test_low_confidence_gets_default_skip(
        self,
        use_case_with_skip: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_judgment_cache_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that low confidence results in default skip time."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Test message",
            timestamp=timestamp,
            mentions=[],
        )
        mock_channel_monitor.get_unreplied_messages.return_value = [message]
        mock_judgment_cache_repository.find_by_scope.return_value = None
        mock_response_judgment.judge.return_value = JudgmentResult(
            should_respond=False,
            reason="Not sure",
            confidence=0.5,  # < 0.7 threshold
        )

        await use_case_with_skip.check_channel(channel)

        # Check that cache was saved with default skip time
        mock_judgment_cache_repository.save.assert_awaited_once()
        saved_cache = mock_judgment_cache_repository.save.call_args[0][0]
        # 0.5 confidence should get 600 seconds (10 minutes) skip
        expected_skip = timedelta(seconds=600)
        actual_skip = saved_cache.next_check_at - saved_cache.created_at
        assert abs(actual_skip.total_seconds() - expected_skip.total_seconds()) < 5


class TestAutonomousResponseUseCaseChannelNotAccessible:
    """Tests for ChannelNotAccessibleError handling."""

    async def test_channel_not_accessible_removes_channel_from_db(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_messaging_service: Mock,
        mock_channel_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that ChannelNotAccessibleError removes channel from DB."""
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
        # Simulate ChannelNotAccessibleError when sending message
        mock_messaging_service.send_message.side_effect = ChannelNotAccessibleError(
            channel.id
        )

        await use_case.check_channel(channel)

        # Channel should be removed from DB
        mock_channel_repository.delete.assert_awaited_once_with(channel.id)

    async def test_channel_not_accessible_does_not_save_bot_message(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that bot message is not saved when ChannelNotAccessibleError occurs."""
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
        mock_messaging_service.send_message.side_effect = ChannelNotAccessibleError(
            channel.id
        )

        await use_case.check_channel(channel)

        # Bot message should NOT be saved
        mock_message_repository.save.assert_not_awaited()

    async def test_channel_not_accessible_logs_warning(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_response_judgment: Mock,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that ChannelNotAccessibleError is logged as warning."""
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
        mock_messaging_service.send_message.side_effect = ChannelNotAccessibleError(
            channel.id
        )

        with caplog.at_level(logging.WARNING):
            await use_case.check_channel(channel)

        assert (
            "no longer accessible" in caplog.text or "removing" in caplog.text.lower()
        )


class TestAutonomousResponseUseCaseChannelSync:
    """Tests for channel synchronization functionality."""

    async def test_execute_calls_sync_with_cleanup(
        self,
        use_case: AutonomousResponseUseCase,
        mock_channel_monitor: Mock,
        mock_channel_sync_service: Mock,
    ) -> None:
        """Test that execute calls sync_with_cleanup."""
        mock_channel_monitor.get_channels.return_value = []

        await use_case.execute()

        mock_channel_sync_service.sync_with_cleanup.assert_awaited_once()
