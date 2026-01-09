"""Tests for ReplyToMentionUseCase."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.config import PersonaConfig
from myao2.domain.entities import (
    Channel,
    Context,
    GenerationResult,
    JudgmentCache,
    Message,
    User,
)
from myao2.domain.entities.channel_messages import ChannelMessages


@pytest.fixture
def bot_user_id() -> str:
    """Bot's user ID."""
    return "B001"


@pytest.fixture
def mock_messaging_service() -> Mock:
    """Create mock messaging service."""
    service = Mock()
    service.send_message = AsyncMock()
    return service


@pytest.fixture
def mock_response_generator() -> Mock:
    """Create mock response generator."""
    generator = Mock()
    generator.generate = AsyncMock(
        return_value=GenerationResult(text="Nice to meet you!")
    )
    return generator


@pytest.fixture
def mock_message_repository() -> Mock:
    """Create mock message repository."""
    repo = Mock()
    repo.save = AsyncMock()
    repo.find_by_channel = AsyncMock(return_value=[])
    repo.find_by_thread = AsyncMock(return_value=[])
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_all_in_channel = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_channel_repository() -> Mock:
    """Create mock channel repository."""
    repo = Mock()
    repo.find_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_memory_repository() -> Mock:
    """Create mock memory repository."""
    repo = Mock()
    repo.find_by_scope_and_type = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_judgment_cache_repository() -> Mock:
    """Create mock judgment cache repository."""
    repo = Mock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def persona() -> PersonaConfig:
    """Create persona config."""
    return PersonaConfig(
        name="TestBot",
        system_prompt="You are a friendly bot.",
    )


