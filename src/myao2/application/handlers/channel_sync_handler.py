"""Channel sync event handler."""

import logging

from myao2.domain.entities import Event
from myao2.domain.entities.event import EventType
from myao2.domain.services import ChannelSyncService
from myao2.infrastructure.events.dispatcher import event_handler

logger = logging.getLogger(__name__)


class ChannelSyncEventHandler:
    """Handler for CHANNEL_SYNC events.

    Triggers channel synchronization with external service.
    """

    def __init__(
        self,
        channel_sync_service: ChannelSyncService,
    ) -> None:
        """Initialize the handler.

        Args:
            channel_sync_service: Service for syncing channels.
        """
        self._channel_sync_service = channel_sync_service

    @event_handler(EventType.CHANNEL_SYNC)
    async def handle(self, event: Event) -> None:
        """Handle CHANNEL_SYNC event.

        Args:
            event: The CHANNEL_SYNC event.
        """
        logger.info("Handling CHANNEL_SYNC event")

        try:
            synced, removed = await self._channel_sync_service.sync_with_cleanup()
            logger.info(
                "CHANNEL_SYNC event handled: synced=%d, removed=%d",
                len(synced),
                len(removed),
            )
        except Exception:
            logger.exception("Error syncing channels")
