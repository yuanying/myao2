"""Event loop for event-driven architecture."""

import asyncio
import logging

from myao2.infrastructure.events.dispatcher import EventDispatcher
from myao2.infrastructure.events.queue import EventQueue

logger = logging.getLogger(__name__)


class EventLoop:
    """Event processing loop.

    Continuously dequeues events and dispatches them to handlers.
    Events are processed sequentially (one at a time).
    """

    def __init__(self, queue: EventQueue, dispatcher: EventDispatcher) -> None:
        """Initialize the event loop.

        Args:
            queue: The event queue to read from.
            dispatcher: The dispatcher to send events to.
        """
        self._queue = queue
        self._dispatcher = dispatcher
        self._stop_event = asyncio.Event()
        self._stop_event.set()  # Initially stopped

    async def start(self) -> None:
        """Start the event loop.

        This method runs until stop() is called.
        """
        if not self._stop_event.is_set():
            logger.warning("EventLoop already running")
            return

        self._stop_event.clear()
        logger.info("EventLoop started")

        while not self._stop_event.is_set():
            try:
                # Use a timeout to periodically check stop_event
                try:
                    event = await asyncio.wait_for(
                        self._queue.dequeue(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                logger.debug("Processing event: %s", event.type.value)

                # Mark as processing before dispatch
                self._queue.mark_processing(event)

                # Dispatch to handlers
                await self._dispatcher.dispatch(event)

                # Mark as done after dispatch
                self._queue.mark_done(event)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in event loop")

        logger.info("EventLoop stopped")

    async def stop(self) -> None:
        """Stop the event loop."""
        logger.info("Stopping EventLoop")
        self._stop_event.set()
        self._queue.clear()

    @property
    def is_running(self) -> bool:
        """Check if the event loop is running."""
        return not self._stop_event.is_set()
