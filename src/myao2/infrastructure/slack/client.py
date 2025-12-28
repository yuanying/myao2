"""Slack Bolt client and runner."""

import asyncio

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from myao2.config import SlackConfig


def create_slack_app(config: SlackConfig) -> AsyncApp:
    """Create a Slack Bolt application.

    Args:
        config: Slack connection settings.

    Returns:
        Configured AsyncApp instance.
    """
    return AsyncApp(token=config.bot_token)


class SlackAppRunner:
    """Manage Slack application execution.

    This class handles starting and stopping the Slack app
    using Socket Mode.
    """

    def __init__(self, app: AsyncApp, app_token: str) -> None:
        """Initialize the runner.

        Args:
            app: AsyncApp instance.
            app_token: App-Level Token for Socket Mode.
        """
        self._app = app
        self._app_token = app_token
        self._handler: AsyncSocketModeHandler | None = None

    async def start(self) -> None:
        """Start the app using Socket Mode (async)."""
        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        await self._handler.start_async()

    async def stop(self) -> None:
        """Stop the app."""
        if self._handler is not None:
            await self._handler.close_async()

    async def close(self, timeout: float = 5.0) -> bool:
        """Close the handler with timeout.

        Args:
            timeout: Maximum seconds to wait for close.

        Returns:
            True if closed successfully, False if timed out.
        """
        if self._handler is None:
            return True
        try:
            await asyncio.wait_for(self._handler.close_async(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
