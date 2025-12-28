"""Periodic checker service for autonomous response."""

import asyncio
import logging

from myao2.application.use_cases.autonomous_response import AutonomousResponseUseCase
from myao2.config import ResponseConfig

logger = logging.getLogger(__name__)


class PeriodicChecker:
    """Periodic check service.

    Executes autonomous response use case at specified intervals.
    Runs as an asyncio task and gracefully shuts down on stop signal.
    """

    def __init__(
        self,
        autonomous_response_usecase: AutonomousResponseUseCase,
        config: ResponseConfig,
    ) -> None:
        """Initialize PeriodicChecker.

        Args:
            autonomous_response_usecase: Use case to execute periodically.
            config: Response configuration with check interval.
        """
        self._usecase = autonomous_response_usecase
        self._config = config
        # _stop_event uses inverted logic:
        # - set() means "stop signal active" (not running)
        # - clear() means "no stop signal" (running)
        # Initially stopped.
        self._stop_event = asyncio.Event()
        self._stop_event.set()

    async def start(self) -> None:
        """Start periodic checking.

        Continues looping until stop signal is received.
        If already running, this method returns immediately after logging a warning.
        """
        # If already running, do not start another loop
        if not self._stop_event.is_set():
            logger.warning(
                "PeriodicChecker.start() called while already running; ignoring."
            )
            return
        self._stop_event.clear()

        while not self._stop_event.is_set():
            try:
                await self._usecase.execute()
            except Exception as e:
                logger.error(
                    "Periodic check failed (interval=%ds): %s",
                    self._config.check_interval_seconds,
                    e,
                )

            # Wait for stop signal or timeout
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._config.check_interval_seconds,
                )
                break  # Stop signal received
            except asyncio.TimeoutError:
                pass  # Timeout, continue to next iteration

    async def stop(self) -> None:
        """Signal periodic checking to stop.

        Signals the loop to stop after current processing completes.
        This method does not wait for the loop task to finish; callers
        should await the task running start() if they need to wait for
        completion.
        """
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if periodic checker is running.

        Returns:
            True if running, False otherwise.
        """
        return not self._stop_event.is_set()
