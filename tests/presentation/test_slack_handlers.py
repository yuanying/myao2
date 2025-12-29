"""Tests for Slack event handlers."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.presentation.slack_handlers import register_handlers


@pytest.fixture
def mock_reply_use_case() -> AsyncMock:
    """Create a mock ReplyToMentionUseCase."""
    return AsyncMock()


@pytest.fixture
def mock_event_adapter() -> AsyncMock:
    """Create a mock SlackEventAdapter."""
    return AsyncMock()


@pytest.fixture
def mock_message_repository() -> AsyncMock:
    """Create a mock MessageRepository."""
    return AsyncMock()


@pytest.fixture
def mock_channel_repository() -> AsyncMock:
    """Create a mock ChannelRepository."""
    mock = AsyncMock()
    mock.delete = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def bot_user_id() -> str:
    """Bot user ID for testing."""
    return "U_BOT_123"


@pytest.fixture
def registered_handlers(
    mock_reply_use_case: AsyncMock,
    mock_event_adapter: AsyncMock,
    mock_message_repository: AsyncMock,
    mock_channel_repository: AsyncMock,
    bot_user_id: str,
) -> dict[str, Any]:
    """Register handlers and return captured handler dict."""
    handlers: dict[str, Any] = {}
    mock_app = Mock()

    def capture_event(event_type: str):
        def decorator(func):
            handlers[event_type] = func
            return func

        return decorator

    mock_app.event = capture_event

    register_handlers(
        mock_app,
        mock_reply_use_case,
        mock_event_adapter,
        bot_user_id,
        mock_message_repository,
        mock_channel_repository,
    )

    return handlers


class TestMemberLeftChannelHandler:
    """Tests for member_left_channel handler."""

    async def test_bot_leaving_channel_removes_from_db(
        self,
        registered_handlers: dict[str, Any],
        mock_channel_repository: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """Test that bot leaving a channel removes it from DB."""
        # Verify member_left_channel handler was registered
        assert "member_left_channel" in registered_handlers

        # Call the handler with bot leaving
        handler = registered_handlers["member_left_channel"]
        event = {
            "type": "member_left_channel",
            "user": bot_user_id,
            "channel": "C123456",
        }

        await handler(event)

        mock_channel_repository.delete.assert_awaited_once_with("C123456")

    async def test_other_user_leaving_channel_does_nothing(
        self,
        registered_handlers: dict[str, Any],
        mock_channel_repository: AsyncMock,
    ) -> None:
        """Test that other users leaving doesn't affect DB."""
        handler = registered_handlers["member_left_channel"]
        event = {
            "type": "member_left_channel",
            "user": "U_OTHER_USER",  # Not the bot
            "channel": "C123456",
        }

        await handler(event)

        mock_channel_repository.delete.assert_not_awaited()

    async def test_handler_logs_error_on_delete_failure(
        self,
        mock_reply_use_case: AsyncMock,
        mock_event_adapter: AsyncMock,
        mock_message_repository: AsyncMock,
        mock_channel_repository: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """Test that errors during delete are logged but don't crash."""
        # Need to create a fresh fixture with error-raising delete
        handlers: dict[str, Any] = {}
        mock_app = Mock()

        def capture_event(event_type: str):
            def decorator(func):
                handlers[event_type] = func
                return func

            return decorator

        mock_app.event = capture_event

        # Make delete raise an exception
        mock_channel_repository.delete.side_effect = Exception("DB error")

        register_handlers(
            mock_app,
            mock_reply_use_case,
            mock_event_adapter,
            bot_user_id,
            mock_message_repository,
            mock_channel_repository,
        )

        handler = handlers["member_left_channel"]
        event = {
            "type": "member_left_channel",
            "user": bot_user_id,
            "channel": "C123456",
        }

        # Should not raise
        await handler(event)

        mock_channel_repository.delete.assert_awaited_once_with("C123456")


class TestMessageHandlerChannelFiltering:
    """Tests for message handler channel filtering."""

    async def test_message_from_unknown_channel_is_skipped(
        self,
        mock_reply_use_case: AsyncMock,
        mock_event_adapter: AsyncMock,
        mock_message_repository: AsyncMock,
        mock_channel_repository: AsyncMock,
        bot_user_id: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that messages from unknown channels are skipped with warning."""
        # Need fresh handlers with find_by_id returning None
        handlers: dict[str, Any] = {}
        mock_app = Mock()

        def capture_event(event_type: str):
            def decorator(func):
                handlers[event_type] = func
                return func

            return decorator

        mock_app.event = capture_event

        # Channel not in DB
        mock_channel_repository.find_by_id = AsyncMock(return_value=None)

        register_handlers(
            mock_app,
            mock_reply_use_case,
            mock_event_adapter,
            bot_user_id,
            mock_message_repository,
            mock_channel_repository,
        )

        handler = handlers["message"]
        event = {
            "type": "message",
            "ts": "1234567890.123456",
            "channel": "C_UNKNOWN",
            "text": f"Hello <@{bot_user_id}>",
            "user": "U_USER",
        }

        await handler(event)

        # Should not process the message
        mock_event_adapter.to_message.assert_not_awaited()
        mock_message_repository.save.assert_not_awaited()

        # Should log warning about scope
        assert "C_UNKNOWN" in caplog.text
        assert "scope" in caplog.text.lower()

    async def test_message_from_known_channel_is_processed(
        self,
        mock_reply_use_case: AsyncMock,
        mock_event_adapter: AsyncMock,
        mock_message_repository: AsyncMock,
        mock_channel_repository: AsyncMock,
        bot_user_id: str,
    ) -> None:
        """Test that messages from known channels are processed normally."""
        from datetime import datetime, timezone

        from myao2.domain.entities.message import Channel, Message, User

        # Need fresh handlers with find_by_id returning a channel
        handlers: dict[str, Any] = {}
        mock_app = Mock()

        def capture_event(event_type: str):
            def decorator(func):
                handlers[event_type] = func
                return func

            return decorator

        mock_app.event = capture_event

        # Channel exists in DB
        channel = Channel(id="C_KNOWN", name="general")
        mock_channel_repository.find_by_id = AsyncMock(return_value=channel)

        # Setup message conversion
        user = User(id="U_USER", name="testuser", is_bot=False)
        message = Message(
            id="1234567890.123456",
            channel=channel,
            user=user,
            text="Hello",
            timestamp=datetime.now(timezone.utc),
            thread_ts=None,
            mentions=[],
        )
        mock_event_adapter.to_message = AsyncMock(return_value=message)

        register_handlers(
            mock_app,
            mock_reply_use_case,
            mock_event_adapter,
            bot_user_id,
            mock_message_repository,
            mock_channel_repository,
        )

        handler = handlers["message"]
        event = {
            "type": "message",
            "ts": "1234567890.123456",
            "channel": "C_KNOWN",
            "text": "Hello",
            "user": "U_USER",
        }

        await handler(event)

        # Should process the message
        mock_channel_repository.find_by_id.assert_awaited_once_with("C_KNOWN")
        mock_event_adapter.to_message.assert_awaited_once()
        mock_message_repository.save.assert_awaited_once()

    async def test_message_deleted_skips_channel_check(
        self,
        registered_handlers: dict[str, Any],
        mock_channel_repository: AsyncMock,
        mock_message_repository: AsyncMock,
    ) -> None:
        """Test that message_deleted events skip channel membership check."""
        handler = registered_handlers["message"]
        event = {
            "type": "message",
            "subtype": "message_deleted",
            "deleted_ts": "1234567890.123456",
            "channel": "C_ANY",
        }

        await handler(event)

        # Should process delete without channel check
        mock_channel_repository.find_by_id.assert_not_awaited()
        mock_message_repository.delete.assert_awaited_once()
