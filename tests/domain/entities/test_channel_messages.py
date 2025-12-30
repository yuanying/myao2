"""Tests for ChannelMessages and ChannelMemory entities."""

from datetime import datetime, timedelta, timezone

import pytest

from myao2.domain.entities import Channel, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages


@pytest.fixture
def sample_user() -> User:
    """Create test user."""
    return User(id="U123", name="testuser", is_bot=False)


@pytest.fixture
def sample_channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def base_timestamp() -> datetime:
    """Create base timestamp for testing."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_test_message(
    text: str,
    user: User,
    channel: Channel,
    timestamp: datetime,
    message_id: str = "msg001",
    thread_ts: str | None = None,
) -> Message:
    """Create a test message."""
    return Message(
        id=message_id,
        channel=channel,
        user=user,
        text=text,
        timestamp=timestamp,
        thread_ts=thread_ts,
        mentions=[],
    )


class TestChannelMemory:
    """Tests for ChannelMemory entity."""

    def test_creates_with_required_fields_only(self) -> None:
        """Test that ChannelMemory can be created with only required fields."""
        memory = ChannelMemory(channel_id="C123", channel_name="general")

        assert memory.channel_id == "C123"
        assert memory.channel_name == "general"
        assert memory.long_term_memory is None
        assert memory.short_term_memory is None

    def test_creates_with_all_fields(self) -> None:
        """Test that ChannelMemory can be created with all fields."""
        memory = ChannelMemory(
            channel_id="C123",
            channel_name="general",
            long_term_memory="Long term memory content",
            short_term_memory="Short term memory content",
        )

        assert memory.channel_id == "C123"
        assert memory.channel_name == "general"
        assert memory.long_term_memory == "Long term memory content"
        assert memory.short_term_memory == "Short term memory content"

    def test_memory_fields_default_to_none(self) -> None:
        """Test that memory fields default to None."""
        memory = ChannelMemory(channel_id="C123", channel_name="general")

        assert memory.long_term_memory is None
        assert memory.short_term_memory is None

    def test_is_frozen(self) -> None:
        """Test that ChannelMemory is immutable."""
        memory = ChannelMemory(channel_id="C123", channel_name="general")

        with pytest.raises(AttributeError):
            memory.channel_id = "C456"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            memory.long_term_memory = "new"  # type: ignore[misc]


class TestChannelMessagesCreation:
    """Tests for ChannelMessages creation."""

    def test_creates_empty_instance(self) -> None:
        """Test that ChannelMessages can be created with minimum fields."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        assert messages.channel_id == "C123"
        assert messages.channel_name == "general"
        assert messages.top_level_messages == []
        assert messages.thread_messages == {}

    def test_creates_with_top_level_only(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that ChannelMessages can be created with only top-level messages."""
        msg1 = create_test_message(
            text="Hello",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )
        msg2 = create_test_message(
            text="World",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=1),
            message_id="msg002",
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[msg1, msg2],
        )

        assert len(messages.top_level_messages) == 2
        assert messages.thread_messages == {}

    def test_creates_with_threads_only(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that ChannelMessages can be created with only thread messages."""
        thread_ts = "1234567890.000000"
        thread_msg1 = create_test_message(
            text="Thread message 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread_msg001",
            thread_ts=thread_ts,
        )
        thread_msg2 = create_test_message(
            text="Thread message 2",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=1),
            message_id="thread_msg002",
            thread_ts=thread_ts,
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            thread_messages={thread_ts: [thread_msg1, thread_msg2]},
        )

        assert messages.top_level_messages == []
        assert len(messages.thread_messages) == 1
        assert len(messages.thread_messages[thread_ts]) == 2

    def test_creates_with_mixed_messages(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that ChannelMessages can be created with mixed messages."""
        thread_ts = "1234567890.000000"

        top_msg = create_test_message(
            text="Top level message",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )
        thread_msg = create_test_message(
            text="Thread message",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=1),
            message_id="thread_msg001",
            thread_ts=thread_ts,
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[top_msg],
            thread_messages={thread_ts: [thread_msg]},
        )

        assert len(messages.top_level_messages) == 1
        assert len(messages.thread_messages) == 1

    def test_is_frozen(self) -> None:
        """Test that ChannelMessages is immutable."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        with pytest.raises(AttributeError):
            messages.channel_id = "C456"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            messages.top_level_messages = []  # type: ignore[misc]


class TestChannelMessagesGetAllMessages:
    """Tests for get_all_messages() method."""

    def test_returns_empty_list_when_no_messages(self) -> None:
        """Test that get_all_messages returns empty list when no messages."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        result = messages.get_all_messages()

        assert result == []

    def test_returns_top_level_messages_sorted(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that get_all_messages returns top-level messages sorted by timestamp."""
        msg1 = create_test_message(
            text="First",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=2),
            message_id="msg002",
        )
        msg2 = create_test_message(
            text="Second",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[msg1, msg2],  # Out of order
        )

        result = messages.get_all_messages()

        assert len(result) == 2
        assert result[0].text == "Second"  # Older first
        assert result[1].text == "First"  # Newer last

    def test_returns_all_messages_sorted(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that get_all_messages returns all messages sorted by timestamp."""
        thread_ts = "1234567890.000000"

        top_msg = create_test_message(
            text="Top level",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )
        thread_msg1 = create_test_message(
            text="Thread 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=1),
            message_id="thread_msg001",
            thread_ts=thread_ts,
        )
        thread_msg2 = create_test_message(
            text="Thread 2",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=2),
            message_id="thread_msg002",
            thread_ts=thread_ts,
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[top_msg],
            thread_messages={thread_ts: [thread_msg1, thread_msg2]},
        )

        result = messages.get_all_messages()

        assert len(result) == 3
        assert result[0].text == "Top level"
        assert result[1].text == "Thread 1"
        assert result[2].text == "Thread 2"

    def test_includes_thread_messages_from_multiple_threads(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that get_all_messages includes messages from multiple threads."""
        thread_ts1 = "1234567890.000000"
        thread_ts2 = "1234567891.000000"

        thread_msg1 = create_test_message(
            text="Thread 1 message",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread1_msg001",
            thread_ts=thread_ts1,
        )
        thread_msg2 = create_test_message(
            text="Thread 2 message",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp + timedelta(minutes=1),
            message_id="thread2_msg001",
            thread_ts=thread_ts2,
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            thread_messages={
                thread_ts1: [thread_msg1],
                thread_ts2: [thread_msg2],
            },
        )

        result = messages.get_all_messages()

        assert len(result) == 2
        assert result[0].text == "Thread 1 message"
        assert result[1].text == "Thread 2 message"


class TestChannelMessagesGetThread:
    """Tests for get_thread() method."""

    def test_returns_thread_messages(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test that get_thread returns messages for existing thread."""
        thread_ts = "1234567890.000000"
        thread_msg = create_test_message(
            text="Thread message",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread_msg001",
            thread_ts=thread_ts,
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            thread_messages={thread_ts: [thread_msg]},
        )

        result = messages.get_thread(thread_ts)

        assert len(result) == 1
        assert result[0].text == "Thread message"

    def test_returns_empty_list_for_nonexistent_thread(self) -> None:
        """Test that get_thread returns empty list for nonexistent thread."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        result = messages.get_thread("nonexistent_thread_ts")

        assert result == []


class TestChannelMessagesProperties:
    """Tests for ChannelMessages properties."""

    def test_thread_count_empty(self) -> None:
        """Test thread_count returns 0 when no threads."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        assert messages.thread_count == 0

    def test_thread_count_with_threads(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test thread_count returns correct count."""
        thread_msg1 = create_test_message(
            text="Thread 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread1_msg001",
            thread_ts="thread1",
        )
        thread_msg2 = create_test_message(
            text="Thread 2",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread2_msg001",
            thread_ts="thread2",
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            thread_messages={
                "thread1": [thread_msg1],
                "thread2": [thread_msg2],
            },
        )

        assert messages.thread_count == 2

    def test_total_message_count_empty(self) -> None:
        """Test total_message_count returns 0 when no messages."""
        messages = ChannelMessages(channel_id="C123", channel_name="general")

        assert messages.total_message_count == 0

    def test_total_message_count_top_level_only(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test total_message_count with only top-level messages."""
        msg1 = create_test_message(
            text="Message 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )
        msg2 = create_test_message(
            text="Message 2",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg002",
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[msg1, msg2],
        )

        assert messages.total_message_count == 2

    def test_total_message_count_mixed(
        self,
        sample_user: User,
        sample_channel: Channel,
        base_timestamp: datetime,
    ) -> None:
        """Test total_message_count with mixed messages."""
        top_msg = create_test_message(
            text="Top level",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="msg001",
        )
        thread_msg1 = create_test_message(
            text="Thread 1 msg 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread1_msg001",
            thread_ts="thread1",
        )
        thread_msg2 = create_test_message(
            text="Thread 1 msg 2",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread1_msg002",
            thread_ts="thread1",
        )
        thread_msg3 = create_test_message(
            text="Thread 2 msg 1",
            user=sample_user,
            channel=sample_channel,
            timestamp=base_timestamp,
            message_id="thread2_msg001",
            thread_ts="thread2",
        )

        messages = ChannelMessages(
            channel_id="C123",
            channel_name="general",
            top_level_messages=[top_msg],
            thread_messages={
                "thread1": [thread_msg1, thread_msg2],
                "thread2": [thread_msg3],
            },
        )

        # 1 top-level + 2 thread1 + 1 thread2 = 4
        assert messages.total_message_count == 4
