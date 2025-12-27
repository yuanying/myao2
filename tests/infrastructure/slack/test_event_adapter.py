"""Tests for SlackEventAdapter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from myao2.domain.entities import Message
from myao2.infrastructure.slack import SlackEventAdapter


class TestSlackEventAdapter:
    """SlackEventAdapter tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack WebClient."""
        client = MagicMock()
        client.users_info.return_value = {
            "user": {
                "id": "U123456",
                "name": "testuser",
                "is_bot": False,
            }
        }
        return client

    @pytest.fixture
    def adapter(self, mock_client: MagicMock) -> SlackEventAdapter:
        """Create adapter instance."""
        return SlackEventAdapter(client=mock_client)

    def test_to_message_basic(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test basic event to message conversion."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = adapter.to_message(event)

        assert isinstance(message, Message)
        assert message.id == "1234567890.123456"
        assert message.channel.id == "C123456"
        assert message.user.id == "U123456"
        assert message.user.name == "testuser"
        assert message.text == "<@UBOT123> hello"
        assert message.thread_ts is None
        assert "UBOT123" in message.mentions

    def test_to_message_in_thread(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test event to message conversion for thread message."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> help me",
            "ts": "1234567890.123456",
            "channel": "C123456",
            "thread_ts": "1234567890.000000",
        }

        message = adapter.to_message(event)

        assert message.thread_ts == "1234567890.000000"
        assert message.is_in_thread() is True

    def test_to_message_bot_user(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test event to message conversion for bot user."""
        mock_client.users_info.return_value = {
            "user": {
                "id": "UBOT456",
                "name": "bot",
                "is_bot": True,
            }
        }
        event = {
            "type": "app_mention",
            "user": "UBOT456",
            "text": "<@UBOT123> test",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = adapter.to_message(event)

        assert message.user.is_bot is True

    def test_to_message_timestamp_conversion(self, adapter: SlackEventAdapter) -> None:
        """Test that timestamp is properly converted."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = adapter.to_message(event)

        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc

    def test_extract_mentions_single(self, adapter: SlackEventAdapter) -> None:
        """Test extracting single mention."""
        text = "<@U123456> hello"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123456"]

    def test_extract_mentions_multiple(self, adapter: SlackEventAdapter) -> None:
        """Test extracting multiple mentions."""
        text = "<@U123> and <@U456> are here"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123", "U456"]

    def test_extract_mentions_none(self, adapter: SlackEventAdapter) -> None:
        """Test extracting when no mentions."""
        text = "hello everyone"

        mentions = adapter.extract_mentions(text)

        assert mentions == []

    def test_extract_mentions_with_display_name(
        self, adapter: SlackEventAdapter
    ) -> None:
        """Test extracting mentions with display name format."""
        text = "<@U123|username> hello"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123"]
