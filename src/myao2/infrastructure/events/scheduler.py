"""Event scheduler for periodic event firing."""

import asyncio
import logging

from myao2.domain.entities.event import Event, EventType
from myao2.infrastructure.events.queue import EventQueue

logger = logging.getLogger(__name__)


class EventScheduler:
    """Scheduler for periodic events.

    Fires events at configured intervals:
    - AUTONOMOUS_CHECK: check_interval_seconds
    - SUMMARY: summary_interval_seconds
    - CHANNEL_SYNC: channel_sync_interval_seconds
    """

    def __init__(
        self,
        queue: EventQueue,
        check_interval_seconds: float,
        summary_interval_seconds: float,
        channel_sync_interval_seconds: float,
    ) -> None:
        """Initialize the scheduler.

        Args:
            queue: The event queue to enqueue events to.
            check_interval_seconds: Interval for AUTONOMOUS_CHECK events.
            summary_interval_seconds: Interval for SUMMARY events.
            channel_sync_interval_seconds: Interval for CHANNEL_SYNC events.
        """
        self._queue = queue
        self._check_interval = check_interval_seconds
        self._summary_interval = summary_interval_seconds
        self._channel_sync_interval = channel_sync_interval_seconds
        self._stop_event = asyncio.Event()
        self._stop_event.set()  # Initially stopped

    async def start(self) -> None:
        """Start the scheduler.

        Fires initial events immediately, then at configured intervals.
        """
        if not self._stop_event.is_set():
            logger.warning("EventScheduler already running")
            return

        self._stop_event.clear()
        logger.info("EventScheduler started")

        # Fire initial events immediately
        await self._enqueue_autonomous_check()
        await self._enqueue_summary()
        await self._enqueue_channel_sync()

        # Track last fire times
        loop = asyncio.get_running_loop()
        last_check = loop.time()
        last_summary = loop.time()
        last_channel_sync = loop.time()

        # Calculate minimum interval for polling
        min_interval = min(
            self._check_interval,
            self._summary_interval,
            self._channel_sync_interval,
            1.0,  # Maximum poll interval
        )
        poll_interval = max(min_interval / 10, 0.01)  # Poll at 1/10 of min interval

        while not self._stop_event.is_set():
            try:
                # Wait for stop event or timeout
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=poll_interval,
                    )
                    # Stop event was set
                    break
                except asyncio.TimeoutError:
                    pass

                current = loop.time()

                # Check if it's time to fire each event type
                if current - last_check >= self._check_interval:
                    await self._enqueue_autonomous_check()
                    last_check = current

                if current - last_summary >= self._summary_interval:
                    await self._enqueue_summary()
                    last_summary = current

                if current - last_channel_sync >= self._channel_sync_interval:
                    await self._enqueue_channel_sync()
                    last_channel_sync = current

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in event scheduler")

        logger.info("EventScheduler stopped")

    async def _enqueue_autonomous_check(self) -> None:
        """Enqueue an AUTONOMOUS_CHECK event."""
        event = Event(type=EventType.AUTONOMOUS_CHECK, payload={})
        await self._queue.enqueue(event)
        logger.debug("Enqueued autonomous check event")

    async def _enqueue_summary(self) -> None:
        """Enqueue a SUMMARY event."""
        event = Event(type=EventType.SUMMARY, payload={})
        await self._queue.enqueue(event)
        logger.debug("Enqueued summary event")

    async def _enqueue_channel_sync(self) -> None:
        """Enqueue a CHANNEL_SYNC event."""
        event = Event(type=EventType.CHANNEL_SYNC, payload={})
        await self._queue.enqueue(event)
        logger.debug("Enqueued channel sync event")

    async def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping EventScheduler")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return not self._stop_event.is_set()
