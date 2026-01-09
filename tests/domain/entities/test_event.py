"""Tests for Event entity."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities.event import Event, EventType


class TestEventType:
    """Tests for EventType enum."""

    def test_message_value(self) -> None:
        """Test MESSAGE type value."""
        assert EventType.MESSAGE.value == "message"

    def test_summary_value(self) -> None:
        """Test SUMMARY type value."""
        assert EventType.SUMMARY.value == "summary"

    def test_autonomous_check_value(self) -> None:
        """Test AUTONOMOUS_CHECK type value."""
        assert EventType.AUTONOMOUS_CHECK.value == "autonomous_check"

    def test_channel_sync_value(self) -> None:
        """Test CHANNEL_SYNC type value."""
        assert EventType.CHANNEL_SYNC.value == "channel_sync"


class TestEvent:
    """Tests for Event entity."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_create_message_event(self, now: datetime) -> None:
        """Test creating a MESSAGE event."""
        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C1234567890",
                "thread_ts": "1234567890.123456",
                "is_mention": True,
            },
            created_at=now,
        )

        assert event.type == EventType.MESSAGE
        assert event.payload["channel_id"] == "C1234567890"
        assert event.payload["thread_ts"] == "1234567890.123456"
        assert event.payload["is_mention"] is True
        assert event.created_at == now

    def test_create_summary_event(self, now: datetime) -> None:
        """Test creating a SUMMARY event."""
        event = Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )

        assert event.type == EventType.SUMMARY
        assert event.payload == {}
        assert event.created_at == now

    def test_create_autonomous_check_event(self, now: datetime) -> None:
        """Test creating an AUTONOMOUS_CHECK event."""
        event = Event(
            type=EventType.AUTONOMOUS_CHECK,
            payload={},
            created_at=now,
        )

        assert event.type == EventType.AUTONOMOUS_CHECK
        assert event.payload == {}

    def test_create_channel_sync_event(self, now: datetime) -> None:
        """Test creating a CHANNEL_SYNC event."""
        event = Event(
            type=EventType.CHANNEL_SYNC,
            payload={},
            created_at=now,
        )

        assert event.type == EventType.CHANNEL_SYNC
        assert event.payload == {}

    def test_event_is_immutable(self, now: datetime) -> None:
        """Test that Event is frozen (immutable)."""
        event = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123"},
            created_at=now,
        )

        with pytest.raises(AttributeError):
            event.type = EventType.SUMMARY  # type: ignore[misc]

    def test_created_at_defaults_to_now(self) -> None:
        """Test that created_at defaults to current time."""
        before = datetime.now(timezone.utc)
        event = Event(
            type=EventType.MESSAGE,
            payload={},
        )
        after = datetime.now(timezone.utc)

        assert before <= event.created_at <= after


class TestEventGetIdentityKey:
    """Tests for Event.get_identity_key method."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_message_event_identity_key_with_thread(self, now: datetime) -> None:
        """Test identity key for MESSAGE event with thread_ts."""
        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C1234567890",
                "thread_ts": "1234567890.123456",
            },
            created_at=now,
        )

        assert event.get_identity_key() == "message:C1234567890:1234567890.123456"

    def test_message_event_identity_key_without_thread(self, now: datetime) -> None:
        """Test identity key for MESSAGE event without thread_ts."""
        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C1234567890",
                "thread_ts": None,
            },
            created_at=now,
        )

        assert event.get_identity_key() == "message:C1234567890:"

    def test_message_event_identity_key_missing_thread_ts(self, now: datetime) -> None:
        """Test identity key for MESSAGE event with missing thread_ts key."""
        event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C1234567890",
            },
            created_at=now,
        )

        assert event.get_identity_key() == "message:C1234567890:"

    def test_message_event_identity_key_missing_channel_id(self, now: datetime) -> None:
        """Test identity key for MESSAGE event with missing channel_id."""
        event = Event(
            type=EventType.MESSAGE,
            payload={},
            created_at=now,
        )

        assert event.get_identity_key() == "message::"

    def test_summary_event_identity_key(self, now: datetime) -> None:
        """Test identity key for SUMMARY event."""
        event = Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )

        assert event.get_identity_key() == "summary:workspace"

    def test_autonomous_check_event_identity_key(self, now: datetime) -> None:
        """Test identity key for AUTONOMOUS_CHECK event."""
        event = Event(
            type=EventType.AUTONOMOUS_CHECK,
            payload={},
            created_at=now,
        )

        assert event.get_identity_key() == "autonomous_check:workspace"

    def test_channel_sync_event_identity_key(self, now: datetime) -> None:
        """Test identity key for CHANNEL_SYNC event."""
        event = Event(
            type=EventType.CHANNEL_SYNC,
            payload={},
            created_at=now,
        )

        assert event.get_identity_key() == "channel_sync:workspace"

    def test_same_message_events_have_same_identity_key(self, now: datetime) -> None:
        """Test that two MESSAGE events for same thread have same identity key."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "123.456",
            },
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "123.456",
                "is_mention": True,  # Different payload but same identity
            },
            created_at=now,
        )

        assert event1.get_identity_key() == event2.get_identity_key()

    def test_different_channel_message_events_have_different_identity_key(
        self, now: datetime
    ) -> None:
        """Test that MESSAGE events for different channels have different keys."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "123.456",
            },
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C456",
                "thread_ts": "123.456",
            },
            created_at=now,
        )

        assert event1.get_identity_key() != event2.get_identity_key()

    def test_different_thread_message_events_have_different_identity_key(
        self, now: datetime
    ) -> None:
        """Test that MESSAGE events for different threads have different keys."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "123.456",
            },
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C123",
                "thread_ts": "789.012",
            },
            created_at=now,
        )

        assert event1.get_identity_key() != event2.get_identity_key()