@pytest.fixture
def use_case(
    mock_messaging_service: Mock,
    mock_response_generator: Mock,
    mock_message_repository: Mock,
    mock_channel_repository: Mock,
    mock_memory_repository: Mock,
    persona: PersonaConfig,
    bot_user_id: str,
) -> ReplyToMentionUseCase:
    """Create use case instance."""
    return ReplyToMentionUseCase(
        messaging_service=mock_messaging_service,
        response_generator=mock_response_generator,
        message_repository=mock_message_repository,
        channel_repository=mock_channel_repository,
        memory_repository=mock_memory_repository,
        persona=persona,
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


class TestReplyToMentionUseCase:
    """ReplyToMentionUseCase tests."""

    async def test_mention_in_channel_sends_message(
        self,
        use_case: ReplyToMentionUseCase,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot replies when mentioned in channel."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        mock_messaging_service.send_message.assert_awaited_once_with(
            channel_id=channel.id,
            text="Nice to meet you!",
            thread_ts=None,
        )

    async def test_mention_in_thread_replies_to_thread(
        self,
        use_case: ReplyToMentionUseCase,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot replies to thread when mentioned in thread."""
        thread_ts = "1234567890.123456"
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> help me",
            timestamp=timestamp,
            thread_ts=thread_ts,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        mock_messaging_service.send_message.assert_awaited_once_with(
            channel_id=channel.id,
            text="Nice to meet you!",
            thread_ts=thread_ts,
        )

    async def test_no_mention_does_nothing(
        self,
        use_case: ReplyToMentionUseCase,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that bot does not reply when not mentioned."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Hello everyone!",
            timestamp=timestamp,
            mentions=["U999"],  # Other user mentioned
        )

        await use_case.execute(message)

        mock_messaging_service.send_message.assert_not_awaited()
        mock_message_repository.save.assert_not_awaited()

    async def test_bot_message_ignored(
        self,
        use_case: ReplyToMentionUseCase,
        mock_messaging_service: Mock,
        mock_message_repository: Mock,
        channel: Channel,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot ignores its own messages."""
        bot_user = User(id=bot_user_id, name="Bot", is_bot=True)
        message = Message(
            id="M001",
            channel=channel,
            user=bot_user,
            text=f"<@{bot_user_id}> I mentioned myself",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        mock_messaging_service.send_message.assert_not_awaited()
        mock_message_repository.save.assert_not_awaited()


class TestReplyToMentionUseCaseMessageSaving:
    """Tests for message saving functionality."""

    async def test_saves_received_message(
        self,
        use_case: ReplyToMentionUseCase,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that received message is saved to repository."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        # First save call should be for the received message
        assert mock_message_repository.save.await_count >= 1
        first_save_call = mock_message_repository.save.await_args_list[0]
        saved_message = first_save_call[0][0]
        assert saved_message.id == message.id

    async def test_saves_bot_response_message(
        self,
        use_case: ReplyToMentionUseCase,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
        persona: PersonaConfig,
    ) -> None:
        """Test that bot response is saved to repository."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        # Second save call should be for the bot response
        assert mock_message_repository.save.await_count == 2
        second_save_call = mock_message_repository.save.await_args_list[1]
        saved_response = second_save_call[0][0]
        assert saved_response.text == "Nice to meet you!"
        assert saved_response.user.id == bot_user_id
        assert saved_response.user.is_bot is True


class TestReplyToMentionUseCaseContextBuilding:
    """Tests for Context building."""

    async def test_builds_context_with_history(
        self,
        use_case: ReplyToMentionUseCase,
        mock_response_generator: Mock,
        mock_message_repository: Mock,
        persona: PersonaConfig,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that Context is built with conversation history."""
        # Set up history
        history = [
            Message(
                id="H001",
                channel=channel,
                user=user,
                text="Previous message",
                timestamp=timestamp,
                mentions=[],
            ),
        ]
        mock_message_repository.find_all_in_channel.return_value = history

        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> hello",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        # Verify generate was called with proper Context
        mock_response_generator.generate.assert_awaited_once()
        call_args = mock_response_generator.generate.call_args
        passed_context = call_args.kwargs["context"]

        assert isinstance(passed_context, Context)
        assert passed_context.persona == persona
        # conversation_history is now ChannelMessages
        assert isinstance(passed_context.conversation_history, ChannelMessages)
        assert passed_context.conversation_history.get_all_messages() == history

    async def test_builds_context_with_empty_history(
        self,
        use_case: ReplyToMentionUseCase,
        mock_response_generator: Mock,
        persona: PersonaConfig,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that Context works with empty history."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> hello",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        call_args = mock_response_generator.generate.call_args
        passed_context = call_args.kwargs["context"]

        # conversation_history is now ChannelMessages
        assert isinstance(passed_context.conversation_history, ChannelMessages)
        assert passed_context.conversation_history.get_all_messages() == []


class TestReplyToMentionUseCaseContextGeneration:
    """Tests for context-based response generation."""

    async def test_generates_response_with_context(
        self,
        use_case: ReplyToMentionUseCase,
        mock_response_generator: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that generate is called with context."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> hello",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        mock_response_generator.generate.assert_awaited_once()
        call_args = mock_response_generator.generate.call_args

        assert "context" in call_args.kwargs
        assert isinstance(call_args.kwargs["context"], Context)


class TestReplyToMentionUseCaseJudgmentCache:
    """Tests for judgment cache creation."""

    async def test_creates_judgment_cache_after_reply(
        self,
        mock_messaging_service: Mock,
        mock_response_generator: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_repository: Mock,
        mock_judgment_cache_repository: Mock,
        persona: PersonaConfig,
        bot_user_id: str,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment cache is created after successful reply."""
        use_case = ReplyToMentionUseCase(
            messaging_service=mock_messaging_service,
            response_generator=mock_response_generator,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            memory_repository=mock_memory_repository,
            persona=persona,
            bot_user_id=bot_user_id,
            judgment_cache_repository=mock_judgment_cache_repository,
        )

        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        # Verify judgment cache was saved
        mock_judgment_cache_repository.save.assert_awaited_once()
        saved_cache = mock_judgment_cache_repository.save.call_args[0][0]
        assert isinstance(saved_cache, JudgmentCache)
        assert saved_cache.channel_id == channel.id
        assert saved_cache.thread_ts is None  # Top-level message
        assert saved_cache.should_respond is True
        assert saved_cache.confidence == 1.0
        assert saved_cache.reason == "Responded to mention"

    async def test_creates_judgment_cache_with_thread_ts(
        self,
        mock_messaging_service: Mock,
        mock_response_generator: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_repository: Mock,
        mock_judgment_cache_repository: Mock,
        persona: PersonaConfig,
        bot_user_id: str,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that judgment cache includes thread_ts for thread replies."""
        use_case = ReplyToMentionUseCase(
            messaging_service=mock_messaging_service,
            response_generator=mock_response_generator,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            memory_repository=mock_memory_repository,
            persona=persona,
            bot_user_id=bot_user_id,
            judgment_cache_repository=mock_judgment_cache_repository,
        )

        thread_ts = "1234567890.123456"
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> help me",
            timestamp=timestamp,
            thread_ts=thread_ts,
            mentions=[bot_user_id],
        )

        await use_case.execute(message)

        # Verify judgment cache includes thread_ts
        mock_judgment_cache_repository.save.assert_awaited_once()
        saved_cache = mock_judgment_cache_repository.save.call_args[0][0]
        assert saved_cache.thread_ts == thread_ts

    async def test_does_not_create_cache_without_repository(
        self,
        use_case: ReplyToMentionUseCase,
        mock_messaging_service: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that cache creation is skipped when repository is not provided."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        # Should not raise any errors
        await use_case.execute(message)

        # Messaging should still work
        mock_messaging_service.send_message.assert_awaited_once()
