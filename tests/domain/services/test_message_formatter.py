"""Tests for message_formatter module."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities.channel import Channel
from myao2.domain.entities.message import Message
from myao2.domain.entities.user import User
from myao2.domain.services.message_formatter import (
    format_conversation_history,
    format_message_with_metadata,
    format_other_channels,
)


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(id="U001", name="testuser", is_bot=False)


@pytest.fixture
def sample_bot_user() -> User:
    """Create a sample bot user for testing."""
    return User(id="U002", name="myao", is_bot=True)


@pytest.fixture
def sample_channel() -> Channel:
    """Create a sample channel for testing."""
    return Channel(id="C001", name="general")


@pytest.fixture
def sample_message(sample_user: User, sample_channel: Channel) -> Message:
    """Create a sample message for testing."""
    return Message(
        id="msg001",
        channel=sample_channel,
        user=sample_user,
        text="こんにちは",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestFormatMessageWithMetadata:
    """Tests for format_message_with_metadata function."""

    def test_formats_message_with_timestamp_and_username(
        self, sample_message: Message
    ) -> None:
        """Test that message is formatted with timestamp and username."""
        result = format_message_with_metadata(sample_message)

        assert result == "[2024-01-01 12:00:00] testuser: こんにちは"

    def test_formats_bot_message(
        self, sample_bot_user: User, sample_channel: Channel
    ) -> None:
        """Test that bot message is formatted correctly."""
        message = Message(
            id="msg002",
            channel=sample_channel,
            user=sample_bot_user,
            text="やあ！",
            timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
        )

        result = format_message_with_metadata(message)

        assert result == "[2024-01-01 12:01:00] myao: やあ！"

    def test_formats_multiline_message(
        self, sample_user: User, sample_channel: Channel
    ) -> None:
        """Test that multiline message is formatted correctly."""
        message = Message(
            id="msg003",
            channel=sample_channel,
            user=sample_user,
            text="行1\n行2\n行3",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        result = format_message_with_metadata(message)

        assert result == "[2024-01-01 12:00:00] testuser: 行1\n行2\n行3"


class TestFormatConversationHistory:
    """Tests for format_conversation_history function."""

    def test_returns_no_history_message_for_empty_list(self) -> None:
        """Test that empty list returns 'no history' message."""
        result = format_conversation_history([])

        assert result == "(会話履歴なし)"

    def test_formats_single_message(self, sample_message: Message) -> None:
        """Test formatting of single message."""
        result = format_conversation_history([sample_message])

        assert result == "[2024-01-01 12:00:00] testuser: こんにちは"

    def test_formats_multiple_messages(
        self,
        sample_user: User,
        sample_bot_user: User,
        sample_channel: Channel,
    ) -> None:
        """Test formatting of multiple messages."""
        messages = [
            Message(
                id="msg001",
                channel=sample_channel,
                user=sample_user,
                text="こんにちは",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Message(
                id="msg002",
                channel=sample_channel,
                user=sample_bot_user,
                text="やあ！",
                timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
            ),
            Message(
                id="msg003",
                channel=sample_channel,
                user=sample_user,
                text="元気？",
                timestamp=datetime(2024, 1, 1, 12, 2, 0, tzinfo=timezone.utc),
            ),
        ]

        result = format_conversation_history(messages)

        expected = (
            "[2024-01-01 12:00:00] testuser: こんにちは\n"
            "[2024-01-01 12:01:00] myao: やあ！\n"
            "[2024-01-01 12:02:00] testuser: 元気？"
        )
        assert result == expected


class TestFormatOtherChannels:
    """Tests for format_other_channels function."""

    def test_returns_none_for_empty_dict(self) -> None:
        """Test that empty dict returns None."""
        result = format_other_channels({})

        assert result is None

    def test_returns_none_for_dict_with_empty_lists(self) -> None:
        """Test that dict with only empty lists returns None."""
        result = format_other_channels({"random": [], "dev": []})

        assert result is None

    def test_formats_single_channel(
        self, sample_user: User, sample_channel: Channel
    ) -> None:
        """Test formatting of single channel."""
        messages = [
            Message(
                id="msg001",
                channel=sample_channel,
                user=sample_user,
                text="今日は暑いね",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        result = format_other_channels({"random": messages})

        expected = "### #random\n- [2024-01-01 12:00:00] testuser: 今日は暑いね\n"
        assert result == expected

    def test_formats_multiple_channels(
        self, sample_user: User, sample_bot_user: User, sample_channel: Channel
    ) -> None:
        """Test formatting of multiple channels."""
        random_channel = Channel(id="C002", name="random")
        dev_channel = Channel(id="C003", name="dev")

        random_messages = [
            Message(
                id="msg001",
                channel=random_channel,
                user=sample_user,
                text="今日は暑いね",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Message(
                id="msg002",
                channel=random_channel,
                user=sample_bot_user,
                text="エアコンつけたよ",
                timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
            ),
        ]
        dev_messages = [
            Message(
                id="msg003",
                channel=dev_channel,
                user=sample_user,
                text="PRレビューお願いします",
                timestamp=datetime(2024, 1, 1, 11, 50, 0, tzinfo=timezone.utc),
            ),
        ]

        result = format_other_channels(
            {
                "random": random_messages,
                "dev": dev_messages,
            }
        )

        assert result is not None
        assert "### #random" in result
        assert "### #dev" in result
        assert "[2024-01-01 12:00:00] testuser: 今日は暑いね" in result
        assert "[2024-01-01 12:01:00] myao: エアコンつけたよ" in result
        assert "[2024-01-01 11:50:00] testuser: PRレビューお願いします" in result

    def test_skips_channels_with_empty_messages(
        self, sample_user: User, sample_channel: Channel
    ) -> None:
        """Test that channels with empty message lists are skipped."""
        messages = [
            Message(
                id="msg001",
                channel=sample_channel,
                user=sample_user,
                text="Hello",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        result = format_other_channels(
            {
                "random": messages,
                "empty": [],
            }
        )

        assert result is not None
        assert "### #random" in result
        assert "### #empty" not in result
