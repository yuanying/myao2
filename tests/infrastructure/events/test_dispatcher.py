"""Tests for EventDispatcher."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities.event import Event, EventType
from myao2.infrastructure.events.dispatcher import EventDispatcher, event_handler


class TestEventHandler:
    """Tests for @event_handler decorator."""

    def test_decorator_sets_event_type(self) -> None:
        """Test that decorator sets _event_type attribute."""

        @event_handler(EventType.MESSAGE)
        async def handle_message(event: Event) -> None:
            pass

        assert handle_message._event_type == EventType.MESSAGE  # type: ignore[attr-defined]

    def test_decorator_preserves_function(self) -> None:
        """Test that decorator preserves the original function."""

        @event_handler(EventType.SUMMARY)
        async def handle_summary(event: Event) -> None:
            pass

        assert handle_summary.__name__ == "handle_summary"


class TestEventDispatcher:
    """Tests for EventDispatcher."""

    @pytest.fixture
    def dispatcher(self) -> EventDispatcher:
        """Create an EventDispatcher instance."""
        return EventDispatcher()

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    async def test_register_and_dispatch(
        self, dispatcher: EventDispatcher, now: datetime
    ) -> None:
        """Test registering a handler and dispatching an event."""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        dispatcher.register(EventType.MESSAGE, handler)

        event = Event(
            type=EventType.MESSAGE,
            payload={"test": "data"},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    async def test_register_handler_with_decorator(
        self, dispatcher: EventDispatcher, now: datetime
    ) -> None:
        """Test registering a handler using @event_handler decorator."""
        received_events: list[Event] = []

        @event_handler(EventType.SUMMARY)
        async def handle_summary(event: Event) -> None:
            received_events.append(event)

        dispatcher.register_handler(handle_summary)

        event = Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    async def test_register_handler_without_decorator_raises_error(
        self, dispatcher: EventDispatcher
    ) -> None:
        """Test that registering a non-decorated handler raises ValueError."""

        async def plain_handler(event: Event) -> None:
            pass

        with pytest.raises(ValueError) as exc_info:
            dispatcher.register_handler(plain_handler)

        assert "has no _event_type attribute" in str(exc_info.value)

    async def test_multiple_handlers_for_same_type(
        self, dispatcher: EventDispatcher, now: datetime
    ) -> None:
        """Test that multiple handlers can be registered for the same type."""
        calls: list[str] = []

        async def handler1(event: Event) -> None:
            calls.append("handler1")

        async def handler2(event: Event) -> None:
            calls.append("handler2")

        dispatcher.register(EventType.MESSAGE, handler1)
        dispatcher.register(EventType.MESSAGE, handler2)

        event = Event(
            type=EventType.MESSAGE,
            payload={},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert calls == ["handler1", "handler2"]

    async def test_dispatch_without_handler_logs_warning(
        self,
        dispatcher: EventDispatcher,
        now: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that dispatching without a handler logs a warning."""
        event = Event(
            type=EventType.MESSAGE,
            payload={},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert "No handler registered for event type" in caplog.text

    async def test_handler_exception_is_logged(
        self,
        dispatcher: EventDispatcher,
        now: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that handler exceptions are logged but don't stop processing."""

        async def failing_handler(event: Event) -> None:
            raise RuntimeError("Test error")

        dispatcher.register(EventType.MESSAGE, failing_handler)

        event = Event(
            type=EventType.MESSAGE,
            payload={},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert "Error in event handler" in caplog.text
        assert "Test error" in caplog.text

    async def test_handler_exception_doesnt_stop_other_handlers(
        self, dispatcher: EventDispatcher, now: datetime
    ) -> None:
        """Test that a failing handler doesn't prevent other handlers from running."""
        calls: list[str] = []

        async def failing_handler(event: Event) -> None:
            calls.append("failing")
            raise RuntimeError("Test error")

        async def successful_handler(event: Event) -> None:
            calls.append("successful")

        dispatcher.register(EventType.MESSAGE, failing_handler)
        dispatcher.register(EventType.MESSAGE, successful_handler)

        event = Event(
            type=EventType.MESSAGE,
            payload={},
            created_at=now,
        )
        await dispatcher.dispatch(event)

        assert calls == ["failing", "successful"]

    async def test_different_event_types_go_to_different_handlers(
        self, dispatcher: EventDispatcher, now: datetime
    ) -> None:
        """Test that different event types are routed to correct handlers."""
        message_events: list[Event] = []
        summary_events: list[Event] = []

        async def message_handler(event: Event) -> None:
            message_events.append(event)

        async def summary_handler(event: Event) -> None:
            summary_events.append(event)

        dispatcher.register(EventType.MESSAGE, message_handler)
        dispatcher.register(EventType.SUMMARY, summary_handler)

        message_event = Event(type=EventType.MESSAGE, payload={}, created_at=now)
        summary_event = Event(type=EventType.SUMMARY, payload={}, created_at=now)

        await dispatcher.dispatch(message_event)
        await dispatcher.dispatch(summary_event)

        assert len(message_events) == 1
        assert len(summary_events) == 1
        assert message_events[0] == message_event
        assert summary_events[0] == summary_event
