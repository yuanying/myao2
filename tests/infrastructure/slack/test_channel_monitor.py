"""Tests for SlackChannelMonitor."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from myao2.domain.entities import Channel, Message
from myao2.infrastructure.slack import SlackChannelMonitor


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


def create_slack_channel(
    id: str = "C123456",
    name: str = "general",
) -> dict:
    """Create a Slack API format channel."""
    return {
        "id": id,
        "name": name,
    }


class TestSlackChannelMonitor:
    """SlackChannelMonitor tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.users_info = AsyncMock(
            return_value={
                "user": {
                    "id": "U123456",
                    "name": "testuser",
                    "is_bot": False,
                }
            }
        )
        client.users_conversations = AsyncMock()
        client.conversations_history = AsyncMock()
        client.conversations_replies = AsyncMock()
        return client

    @pytest.fixture
    def monitor(self, mock_client: MagicMock) -> SlackChannelMonitor:
        """Create monitor instance."""
        return SlackChannelMonitor(client=mock_client, bot_user_id="UBOT123")


class TestGetChannels(TestSlackChannelMonitor):
    """Tests for get_channels."""

    async def test_get_channels_with_channels(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test get_channels with channels present."""
        mock_client.users_conversations.return_value = {
            "ok": True,
            "channels": [
                create_slack_channel(id="C001", name="general"),
                create_slack_channel(id="C002", name="random"),
            ],
        }

        channels = await monitor.get_channels()

        assert len(channels) == 2
        assert all(isinstance(c, Channel) for c in channels)
        assert channels[0].id == "C001"
        assert channels[0].name == "general"
        assert channels[1].id == "C002"
        assert channels[1].name == "random"

        mock_client.users_conversations.assert_awaited_once_with(
            types="public_channel,private_channel",
        )

    async def test_get_channels_empty(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test get_channels with no channels."""
        mock_client.users_conversations.return_value = {
            "ok": True,
            "channels": [],
        }

        channels = await monitor.get_channels()

        assert channels == []

    async def test_get_channels_api_error_returns_empty(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that API errors return empty list."""
        mock_client.users_conversations.side_effect = SlackApiError(
            message="invalid_auth",
            response={"error": "invalid_auth"},
        )

        channels = await monitor.get_channels()

        assert channels == []


class TestGetRecentMessages(TestSlackChannelMonitor):
    """Tests for get_recent_messages."""

    async def test_get_recent_messages_basic(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test basic message retrieval."""
        # API returns newest first
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000003", text="Third"),
                create_slack_message(ts="1234567890.000002", text="Second"),
                create_slack_message(ts="1234567890.000001", text="First"),
            ],
        }

        messages = await monitor.get_recent_messages(channel_id="C123456")

        assert len(messages) == 3
        assert all(isinstance(m, Message) for m in messages)
        # Should be in newest first order
        assert messages[0].text == "Third"
        assert messages[1].text == "Second"
        assert messages[2].text == "First"

        mock_client.conversations_history.assert_awaited_once_with(
            channel="C123456",
            limit=20,
        )

    async def test_get_recent_messages_with_limit(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test message retrieval with custom limit."""
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000001", text="First"),
            ],
        }

        await monitor.get_recent_messages(channel_id="C123456", limit=10)

        mock_client.conversations_history.assert_awaited_once_with(
            channel="C123456",
            limit=10,
        )

    async def test_get_recent_messages_with_since(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test message retrieval with since filter."""
        since = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # API returns newest first, messages older than since should be filtered
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                # timestamp 1705320000 = 2024-01-15 12:00:00 UTC
                create_slack_message(ts="1705320060.000002", text="After since"),
                create_slack_message(ts="1705319940.000001", text="Before since"),
            ],
        }

        messages = await monitor.get_recent_messages(channel_id="C123456", since=since)

        # Only "After since" should be returned
        assert len(messages) == 1
        assert messages[0].text == "After since"

    async def test_get_recent_messages_api_error_returns_empty(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that API errors return empty list."""
        mock_client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        messages = await monitor.get_recent_messages(channel_id="C123456")

        assert messages == []

    async def test_get_recent_messages_excludes_subtypes(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that system messages are excluded."""
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts="1234567890.000003", text="Normal"),
                create_slack_message(
                    ts="1234567890.000002", text="Join", subtype="channel_join"
                ),
                create_slack_message(ts="1234567890.000001", text="Normal2"),
            ],
        }

        messages = await monitor.get_recent_messages(channel_id="C123456")

        assert len(messages) == 2
        assert messages[0].text == "Normal"
        assert messages[1].text == "Normal2"


