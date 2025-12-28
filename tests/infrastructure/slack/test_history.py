"""Tests for SlackConversationHistoryService."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from myao2.domain.entities import Message
from myao2.infrastructure.slack import SlackConversationHistoryService


def create_slack_message(
    ts: str = "1234567890.123456",
    user: str = "U123456",
    text: str = "Hello",
    thread_ts: str | None = None,
    subtype: str | None = None,
) -> dict:
    """Create a Slack API format message."""
    msg: dict = {
        "type": "message",
        "ts": ts,
        "user": user,
        "text": text,
    }
    if thread_ts:
        msg["thread_ts"] = thread_ts
    if subtype:
        msg["subtype"] = subtype
    return msg


class TestSlackConversationHistoryService:
    """SlackConversationHistoryService tests."""

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
    def service(self, mock_client: MagicMock) -> SlackConversationHistoryService:
        """Create service instance."""
        return SlackConversationHistoryService(client=mock_client)


class TestFetchThreadHistory(TestSlackConversationHistoryService):
    """Tests for fetch_thread_history."""

    def test_fetch_thread_history_basic(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test basic thread history retrieval."""
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000001", text="First"),
                create_slack_message(ts="1234567890.000002", text="Second"),
                create_slack_message(ts="1234567890.000003", text="Third"),
            ],
        }

        messages = service.fetch_thread_history(
            channel_id="C123456",
            thread_ts="1234567890.000001",
        )

        assert len(messages) == 3
        assert all(isinstance(m, Message) for m in messages)
        # Should be in chronological order (oldest first)
        assert messages[0].text == "First"
        assert messages[1].text == "Second"
        assert messages[2].text == "Third"

        mock_client.conversations_replies.assert_called_once_with(
            channel="C123456",
            ts="1234567890.000001",
            limit=20,
        )

    def test_fetch_thread_history_empty(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test empty thread history."""
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [],
        }

        messages = service.fetch_thread_history(
            channel_id="C123456",
            thread_ts="1234567890.000001",
        )

        assert messages == []

    def test_fetch_thread_history_with_limit(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test thread history with custom limit."""
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000001", text="First"),
                create_slack_message(ts="1234567890.000002", text="Second"),
            ],
        }

        service.fetch_thread_history(
            channel_id="C123456",
            thread_ts="1234567890.000001",
            limit=5,
        )

        mock_client.conversations_replies.assert_called_once_with(
            channel="C123456",
            ts="1234567890.000001",
            limit=5,
        )

    def test_fetch_thread_history_excludes_subtypes(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test that subtypes are excluded."""
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000001", text="Normal"),
                create_slack_message(
                    ts="1234567890.000002", text="Bot", subtype="bot_message"
                ),
                create_slack_message(
                    ts="1234567890.000003", text="Changed", subtype="message_changed"
                ),
                create_slack_message(
                    ts="1234567890.000004", text="Deleted", subtype="message_deleted"
                ),
                create_slack_message(
                    ts="1234567890.000005", text="Join", subtype="channel_join"
                ),
                create_slack_message(
                    ts="1234567890.000006", text="Leave", subtype="channel_leave"
                ),
                create_slack_message(ts="1234567890.000007", text="Normal2"),
            ],
        }

        messages = service.fetch_thread_history(
            channel_id="C123456",
            thread_ts="1234567890.000001",
        )

        assert len(messages) == 2
        assert messages[0].text == "Normal"
        assert messages[1].text == "Normal2"

    def test_fetch_thread_history_api_error(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test that API errors are propagated."""
        mock_client.conversations_replies.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        with pytest.raises(SlackApiError):
            service.fetch_thread_history(
                channel_id="C123456",
                thread_ts="1234567890.000001",
            )


class TestFetchChannelHistory(TestSlackConversationHistoryService):
    """Tests for fetch_channel_history."""

    def test_fetch_channel_history_basic(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test basic channel history retrieval."""
        # API returns newest first
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000003", text="Third"),
                create_slack_message(ts="1234567890.000002", text="Second"),
                create_slack_message(ts="1234567890.000001", text="First"),
            ],
        }

        messages = service.fetch_channel_history(channel_id="C123456")

        assert len(messages) == 3
        assert all(isinstance(m, Message) for m in messages)
        # Should be reversed to chronological order (oldest first)
        assert messages[0].text == "First"
        assert messages[1].text == "Second"
        assert messages[2].text == "Third"

        mock_client.conversations_history.assert_called_once_with(
            channel="C123456",
            limit=20,
        )

    def test_fetch_channel_history_empty(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test empty channel history."""
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [],
        }

        messages = service.fetch_channel_history(channel_id="C123456")

        assert messages == []

    def test_fetch_channel_history_with_limit(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test channel history with custom limit."""
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000001", text="First"),
            ],
        }

        service.fetch_channel_history(channel_id="C123456", limit=10)

        mock_client.conversations_history.assert_called_once_with(
            channel="C123456",
            limit=10,
        )

    def test_fetch_channel_history_excludes_subtypes(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test that subtypes are excluded."""
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000007", text="Normal2"),
                create_slack_message(
                    ts="1234567890.000006", text="Leave", subtype="channel_leave"
                ),
                create_slack_message(
                    ts="1234567890.000005", text="Join", subtype="channel_join"
                ),
                create_slack_message(
                    ts="1234567890.000004", text="Deleted", subtype="message_deleted"
                ),
                create_slack_message(
                    ts="1234567890.000003", text="Changed", subtype="message_changed"
                ),
                create_slack_message(
                    ts="1234567890.000002", text="Bot", subtype="bot_message"
                ),
                create_slack_message(ts="1234567890.000001", text="Normal"),
            ],
        }

        messages = service.fetch_channel_history(channel_id="C123456")

        assert len(messages) == 2
        # Reversed to chronological order
        assert messages[0].text == "Normal"
        assert messages[1].text == "Normal2"

    def test_fetch_channel_history_api_error(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test that API errors are propagated."""
        mock_client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        with pytest.raises(SlackApiError):
            service.fetch_channel_history(channel_id="C123456")


class TestToMessage(TestSlackConversationHistoryService):
    """Tests for _to_message."""

    def test_to_message_basic(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test basic message conversion."""
        msg = create_slack_message(
            ts="1234567890.123456",
            user="U123456",
            text="Hello world",
        )

        message = service._to_message(msg, channel_id="C123456")

        assert isinstance(message, Message)
        assert message.id == "1234567890.123456"
        assert message.channel.id == "C123456"
        assert message.channel.name == ""
        assert message.user.id == "U123456"
        assert message.user.name == "testuser"
        assert message.user.is_bot is False
        assert message.text == "Hello world"
        assert message.thread_ts is None
        assert message.mentions == []

        # Verify timestamp conversion
        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc

    def test_to_message_with_thread_ts(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test message conversion with thread_ts."""
        msg = create_slack_message(
            ts="1234567890.123456",
            user="U123456",
            text="Reply",
            thread_ts="1234567890.000001",
        )

        message = service._to_message(msg, channel_id="C123456")

        assert message.thread_ts == "1234567890.000001"
        assert message.is_in_thread() is True

    def test_to_message_with_mentions(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test message conversion with mentions."""
        msg = create_slack_message(
            ts="1234567890.123456",
            user="U123456",
            text="Hello <@UBOT123>!",
        )

        message = service._to_message(msg, channel_id="C123456")

        assert message.mentions == ["UBOT123"]

    def test_to_message_with_multiple_mentions(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test message conversion with multiple mentions."""
        msg = create_slack_message(
            ts="1234567890.123456",
            user="U123456",
            text="<@U111> and <@U222|username> are here",
        )

        message = service._to_message(msg, channel_id="C123456")

        assert message.mentions == ["U111", "U222"]

    def test_to_message_with_no_user(
        self, service: SlackConversationHistoryService, mock_client: MagicMock
    ) -> None:
        """Test message conversion when user is not provided."""
        msg = {
            "type": "message",
            "ts": "1234567890.123456",
            "text": "System message",
        }

        message = service._to_message(msg, channel_id="C123456")

        assert message.user.id == ""
        assert message.user.name == "Unknown"
        assert message.user.is_bot is True

        # Should not call users_info when no user
        mock_client.users_info.assert_not_called()
