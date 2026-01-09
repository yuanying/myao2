"""Tests for EventScheduler."""

import asyncio

import pytest

from myao2.domain.entities.event import Event, EventType
from myao2.infrastructure.events.queue import EventQueue
from myao2.infrastructure.events.scheduler import EventScheduler


class TestEventScheduler:
    """Tests for EventScheduler."""

    @pytest.fixture
    def queue(self) -> EventQueue:
        """Create an EventQueue instance."""
        return EventQueue()

    @pytest.fixture
    def scheduler(self, queue: EventQueue) -> EventScheduler:
        """Create an EventScheduler with short intervals for testing."""
        return EventScheduler(
            queue=queue,
            check_interval_seconds=0.2,
            summary_interval_seconds=0.3,
            channel_sync_interval_seconds=0.4,
        )

    async def test_is_running_initially_false(self, scheduler: EventScheduler) -> None:
        """Test that is_running is False initially."""
        assert not scheduler.is_running

    async def test_start_sets_is_running(self, scheduler: EventScheduler) -> None:
        """Test that start sets is_running to True."""
        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        assert scheduler.is_running

        await scheduler.stop()
        await task

    async def test_stop_sets_is_running_false(self, scheduler: EventScheduler) -> None:
        """Test that stop sets is_running to False."""
        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        await scheduler.stop()
        await task

        assert not scheduler.is_running

    async def test_fires_initial_events(
        self, scheduler: EventScheduler, queue: EventQueue
    ) -> None:
        """Test that initial events are fired immediately on start."""
        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        await scheduler.stop()
        await task

        # Collect events from queue (they should be there)
        events: list[Event] = []
        try:
            while True:
                event = await asyncio.wait_for(queue.dequeue(), timeout=0.1)
                events.append(event)
                queue.mark_done(event)
        except asyncio.TimeoutError:
            pass

        # Should have AUTONOMOUS_CHECK, SUMMARY, and CHANNEL_SYNC
        event_types = {e.type for e in events}
        assert EventType.AUTONOMOUS_CHECK in event_types
        assert EventType.SUMMARY in event_types
        assert EventType.CHANNEL_SYNC in event_types

    async def test_fires_autonomous_check_at_interval(self, queue: EventQueue) -> None:
        """Test that AUTONOMOUS_CHECK is fired at the configured interval.

        Note: Due to duplicate event control, multiple events with the same
        identity key are deduplicated. So we count how many times the event
        was fired by consuming events as they arrive.
        """
        scheduler = EventScheduler(
            queue=queue,
            check_interval_seconds=0.1,
            summary_interval_seconds=10.0,  # Long, won't fire
            channel_sync_interval_seconds=10.0,  # Long, won't fire
        )

        check_count = 0

        async def consume_events() -> None:
            nonlocal check_count
            while True:
                try:
                    event = await asyncio.wait_for(queue.dequeue(), timeout=0.05)
                    if event.type == EventType.AUTONOMOUS_CHECK:
                        check_count += 1
                    queue.mark_done(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        task = asyncio.create_task(scheduler.start())
        consumer = asyncio.create_task(consume_events())

        # Wait for initial + 2 more intervals
        await asyncio.sleep(0.35)

        await scheduler.stop()
        await task
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass

        # Should have at least 3 (initial + 2 intervals)
        assert check_count >= 3

    async def test_fires_summary_at_interval(self, queue: EventQueue) -> None:
        """Test that SUMMARY is fired at the configured interval."""
        scheduler = EventScheduler(
            queue=queue,
            check_interval_seconds=10.0,  # Long, won't fire
            summary_interval_seconds=0.1,
            channel_sync_interval_seconds=10.0,  # Long, won't fire
        )

        summary_count = 0

        async def consume_events() -> None:
            nonlocal summary_count
            while True:
                try:
                    event = await asyncio.wait_for(queue.dequeue(), timeout=0.05)
                    if event.type == EventType.SUMMARY:
                        summary_count += 1
                    queue.mark_done(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        task = asyncio.create_task(scheduler.start())
        consumer = asyncio.create_task(consume_events())

        await asyncio.sleep(0.35)

        await scheduler.stop()
        await task
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass

        assert summary_count >= 3

    async def test_fires_channel_sync_at_interval(self, queue: EventQueue) -> None:
        """Test that CHANNEL_SYNC is fired at the configured interval."""
        scheduler = EventScheduler(
            queue=queue,
            check_interval_seconds=10.0,  # Long, won't fire
            summary_interval_seconds=10.0,  # Long, won't fire
            channel_sync_interval_seconds=0.1,
        )

        sync_count = 0

        async def consume_events() -> None:
            nonlocal sync_count
            while True:
                try:
                    event = await asyncio.wait_for(queue.dequeue(), timeout=0.05)
                    if event.type == EventType.CHANNEL_SYNC:
                        sync_count += 1
                    queue.mark_done(event)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        task = asyncio.create_task(scheduler.start())
        consumer = asyncio.create_task(consume_events())

        await asyncio.sleep(0.35)

        await scheduler.stop()
        await task
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass

        assert sync_count >= 3

    async def test_cannot_start_twice(
        self,
        scheduler: EventScheduler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that starting twice logs a warning."""
        task1 = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        task2 = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)

        await scheduler.stop()
        await task1
        await task2

        assert "already running" in caplog.text
