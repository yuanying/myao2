"""Tests for HealthServer."""

from unittest.mock import AsyncMock, Mock

import pytest

from myao2.infrastructure.http.health_server import HealthServer


@pytest.fixture
def mock_event_loop() -> Mock:
    """Create a mock EventLoop."""
    mock = Mock()
    mock.is_running = True
    return mock


@pytest.fixture
def mock_event_scheduler() -> Mock:
    """Create a mock EventScheduler."""
    mock = Mock()
    mock.is_running = True
    return mock


@pytest.fixture
def mock_slack_runner() -> Mock:
    """Create a mock SlackAppRunner."""
    mock = Mock()
    mock.is_connected = True
    return mock


@pytest.fixture
def mock_db_manager() -> AsyncMock:
    """Create a mock DatabaseManager."""
    mock = AsyncMock()
    mock.is_healthy = AsyncMock(return_value=True)
    return mock


class TestHealthServerLiveness:
    """Tests for liveness check."""

    async def test_liveness_returns_alive_when_event_loop_running(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that liveness returns alive when event loop is running."""
        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,  # Use any available port
        )

        result = await server.check_liveness()

        assert result["status"] == "alive"
        assert "timestamp" in result

    async def test_liveness_returns_dead_when_event_loop_not_running(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that liveness returns dead when event loop is not running."""
        mock_event_loop.is_running = False

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        result = await server.check_liveness()

        assert result["status"] == "dead"


class TestHealthServerReadiness:
    """Tests for readiness check."""

    async def test_readiness_returns_ready_when_all_healthy(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that readiness returns ready when all components are healthy."""
        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        result = await server.check_readiness()

        assert result["ready"] is True
        assert result["event_loop"] is True
        assert result["event_scheduler"] is True
        assert result["slack"] is True
        assert result["database"] is True

    async def test_readiness_returns_not_ready_when_slack_disconnected(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that readiness returns not ready when Slack is disconnected."""
        mock_slack_runner.is_connected = False

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        result = await server.check_readiness()

        assert result["ready"] is False
        assert result["slack"] is False

    async def test_readiness_returns_not_ready_when_db_unhealthy(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that readiness returns not ready when database is unhealthy."""
        mock_db_manager.is_healthy = AsyncMock(return_value=False)

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        result = await server.check_readiness()

        assert result["ready"] is False
        assert result["database"] is False


class TestHealthServerHTTP:
    """Tests for HTTP server functionality."""

    async def test_server_starts_and_stops(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that server can start and stop."""
        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,  # Use any available port
        )

        # Start the server
        await server.start()
        assert server.is_running is True
        assert server.port > 0  # Should have a valid port

        # Stop the server
        await server.stop()
        assert server.is_running is False

    async def test_live_endpoint_returns_200(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that /live endpoint returns 200 when healthy."""
        import aiohttp

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{server.port}/live") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["status"] == "alive"
        finally:
            await server.stop()

    async def test_ready_endpoint_returns_200_when_ready(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that /ready endpoint returns 200 when ready."""
        import aiohttp

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{server.port}/ready") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["ready"] is True
        finally:
            await server.stop()

    async def test_ready_endpoint_returns_503_when_not_ready(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that /ready endpoint returns 503 when not ready."""
        import aiohttp

        mock_slack_runner.is_connected = False

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{server.port}/ready") as resp:
                    assert resp.status == 503
                    data = await resp.json()
                    assert data["ready"] is False
        finally:
            await server.stop()

    async def test_unknown_endpoint_returns_404(
        self,
        mock_event_loop: Mock,
        mock_event_scheduler: Mock,
        mock_slack_runner: Mock,
        mock_db_manager: AsyncMock,
    ) -> None:
        """Test that unknown endpoints return 404."""
        import aiohttp

        server = HealthServer(
            event_loop=mock_event_loop,
            event_scheduler=mock_event_scheduler,
            slack_runner=mock_slack_runner,
            db_manager=mock_db_manager,
            port=0,
        )

        await server.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{server.port}/unknown"
                ) as resp:
                    assert resp.status == 404
        finally:
            await server.stop()
