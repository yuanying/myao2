"""Autonomous check event handler."""

import logging

from myao2.application.use_cases.autonomous_response import AutonomousResponseUseCase
from myao2.domain.entities import Event
from myao2.domain.entities.event import EventType
from myao2.infrastructure.events.dispatcher import event_handler

logger = logging.getLogger(__name__)


class AutonomousCheckEventHandler:
    """Handler for AUTONOMOUS_CHECK events.

    Triggers autonomous response checking.
    """

    def __init__(
        self,
        autonomous_response_use_case: AutonomousResponseUseCase,
    ) -> None:
        """Initialize the handler.

        Args:
            autonomous_response_use_case: Use case for autonomous responses.
        """
        self._autonomous_response_use_case = autonomous_response_use_case

    @event_handler(EventType.AUTONOMOUS_CHECK)
    async def handle(self, event: Event) -> None:
        """Handle AUTONOMOUS_CHECK event.

        Args:
            event: The AUTONOMOUS_CHECK event.
        """
        logger.info("Handling AUTONOMOUS_CHECK event")

        try:
            await self._autonomous_response_use_case.execute()
            logger.info("AUTONOMOUS_CHECK event handled successfully")
        except Exception:
            logger.exception("Error in autonomous check")
