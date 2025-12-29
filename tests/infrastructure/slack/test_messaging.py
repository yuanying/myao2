"""Tests for SlackMessagingService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from myao2.domain.exceptions import ChannelNotAccessibleError
from myao2.infrastructure.slack import SlackMessagingService


class TestSlackMessagingService:
    """SlackMessagingService tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.chat_postMessage = AsyncMock()
        client.auth_test = AsyncMock(return_value={"user_id": "UBOT123"})
        return client

    @pytest.fixture
    def service(self, mock_client: MagicMock) -> SlackMessagingService:
        """Create service instance."""
        return SlackMessagingService(client=mock_client)

    async def test_send_message_to_channel(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test sending message to channel."""
        await service.send_message(
            channel_id="C123456",
            text="Hello, world!",
        )

        mock_client.chat_postMessage.assert_awaited_once_with(
            channel="C123456",
            text="Hello, world!",
            thread_ts=None,
        )

    async def test_send_message_to_thread(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test sending message to thread."""
        await service.send_message(
            channel_id="C123456",
            text="Thread reply",
            thread_ts="1234567890.123456",
        )

        mock_client.chat_postMessage.assert_awaited_once_with(
            channel="C123456",
            text="Thread reply",
            thread_ts="1234567890.123456",
        )

    async def test_send_message_not_in_channel_raises_channel_not_accessible(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test that not_in_channel error is converted to ChannelNotAccessibleError."""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="not_in_channel",
            response={"error": "not_in_channel"},
        )

        with pytest.raises(ChannelNotAccessibleError) as exc_info:
            await service.send_message(
                channel_id="C123456",
                text="Hello",
            )

        assert exc_info.value.channel_id == "C123456"

    async def test_send_message_channel_not_found_raises_channel_not_accessible(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test channel_not_found converts to ChannelNotAccessibleError."""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        with pytest.raises(ChannelNotAccessibleError) as exc_info:
            await service.send_message(
                channel_id="C123456",
                text="Hello",
            )

        assert exc_info.value.channel_id == "C123456"

    async def test_send_message_is_archived_raises_channel_not_accessible(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test that is_archived error is converted to ChannelNotAccessibleError."""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="is_archived",
            response={"error": "is_archived"},
        )

        with pytest.raises(ChannelNotAccessibleError) as exc_info:
            await service.send_message(
                channel_id="C123456",
                text="Hello",
            )

        assert exc_info.value.channel_id == "C123456"

    async def test_send_message_other_api_error_propagated(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test that other API errors are propagated as SlackApiError."""
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="rate_limited",
            response={"error": "rate_limited"},
        )

        with pytest.raises(SlackApiError):
            await service.send_message(
                channel_id="C123456",
                text="Hello",
            )

    async def test_get_bot_user_id(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test getting bot user ID."""
        bot_id = await service.get_bot_user_id()

        assert bot_id == "UBOT123"
        mock_client.auth_test.assert_awaited_once()

    async def test_get_bot_user_id_cached(
        self, service: SlackMessagingService, mock_client: MagicMock
    ) -> None:
        """Test that bot user ID is cached."""
        await service.get_bot_user_id()
        await service.get_bot_user_id()

        mock_client.auth_test.assert_awaited_once()
