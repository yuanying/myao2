"""Background memory generation service."""

import asyncio
import logging

from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.config.models import MemoryConfig

logger = logging.getLogger(__name__)


class BackgroundMemoryGenerator:
    """Background memory generation service.

    Periodically generates memories at specified intervals.
    Runs as an asyncio task and gracefully shuts down on stop signal.
    """

    def __init__(
        self,
        generate_memory_use_case: GenerateMemoryUseCase,
        config: MemoryConfig,
    ) -> None:
        """Initialize BackgroundMemoryGenerator.

        Args:
            generate_memory_use_case: Use case for memory generation.
            config: Memory configuration with update interval.
        """
        self._generate_memory_use_case = generate_memory_use_case
        self._config = config
        # _stop_event uses inverted logic:
        # - set() means "stop signal active" (not running)
        # - clear() means "no stop signal" (running)
        # Initially stopped.
        self._stop_event = asyncio.Event()
        self._stop_event.set()

    async def start(self) -> None:
        """Start memory generation loop.

        Continues looping until stop signal is received.
        Executes immediately on start, then periodically at configured interval.
        If already running, this method returns immediately after logging a warning.
        """
        # If already running, do not start another loop
        if not self._stop_event.is_set():
            logger.warning(
                "BackgroundMemoryGenerator.start() called while already running; "
                "ignoring."
            )
            return
        self._stop_event.clear()

        logger.info("Starting background memory generator")

        while not self._stop_event.is_set():
            try:
                logger.info("Running memory generation")
                await self._generate_memory_use_case.execute()
                logger.info("Memory generation completed")
            except Exception:
                logger.exception("Error during memory generation")

            # Wait for stop signal or timeout
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._config.long_term_update_interval_seconds,
                )
                break  # Stop signal received
            except asyncio.TimeoutError:
                pass  # Timeout, continue to next iteration

        logger.info("Background memory generator stopped")

    async def stop(self) -> None:
        """Signal memory generation loop to stop.

        Signals the loop to stop after current processing completes.
        This method does not wait for the loop task to finish; callers
        should await the task running start() if they need to wait for
        completion.
        """
        logger.info("Stopping background memory generator")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if generator is running.

        Returns:
            True if running, False otherwise.
        """
        return not self._stop_event.is_set()
