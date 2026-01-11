"""Tests for SummaryEventHandler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from myao2.application.handlers.summary_handler import SummaryEventHandler
from myao2.domain.entities import Event, EventType


class TestSummaryEventHandler:
    """Tests for SummaryEventHandler."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed timestamp."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def generate_memory_use_case(self) -> AsyncMock:
        """Create mock GenerateMemoryUseCase."""
        return AsyncMock()

    @pytest.fixture
    def handler(
        self,
        generate_memory_use_case: AsyncMock,
    ) -> SummaryEventHandler:
        """Create handler instance."""
        return SummaryEventHandler(
            generate_memory_use_case=generate_memory_use_case,
        )

    def test_has_event_handler_decorator(self, handler: SummaryEventHandler) -> None:
        """Test that handle method has event_handler decorator."""
        assert hasattr(handler.handle, "_event_type")
        assert handler.handle._event_type == EventType.SUMMARY

    async def test_handle_calls_generate_memory_use_case(
        self,
        handler: SummaryEventHandler,
        generate_memory_use_case: AsyncMock,
        now: datetime,
    ) -> None:
        """Test that handler calls GenerateMemoryUseCase."""
        event = Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )

        await handler.handle(event)

        generate_memory_use_case.execute.assert_called_once()

    async def test_handle_logs_error_on_exception(
        self,
        handler: SummaryEventHandler,
        generate_memory_use_case: AsyncMock,
        now: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that handler logs errors but doesn't raise."""
        generate_memory_use_case.execute = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        event = Event(
            type=EventType.SUMMARY,
            payload={},
            created_at=now,
        )

        # Should not raise
        await handler.handle(event)

        assert "Error generating memory" in caplog.text
