"""Event dispatcher for event-driven architecture."""

import logging
from collections.abc import Awaitable, Callable

from myao2.domain.entities.event import Event, EventType

logger = logging.getLogger(__name__)

# Handler type: async function that takes an Event and returns None
EventHandler = Callable[[Event], Awaitable[None]]


def event_handler(event_type: EventType) -> Callable[[EventHandler], EventHandler]:
    """Decorator for registering event handlers.

    Usage:
        @event_handler(EventType.MESSAGE)
        async def handle_message(event: Event) -> None:
            ...

    Args:
        event_type: The event type this handler processes.

    Returns:
        Decorator function.
    """

    def decorator(func: EventHandler) -> EventHandler:
        # Store the event type as an attribute on the function
        func._event_type = event_type  # type: ignore[attr-defined]
        return func

    return decorator


class EventDispatcher:
    """Dispatches events to registered handlers.

    Handlers are registered by event type and called when
    an event of that type is dispatched.
    """

    def __init__(self) -> None:
        """Initialize the dispatcher."""
        self._handlers: dict[EventType, list[EventHandler]] = {}

    def register(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The event type to handle.
            handler: The handler function.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(
            "Registered handler for %s: %s",
            event_type.value,
            getattr(handler, "__name__", str(handler)),
        )

    def register_handler(self, handler: EventHandler) -> None:
        """Register a handler that was decorated with @event_handler.

        Args:
            handler: The decorated handler function.

        Raises:
            ValueError: If the handler doesn't have an _event_type attribute.
        """
        event_type = getattr(handler, "_event_type", None)
        if event_type is None:
            raise ValueError(
                f"Handler {getattr(handler, '__name__', str(handler))} "
                "has no _event_type attribute. "
                "Use the @event_handler decorator."
            )
        self.register(event_type, handler)

    async def dispatch(self, event: Event) -> None:
        """Dispatch an event to all registered handlers.

        Args:
            event: The event to dispatch.
        """
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.warning("No handler registered for event type: %s", event.type.value)
            return

        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler %s for event %s",
                    getattr(handler, "__name__", str(handler)),
                    event.type.value,
                )
