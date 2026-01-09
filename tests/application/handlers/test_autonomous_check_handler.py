"""Tests for AutonomousCheckEventHandler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from myao2.application.handlers.autonomous_check_handler import (
    AutonomousCheckEventHandler,
)
from myao2.domain.entities import Event, EventType


class TestAutonomousCheckEventHandler:
    """Tests for AutonomousCheckEventHandler."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed timestamp."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def autonomous_response_use_case(self) -> AsyncMock:
        """Create mock AutonomousResponseUseCase."""
        return AsyncMock()

    @pytest.fixture
    def handler(
        self,
        autonomous_response_use_case: AsyncMock,
    ) -> AutonomousCheckEventHandler:
        """Create handler instance."""
        return AutonomousCheckEventHandler(
            autonomous_response_use_case=autonomous_response_use_case,
        )

    def test_has_event_handler_decorator(
        self, handler: AutonomousCheckEventHandler
    ) -> None:
        """Test that handle method has event_handler decorator."""
        assert hasattr(handler.handle, "_event_type")
        assert handler.handle._event_type == EventType.AUTONOMOUS_CHECK

    async def test_handle_calls_autonomous_response_use_case(
        self,
        handler: AutonomousCheckEventHandler,
        autonomous_response_use_case: AsyncMock,
        now: datetime,
    ) -> None:
        """Test that handler calls AutonomousResponseUseCase."""
        event = Event(
            type=EventType.AUTONOMOUS_CHECK,
            payload={},
            created_at=now,
        )

        await handler.handle(event)

        autonomous_response_use_case.execute.assert_called_once()

    async def test_handle_logs_error_on_exception(
        self,
        handler: AutonomousCheckEventHandler,
        autonomous_response_use_case: AsyncMock,
        now: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that handler logs errors but doesn't raise."""
        autonomous_response_use_case.execute = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        event = Event(
            type=EventType.AUTONOMOUS_CHECK,
            payload={},
            created_at=now,
        )

        # Should not raise
        await handler.handle(event)

        assert "Error in autonomous check" in caplog.text
