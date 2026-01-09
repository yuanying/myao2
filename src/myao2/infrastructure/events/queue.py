"""Event queue for event-driven architecture."""

import asyncio
import logging

from myao2.domain.entities.event import Event

logger = logging.getLogger(__name__)


class EventQueue:
    """In-memory event queue with duplicate control and delayed enqueue.

    Features:
    - Duplicate event control: When an event with the same identity key
      is enqueued, the older event is cancelled and replaced.
    - Delayed enqueue: Events can be enqueued with a delay.
    - Processing state tracking: Events being processed are tracked
      to allow new events with the same key to be queued.
    """

    def __init__(self) -> None:
        """Initialize the event queue."""
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        # Pending events waiting in queue (identity_key -> Event)
        self._pending: dict[str, Event] = {}
        # Events currently being processed (identity_key -> Event)
        self._processing: dict[str, Event] = {}
        # Delayed enqueue tasks (identity_key -> Task)
        self._delay_tasks: dict[str, asyncio.Task[None]] = {}

    async def enqueue(self, event: Event, delay: float | None = None) -> None:
        """Add an event to the queue.

        If an event with the same identity key is already pending or scheduled,
        it will be cancelled and replaced by this event.

        Args:
            event: The event to enqueue.
            delay: Optional delay in seconds before adding to queue.
        """
        identity_key = event.get_identity_key()

        # Cancel any existing delayed enqueue task for this identity key
        if identity_key in self._delay_tasks:
            task = self._delay_tasks.pop(identity_key)
            task.cancel()
            try:
                await task  # Let cancellation propagate and finish cleanup
            except asyncio.CancelledError:
                pass
            logger.debug("Cancelled delayed enqueue for %s", identity_key)

        # If there's already a pending event with same key, we'll replace it
        if identity_key in self._pending:
            logger.debug(
                "Replacing pending event: key=%s, old=%s, new=%s",
                identity_key,
                self._pending[identity_key].created_at,
                event.created_at,
            )
            # We can't remove from asyncio.Queue, but we mark it as replaced
            # by updating _pending. When dequeued, we'll check if it's current.

        if delay is not None and delay > 0:
            # Schedule delayed enqueue
            task = asyncio.create_task(self._delayed_enqueue(event, delay))
            self._delay_tasks[identity_key] = task
        else:
            # Immediate enqueue
            self._pending[identity_key] = event
            await self._queue.put(event)

    async def _delayed_enqueue(self, event: Event, delay: float) -> None:
        """Enqueue an event after a delay.

        Args:
            event: The event to enqueue.
            delay: Delay in seconds.
        """
        identity_key = event.get_identity_key()
        try:
            await asyncio.sleep(delay)
            # After delay, actually enqueue the event
            self._pending[identity_key] = event
            await self._queue.put(event)
            logger.debug("Delayed enqueue completed for %s", identity_key)
        except asyncio.CancelledError:
            logger.debug("Delayed enqueue cancelled for %s", identity_key)
            raise
        finally:
            # Clean up the task reference
            self._delay_tasks.pop(identity_key, None)

    async def dequeue(self) -> Event:
        """Get the next event from the queue.

        This method blocks until an event is available.
        If the event has been replaced while waiting, the newer event
        is returned instead.

        Returns:
            The next event to process.
        """
        while True:
            event = await self._queue.get()
            identity_key = event.get_identity_key()

            # Check if this event is still the current pending event
            current_pending = self._pending.get(identity_key)
            if current_pending is not None and current_pending is event:
                # This is the current event, return it
                return event
            elif current_pending is None:
                # Event was replaced and new one already dequeued, or cleared
                # Skip this stale event
                self._queue.task_done()
                continue
            else:
                # This event was replaced by a newer one
                # Skip the old event
                self._queue.task_done()
                continue

    def mark_processing(self, event: Event) -> None:
        """Mark an event as being processed.

        This allows new events with the same identity key to be queued
        while the current event is being processed.

        Args:
            event: The event being processed.
        """
        identity_key = event.get_identity_key()
        # Move from pending to processing
        self._pending.pop(identity_key, None)
        self._processing[identity_key] = event
        logger.debug("Event marked as processing: %s", identity_key)

    def mark_done(self, event: Event) -> None:
        """Mark an event as done processing.

        Args:
            event: The event that finished processing.
        """
        identity_key = event.get_identity_key()
        # Remove from pending only if it's the same event
        # (new events with same key should not be affected)
        pending_event = self._pending.get(identity_key)
        if pending_event is event:
            self._pending.pop(identity_key)
        # Remove from processing
        self._processing.pop(identity_key, None)
        self._queue.task_done()
        logger.debug("Event marked as done: %s", identity_key)

    def clear(self) -> None:
        """Clear all pending and delayed events.

        This cancels all delayed enqueue tasks and clears the pending map.
        """
        # Cancel all delayed enqueue tasks
        for identity_key, task in list(self._delay_tasks.items()):
            task.cancel()
        self._delay_tasks.clear()

        # Clear pending events
        self._pending.clear()

        # Clear processing events
        self._processing.clear()

        logger.info("EventQueue cleared")