class TestGetUnrepliedThreads(TestSlackChannelMonitor):
    """Tests for get_unreplied_threads."""

    async def test_unreplied_thread_after_wait_time(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that threads past wait time and not replied are returned."""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(seconds=400)).timestamp()

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts=f"{old_ts}", user="U111", text="Hello?"),
            ],
        }
        mock_client.users_info.return_value = {
            "user": {"id": "U111", "name": "user1", "is_bot": False}
        }

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        # Returns None for top-level unreplied
        assert len(threads) == 1
        assert threads[0] is None

    async def test_message_within_wait_time_not_returned(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that messages within wait time are not returned."""
        now = datetime.now(timezone.utc)
        recent_ts = (now - timedelta(seconds=100)).timestamp()

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts=f"{recent_ts}", user="U111", text="Hello?"),
            ],
        }
        mock_client.users_info.return_value = {
            "user": {"id": "U111", "name": "user1", "is_bot": False}
        }

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        assert len(threads) == 0

    async def test_bot_own_message_not_returned(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that bot's own messages are not returned."""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(seconds=400)).timestamp()

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(
                    ts=f"{old_ts}", user="UBOT123", text="Bot message"
                ),
            ],
        }
        mock_client.users_info.return_value = {
            "user": {"id": "UBOT123", "name": "myao", "is_bot": True}
        }

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        assert len(threads) == 0

    async def test_message_with_bot_reply_not_returned(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that messages already replied by bot are not returned."""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(seconds=400)).timestamp()
        reply_ts = (now - timedelta(seconds=200)).timestamp()

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(ts=f"{reply_ts}", user="UBOT123", text="Reply!"),
                create_slack_message(ts=f"{old_ts}", user="U111", text="Hello?"),
            ],
        }

        def user_info_side_effect(**kwargs):
            user_id = kwargs.get("user")
            if user_id == "UBOT123":
                return {"user": {"id": "UBOT123", "name": "myao", "is_bot": True}}
            return {"user": {"id": user_id, "name": "user", "is_bot": False}}

        mock_client.users_info.side_effect = user_info_side_effect

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        # Bot already replied after the user's message
        assert len(threads) == 0

    async def test_thread_message_with_bot_reply_not_returned(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that thread messages with bot reply are not returned."""
        now = datetime.now(timezone.utc)
        parent_ts = (now - timedelta(seconds=400)).timestamp()
        parent_ts_str = f"{parent_ts}"

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(
                    ts=parent_ts_str,
                    user="U111",
                    text="Hello?",
                    thread_ts=parent_ts_str,
                ),
            ],
        }

        # Bot replied in the thread
        reply_ts = (now - timedelta(seconds=200)).timestamp()
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                create_slack_message(
                    ts=parent_ts_str,
                    user="U111",
                    text="Hello?",
                    thread_ts=parent_ts_str,
                ),
                create_slack_message(
                    ts=f"{reply_ts}",
                    user="UBOT123",
                    text="Reply!",
                    thread_ts=parent_ts_str,
                ),
            ],
        }

        def user_info_side_effect(**kwargs):
            user_id = kwargs.get("user")
            if user_id == "UBOT123":
                return {"user": {"id": "UBOT123", "name": "myao", "is_bot": True}}
            return {"user": {"id": user_id, "name": "user", "is_bot": False}}

        mock_client.users_info.side_effect = user_info_side_effect

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        assert len(threads) == 0

    async def test_api_error_returns_empty(
        self, monitor: SlackChannelMonitor, mock_client: MagicMock
    ) -> None:
        """Test that API errors return empty list."""
        mock_client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        threads = await monitor.get_unreplied_threads(
            channel_id="C123456", min_wait_seconds=300
        )

        assert threads == []
