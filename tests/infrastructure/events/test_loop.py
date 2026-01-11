"""Tests for EventLoop."""

import asyncio
from datetime import datetime, timezone

import pytest

from myao2.domain.entities.event import Event, EventType
from myao2.infrastructure.events.dispatcher import EventDispatcher
from myao2.infrastructure.events.loop import EventLoop
from myao2.infrastructure.events.queue import EventQueue


class TestEventLoop:
    """Tests for EventLoop."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def dispatcher(self) -> EventDispatcher:
        """Create an EventDispatcher instance."""
        return EventDispatcher()

    @pytest.fixture
    def loop(self, queue: EventQueue, dispatcher: EventDispatcher) -> EventLoop:
        """Create an EventLoop instance."""
        return EventLoop(queue, dispatcher)

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_is_running_initially_false(self, loop: EventLoop) -> None:
        """Test that is_running is False initially."""
        assert not loop.is_running

    async def test_start_sets_is_running(
        self, loop: EventLoop, queue: EventQueue, now: datetime
    ) -> None:
        """Test that start sets is_running to True."""
        # Start the loop in the background
        task = asyncio.create_task(loop.start())

        # Give it time to start
        await asyncio.sleep(0.05)
        assert loop.is_running

        # Stop the loop
        await loop.stop()
        await task

    async def test_stop_sets_is_running_false(
        self, loop: EventLoop, queue: EventQueue
    ) -> None:
        """Test that stop sets is_running to False."""
        task = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        await loop.stop()
        await task

        assert not loop.is_running

    async def test_processes_events(
        self,
        loop: EventLoop,
        queue: EventQueue,
        dispatcher: EventDispatcher,
        now: datetime,
    ) -> None:
        """Test that events are processed."""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        dispatcher.register(EventType.MESSAGE, handler)

        # Start the loop
        task = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        # Enqueue an event
        event = Event(
            type=EventType.MESSAGE,
            payload={"test": "data"},
            created_at=now,
        )
        await queue.enqueue(event)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Stop the loop
        await loop.stop()
        await task

        assert len(received_events) == 1
        assert received_events[0] == event

    async def test_processes_multiple_events_sequentially(
        self,
        loop: EventLoop,
        queue: EventQueue,
        dispatcher: EventDispatcher,
        now: datetime,
    ) -> None:
        """Test that multiple events are processed sequentially."""
        processing_order: list[int] = []

        async def handler(event: Event) -> None:
            processing_order.append(event.payload["id"])
            await asyncio.sleep(0.05)  # Simulate work

        dispatcher.register(EventType.MESSAGE, handler)

        task = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        # Enqueue events with different identity keys
        for i in range(3):
            event = Event(
                type=EventType.MESSAGE,
                payload={"channel_id": f"C{i}", "id": i},
                created_at=now,
            )
            await queue.enqueue(event)

        # Wait for all events to be processed
        await asyncio.sleep(0.5)

        await loop.stop()
        await task

        assert processing_order == [0, 1, 2]

    async def test_handler_exception_doesnt_stop_loop(
        self,
        loop: EventLoop,
        queue: EventQueue,
        dispatcher: EventDispatcher,
        now: datetime,
    ) -> None:
        """Test that a handler exception doesn't stop the loop."""
        calls: list[int] = []

        async def handler(event: Event) -> None:
            calls.append(event.payload["id"])
            if event.payload["id"] == 1:
                raise RuntimeError("Test error")

        dispatcher.register(EventType.MESSAGE, handler)

        task = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        # Enqueue events
        for i in range(3):
            event = Event(
                type=EventType.MESSAGE,
                payload={"channel_id": f"C{i}", "id": i},
                created_at=now,
            )
            await queue.enqueue(event)

        await asyncio.sleep(0.3)

        await loop.stop()
        await task

        # All events should have been processed despite the error
        assert calls == [0, 1, 2]

    async def test_cannot_start_twice(
        self,
        loop: EventLoop,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that starting twice logs a warning."""
        task1 = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        # Try to start again
        task2 = asyncio.create_task(loop.start())
        await asyncio.sleep(0.05)

        await loop.stop()
        await task1
        await task2

        assert "already running" in caplog.text
