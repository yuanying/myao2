"""Tests for EventQueue."""

import asyncio
from datetime import datetime, timezone

import pytest

from myao2.domain.entities.event import Event, EventType
from myao2.infrastructure.events.queue import EventQueue


class TestEventQueueBasic:
    """Basic tests for EventQueue."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def message_event(self, now: datetime) -> Event:
        """Create a sample MESSAGE event."""
        return Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": "C1234567890",
                "thread_ts": "1234567890.123456",
                "is_mention": True,
            },
            created_at=now,
        )

    @pytest.fixture
    def summary_event(self, now: datetime) -> Event:
        """Create a sample SUMMARY event."""
        return Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )

    async def test_enqueue_and_dequeue(
        self, queue: EventQueue, message_event: Event
    ) -> None:
        """Test basic enqueue and dequeue."""
        await queue.enqueue(message_event)
        event = await queue.dequeue()

        assert event == message_event

    async def test_dequeue_blocks_until_event_available(
        self, queue: EventQueue, message_event: Event
    ) -> None:
        """Test that dequeue blocks until an event is available."""
        result: Event | None = None

        async def enqueue_after_delay() -> None:
            await asyncio.sleep(0.05)
            await queue.enqueue(message_event)

        async def dequeue_task() -> None:
            nonlocal result
            result = await queue.dequeue()

        task1 = asyncio.create_task(dequeue_task())
        task2 = asyncio.create_task(enqueue_after_delay())

        await asyncio.gather(task1, task2)

        assert result == message_event

    async def test_fifo_order(self, queue: EventQueue, now: datetime) -> None:
        """Test that events are dequeued in FIFO order."""
        # Use different identity keys to test FIFO order
        event1 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C1", "thread_ts": "1", "id": 1},
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C2", "thread_ts": "2", "id": 2},
            created_at=now,
        )
        event3 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C3", "thread_ts": "3", "id": 3},
            created_at=now,
        )

        await queue.enqueue(event1)
        await queue.enqueue(event2)
        await queue.enqueue(event3)

        result1 = await queue.dequeue()
        result2 = await queue.dequeue()
        result3 = await queue.dequeue()

        assert result1.payload["id"] == 1
        assert result2.payload["id"] == 2
        assert result3.payload["id"] == 3

    async def test_mark_done(self, queue: EventQueue, message_event: Event) -> None:
        """Test mark_done completes successfully."""
        await queue.enqueue(message_event)
        event = await queue.dequeue()
        queue.mark_done(event)
        # No error should be raised

    async def test_clear(self, queue: EventQueue, now: datetime) -> None:
        """Test clear cancels all pending operations."""
        event = Event(type=EventType.MESSAGE, payload={}, created_at=now)
        await queue.enqueue(event)
        queue.clear()
        # Queue should be cleared


class TestEventQueueDuplicateControl:
    """Tests for duplicate event control in EventQueue."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_duplicate_event_replaces_old_in_queue(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that enqueueing a duplicate event replaces the old one."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 1},
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 2},
            created_at=now,
        )

        await queue.enqueue(event1)
        await queue.enqueue(event2)

        # Only one event should be in the queue (the newer one)
        result = await queue.dequeue()
        assert result.payload["version"] == 2

    async def test_different_identity_events_not_replaced(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that events with different identity keys are both kept."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456"},
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C456", "thread_ts": "789.012"},
            created_at=now,
        )

        await queue.enqueue(event1)
        await queue.enqueue(event2)

        result1 = await queue.dequeue()
        result2 = await queue.dequeue()

        # Both events should be present
        assert {result1.payload["channel_id"], result2.payload["channel_id"]} == {
            "C123",
            "C456",
        }

    async def test_summary_events_are_deduplicated(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that duplicate SUMMARY events are deduplicated."""
        event1 = Event(
            type=EventType.SUMMARY,
            payload={"version": 1},
            created_at=now,
        )
        event2 = Event(
            type=EventType.SUMMARY,
            payload={"version": 2},
            created_at=now,
        )

        await queue.enqueue(event1)
        await queue.enqueue(event2)

        result = await queue.dequeue()
        assert result.payload["version"] == 2


class TestEventQueueDelayedEnqueue:
    """Tests for delayed enqueue in EventQueue."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_enqueue_with_delay(self, queue: EventQueue, now: datetime) -> None:
        """Test that delayed enqueue works."""
        event = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123"},
            created_at=now,
        )

        start = asyncio.get_event_loop().time()
        await queue.enqueue(event, delay=0.1)

        # Event should not be immediately available
        # Wait for the event to be enqueued
        result = await asyncio.wait_for(queue.dequeue(), timeout=1.0)
        elapsed = asyncio.get_event_loop().time() - start

        assert result.payload["channel_id"] == "C123"
        assert elapsed >= 0.1

    async def test_delayed_enqueue_cancelled_by_new_event(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that delayed enqueue is cancelled when new event arrives."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 1},
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 2},
            created_at=now,
        )

        # Enqueue first event with delay
        await queue.enqueue(event1, delay=1.0)

        # Enqueue second event immediately (should cancel the delayed one)
        await queue.enqueue(event2)

        # The second event should be available immediately
        result = await asyncio.wait_for(queue.dequeue(), timeout=0.1)
        assert result.payload["version"] == 2

    async def test_clear_cancels_delayed_enqueue(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that clear cancels delayed enqueue tasks."""
        event = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123"},
            created_at=now,
        )

        await queue.enqueue(event, delay=1.0)
        queue.clear()

        # The delayed event should not be enqueued
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.dequeue(), timeout=0.2)


class TestEventQueueProcessingState:
    """Tests for processing state tracking in EventQueue."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_event_during_processing_is_queued(
        self, queue: EventQueue, now: datetime
    ) -> None:
        """Test that a new event with same key during processing is queued."""
        event1 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 1},
            created_at=now,
        )
        event2 = Event(
            type=EventType.MESSAGE,
            payload={"channel_id": "C123", "thread_ts": "123.456", "version": 2},
            created_at=now,
        )

        await queue.enqueue(event1)

        # Dequeue but don't mark_done (simulating processing)
        processing_event = await queue.dequeue()
        assert processing_event.payload["version"] == 1

        # Mark as processing (moves from pending to processing)
        queue.mark_processing(processing_event)

        # Enqueue new event with same identity key
        # This should go into pending since the old one is in processing
        await queue.enqueue(event2)

        # Mark first event as done (removes from processing)
        queue.mark_done(processing_event)

        # Second event should now be available
        result = await asyncio.wait_for(queue.dequeue(), timeout=1.0)
        assert result.payload["version"] == 2
