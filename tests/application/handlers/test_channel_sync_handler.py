"""Tests for ChannelSyncEventHandler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from myao2.application.handlers.channel_sync_handler import ChannelSyncEventHandler
from myao2.domain.entities import Event, EventType


class TestChannelSyncEventHandler:
    """Tests for ChannelSyncEventHandler."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed timestamp."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def channel_sync_service(self) -> AsyncMock:
        """Create mock ChannelSyncService."""
        mock = AsyncMock()
        mock.sync_with_cleanup = AsyncMock(return_value=([], []))
        return mock

    @pytest.fixture
    def handler(
        self,
        channel_sync_service: AsyncMock,
    ) -> ChannelSyncEventHandler:
        """Create handler instance."""
        return ChannelSyncEventHandler(
            channel_sync_service=channel_sync_service,
        )

    def test_has_event_handler_decorator(
        self, handler: ChannelSyncEventHandler
    ) -> None:
        """Test that handle method has event_handler decorator."""
        assert hasattr(handler.handle, "_event_type")
        assert handler.handle._event_type == EventType.CHANNEL_SYNC

    async def test_handle_calls_channel_sync_service(
        self,
        handler: ChannelSyncEventHandler,
        channel_sync_service: AsyncMock,
        now: datetime,
    ) -> None:
        """Test that handler calls ChannelSyncService."""
        event = Event(
            type=EventType.CHANNEL_SYNC,
            payload={},
            created_at=now,
        )

        await handler.handle(event)

        channel_sync_service.sync_with_cleanup.assert_called_once()

    async def test_handle_logs_error_on_exception(
        self,
        handler: ChannelSyncEventHandler,
        channel_sync_service: AsyncMock,
        now: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that handler logs errors but doesn't raise."""
        channel_sync_service.sync_with_cleanup = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        event = Event(
            type=EventType.CHANNEL_SYNC,
            payload={},
            created_at=now,
        )

        # Should not raise
        await handler.handle(event)

        assert "Error syncing channels" in caplog.text
