"""Summary event handler."""

import logging

from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.domain.entities import Event
from myao2.domain.entities.event import EventType
from myao2.infrastructure.events.dispatcher import event_handler

logger = logging.getLogger(__name__)


class SummaryEventHandler:
    """Handler for SUMMARY events.

    Triggers memory generation.
    """

    def __init__(
        self,
        generate_memory_use_case: GenerateMemoryUseCase,
    ) -> None:
        """Initialize the handler.

        Args:
            generate_memory_use_case: Use case for generating memories.
        """
        self._generate_memory_use_case = generate_memory_use_case

    @event_handler(EventType.SUMMARY)
    async def handle(self, event: Event) -> None:
        """Handle SUMMARY event.

        Args:
            event: The SUMMARY event.
        """
        logger.info("Handling SUMMARY event")

        try:
            await self._generate_memory_use_case.execute()
            logger.info("SUMMARY event handled successfully")
        except Exception:
            logger.exception("Error generating memory")
