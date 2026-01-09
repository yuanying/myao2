"""Tests for MessageEventHandler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.application.handlers.message_handler import MessageEventHandler
from myao2.config import PersonaConfig
from myao2.domain.entities import Channel, Event, EventType, Message, User
from myao2.domain.entities.llm_metrics import LLMMetrics


class TestMessageEventHandler:
    """Tests for MessageEventHandler."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed timestamp."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def persona(self) -> PersonaConfig:
        """Create test persona configuration."""
        return PersonaConfig(
            name="TestBot",
            system_prompt="You are a helpful assistant.",
        )

    @pytest.fixture
    def bot_user_id(self) -> str:
        """Create bot user ID."""
        return "U_BOT"

    @pytest.fixture
    def messaging_service(self) -> AsyncMock:
        """Create mock messaging service."""
        return AsyncMock()

    @pytest.fixture
    def response_generator(self) -> AsyncMock:
        """Create mock response generator."""
        mock = AsyncMock()
        mock.generate = AsyncMock(
            return_value=MagicMock(
                text="Hello!",
                metrics=LLMMetrics(
                    input_tokens=50,
                    output_tokens=50,
                    total_tokens=100,
                ),
            )
        )
        return mock

    @pytest.fixture
    def message_repository(self) -> AsyncMock:
        """Create mock message repository."""
        return AsyncMock()

    @pytest.fixture
    def channel_repository(self) -> AsyncMock:
        """Create mock channel repository."""
        return AsyncMock()

    @pytest.fixture
    def memory_repository(self) -> AsyncMock:
        """Create mock memory repository."""
        mock = AsyncMock()
        mock.find_by_scope_and_type = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def judgment_cache_repository(self) -> AsyncMock:
        """Create mock judgment cache repository."""
        return AsyncMock()

    @pytest.fixture
    def handler(
        self,
        messaging_service: AsyncMock,
        response_generator: AsyncMock,
        message_repository: AsyncMock,
        channel_repository: AsyncMock,
        memory_repository: AsyncMock,
        persona: PersonaConfig,
        bot_user_id: str,
        judgment_cache_repository: AsyncMock,
    ) -> MessageEventHandler:
        """Create handler instance."""
        return MessageEventHandler(
            messaging_service=messaging_service,
            response_generator=response_generator,
            message_repository=message_repository,
            channel_repository=channel_repository,
            memory_repository=memory_repository,
            persona=persona,
            bot_user_id=bot_user_id,
            judgment_cache_repository=judgment_cache_repository,
        )

    def test_has_event_handler_decorator(self, handler: MessageEventHandler) -> None:
        """Test that handle method has event_handler decorator."""
        assert hasattr(handler.handle, "_event_type")
        assert handler.handle._event_type == EventType.MESSAGE

    async def test_handle_processes_message_event(
        self,
        handler: MessageEventHandler,
        messaging_service: AsyncMock,
        response_generator: AsyncMock,
        message_repository: AsyncMock,
        channel_repository: AsyncMock,
        now: datetime,
    ) -> None:
        """Test that handler processes MESSAGE event correctly."""
        channel = Channel(id="C123", name="general")
        user = User(id="U123", name="user1")
        message = Message(
            id="1234567890.123456",
            channel=channel,
            user=user,
            text="Hello <@U_BOT>",
            timestamp=now,
        )

        # Setup mocks
        channel_repository.find_by_id = AsyncMock(return_value=channel)
        message_repository.find_by_thread = AsyncMock(return_value=[message])
        message_repository.find_by_channel_since = AsyncMock(return_value=[])

        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "1234567890.123456",
                "message": message,
            },
            created_at=now,
        )

        await handler.handle(event)

        # Verify message was saved
        assert message_repository.save.called

        # Verify response was generated
        assert response_generator.generate.called

        # Verify message was sent
        messaging_service.send_message.assert_called_once()
        call_args = messaging_service.send_message.call_args
        assert call_args.kwargs["channel_id"] == "C123"
        assert call_args.kwargs["text"] == "Hello!"

    async def test_handle_creates_judgment_cache(
        self,
        handler: MessageEventHandler,
        judgment_cache_repository: AsyncMock,
        channel_repository: AsyncMock,
        message_repository: AsyncMock,
        now: datetime,
    ) -> None:
        """Test that handler creates judgment cache after reply."""
        channel = Channel(id="C123", name="general")
        user = User(id="U123", name="user1")
        message = Message(
            id="1234567890.123456",
            channel=channel,
            user=user,
            text="Hello <@U_BOT>",
            timestamp=now,
        )

        channel_repository.find_by_id = AsyncMock(return_value=channel)
        message_repository.find_by_thread = AsyncMock(return_value=[message])
        message_repository.find_by_channel_since = AsyncMock(return_value=[])

        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "1234567890.123456",
                "message": message,
            },
            created_at=now,
        )

        await handler.handle(event)

        # Verify judgment cache was created
        assert judgment_cache_repository.save.called
        cache = judgment_cache_repository.save.call_args[0][0]
        assert cache.channel_id == "C123"
        assert cache.should_respond is True

    async def test_handle_saves_bot_response_message(
        self,
        handler: MessageEventHandler,
        message_repository: AsyncMock,
        channel_repository: AsyncMock,
        bot_user_id: str,
        now: datetime,
    ) -> None:
        """Test that handler saves the bot's response message."""
        channel = Channel(id="C123", name="general")
        user = User(id="U123", name="user1")
        message = Message(
            id="1234567890.123456",
            channel=channel,
            user=user,
            text="Hello <@U_BOT>",
            timestamp=now,
        )

        channel_repository.find_by_id = AsyncMock(return_value=channel)
        message_repository.find_by_thread = AsyncMock(return_value=[message])
        message_repository.find_by_channel_since = AsyncMock(return_value=[])

        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "1234567890.123456",
                "message": message,
            },
            created_at=now,
        )

        await handler.handle(event)

        # Verify bot message was saved (called twice: once for received, once for bot)
        assert message_repository.save.call_count == 2
        # Second call should be the bot's message
        bot_message = message_repository.save.call_args_list[1][0][0]
        assert bot_message.user.id == bot_user_id
        assert bot_message.text == "Hello!"
