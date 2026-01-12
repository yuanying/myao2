"""Health check HTTP server."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aiohttp import web

if TYPE_CHECKING:
    from myao2.infrastructure.events.loop import EventLoop
    from myao2.infrastructure.events.scheduler import EventScheduler
    from myao2.infrastructure.persistence.database import DatabaseManager
    from myao2.infrastructure.slack.client import SlackAppRunner

logger = logging.getLogger(__name__)


class HealthServer:
    """HTTP server for health check endpoints.

    Provides /live and /ready endpoints for Kubernetes probes.
    """

    def __init__(
        self,
        event_loop: EventLoop,
        event_scheduler: EventScheduler,
        slack_runner: SlackAppRunner,
        db_manager: DatabaseManager,
        port: int = 8080,
    ) -> None:
        """Initialize the health server.

        Args:
            event_loop: EventLoop instance.
            event_scheduler: EventScheduler instance.
            slack_runner: SlackAppRunner instance.
            db_manager: DatabaseManager instance.
            port: Port to listen on. Use 0 for any available port.
        """
        self._event_loop = event_loop
        self._event_scheduler = event_scheduler
        self._slack_runner = slack_runner
        self._db_manager = db_manager
        self._port = port
        self._actual_port = port
        self._server: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def port(self) -> int:
        """Get the port the server is listening on."""
        return self._actual_port

    async def check_liveness(self) -> dict[str, Any]:
        """Check if the application is alive.

        Returns:
            Liveness status with timestamp.
        """
        is_alive = self._event_loop.is_running
        return {
            "status": "alive" if is_alive else "dead",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def check_readiness(self) -> dict[str, Any]:
        """Check if the application is ready to serve traffic.

        Returns:
            Readiness status with component health details.
        """
        event_loop_ok = self._event_loop.is_running
        event_scheduler_ok = self._event_scheduler.is_running
        slack_ok = self._slack_runner.is_connected
        db_ok = await self._db_manager.is_healthy()

        ready = event_loop_ok and event_scheduler_ok and slack_ok and db_ok

        return {
            "ready": ready,
            "event_loop": event_loop_ok,
            "event_scheduler": event_scheduler_ok,
            "slack": slack_ok,
            "database": db_ok,
        }

    async def _handle_live(self, request: web.Request) -> web.Response:
        """Handle /live endpoint."""
        result = await self.check_liveness()
        return web.json_response(result)

    async def _handle_ready(self, request: web.Request) -> web.Response:
        """Handle /ready endpoint."""
        result = await self.check_readiness()
        status = 200 if result["ready"] else 503
        return web.json_response(result, status=status)

    async def start(self) -> None:
        """Start the HTTP server."""
        app = web.Application()
        app.router.add_get("/live", self._handle_live)
        app.router.add_get("/ready", self._handle_ready)

        self._server = web.AppRunner(app)
        await self._server.setup()

        self._site = web.TCPSite(self._server, "0.0.0.0", self._port)
        await self._site.start()

        # Get actual port (useful when port=0 for dynamic allocation)
        if self._site._server is not None:
            sockets = self._site._server.sockets  # type: ignore[union-attr]
            if sockets:
                self._actual_port = sockets[0].getsockname()[1]

        self._running = True
        logger.info("Health server started on port %d", self.port)

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server is not None:
            await self._server.cleanup()
            self._server = None
            self._site = None

        self._running = False
        logger.info("Health server stopped")
