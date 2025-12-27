"""Tests for domain entities."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities import Channel, Message, User


class TestUser:
    """User entity tests."""

    def test_create_user(self) -> None:
        """Test basic user creation."""
        user = User(id="U123", name="Test User")

        assert user.id == "U123"
        assert user.name == "Test User"
        assert user.is_bot is False

    def test_create_bot_user(self) -> None:
        """Test bot user creation."""
        user = User(id="B123", name="Bot", is_bot=True)

        assert user.id == "B123"
        assert user.name == "Bot"
        assert user.is_bot is True

    def test_user_is_frozen(self) -> None:
        """Test that user is immutable."""
        user = User(id="U123", name="Test User")

        with pytest.raises(AttributeError):
            user.name = "New Name"  # type: ignore[misc]


class TestChannel:
    """Channel entity tests."""

    def test_create_channel(self) -> None:
        """Test basic channel creation."""
        channel = Channel(id="C123", name="general")

        assert channel.id == "C123"
        assert channel.name == "general"

    def test_channel_is_frozen(self) -> None:
        """Test that channel is immutable."""
        channel = Channel(id="C123", name="general")

        with pytest.raises(AttributeError):
            channel.name = "random"  # type: ignore[misc]


class TestMessage:
    """Message entity tests."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User(id="U123", name="Test User")

    @pytest.fixture
    def channel(self) -> Channel:
        """Create a test channel."""
        return Channel(id="C123", name="general")

    @pytest.fixture
    def timestamp(self) -> datetime:
        """Create a test timestamp."""
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_create_message(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test basic message creation."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello, world!",
            timestamp=timestamp,
        )

        assert message.id == "M123"
        assert message.channel == channel
        assert message.user == user
        assert message.text == "Hello, world!"
        assert message.timestamp == timestamp
        assert message.thread_ts is None
        assert message.mentions == []

    def test_create_message_with_thread(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test message creation with thread."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Reply in thread",
            timestamp=timestamp,
            thread_ts="1234567890.123456",
        )

        assert message.thread_ts == "1234567890.123456"

    def test_create_message_with_mentions(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test message creation with mentions."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello <@U456>!",
            timestamp=timestamp,
            mentions=["U456", "U789"],
        )

        assert message.mentions == ["U456", "U789"]

    def test_is_in_thread_true(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test is_in_thread returns True for thread messages."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Thread reply",
            timestamp=timestamp,
            thread_ts="1234567890.123456",
        )

        assert message.is_in_thread() is True

    def test_is_in_thread_false(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test is_in_thread returns False for channel messages."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Channel message",
            timestamp=timestamp,
        )

        assert message.is_in_thread() is False

    def test_mentions_user_true(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test mentions_user returns True when user is mentioned."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello <@U456>!",
            timestamp=timestamp,
            mentions=["U456", "U789"],
        )

        assert message.mentions_user("U456") is True

    def test_mentions_user_false(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test mentions_user returns False when user is not mentioned."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello <@U456>!",
            timestamp=timestamp,
            mentions=["U456"],
        )

        assert message.mentions_user("U999") is False

    def test_mentions_user_empty_mentions(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test mentions_user returns False with no mentions."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello!",
            timestamp=timestamp,
        )

        assert message.mentions_user("U456") is False

    def test_message_is_frozen(
        self, user: User, channel: Channel, timestamp: datetime
    ) -> None:
        """Test that message is immutable."""
        message = Message(
            id="M123",
            channel=channel,
            user=user,
            text="Hello!",
            timestamp=timestamp,
        )

        with pytest.raises(AttributeError):
            message.text = "Modified"  # type: ignore[misc]
