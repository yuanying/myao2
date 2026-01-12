"""Tests for SlackAppRunner."""

from unittest.mock import AsyncMock, Mock

from myao2.infrastructure.slack.client import SlackAppRunner


class TestSlackAppRunnerIsConnected:
    """Tests for is_connected property."""

    def test_is_connected_returns_false_before_start(self) -> None:
        """Test that is_connected returns False before start() is called."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        assert runner.is_connected is False

    def test_is_connected_returns_true_when_client_connected(self) -> None:
        """Test that is_connected returns True when client is connected."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        # Mock the handler with connected client
        mock_session = Mock()
        mock_session.closed = False

        mock_client = Mock()
        mock_client.closed = False
        mock_client.stale = False
        mock_client.current_session = mock_session

        mock_handler = Mock()
        mock_handler.client = mock_client
        runner._handler = mock_handler

        assert runner.is_connected is True

    def test_is_connected_returns_false_when_client_closed(self) -> None:
        """Test that is_connected returns False when client is closed."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        mock_client = Mock()
        mock_client.closed = True
        mock_client.stale = False
        mock_client.current_session = Mock(closed=False)

        mock_handler = Mock()
        mock_handler.client = mock_client
        runner._handler = mock_handler

        assert runner.is_connected is False

    def test_is_connected_returns_false_when_client_stale(self) -> None:
        """Test that is_connected returns False when client is stale."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        mock_client = Mock()
        mock_client.closed = False
        mock_client.stale = True
        mock_client.current_session = Mock(closed=False)

        mock_handler = Mock()
        mock_handler.client = mock_client
        runner._handler = mock_handler

        assert runner.is_connected is False

    def test_is_connected_returns_false_when_no_session(self) -> None:
        """Test that is_connected returns False when no current session."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        mock_client = Mock()
        mock_client.closed = False
        mock_client.stale = False
        mock_client.current_session = None

        mock_handler = Mock()
        mock_handler.client = mock_client
        runner._handler = mock_handler

        assert runner.is_connected is False

    def test_is_connected_returns_false_when_session_closed(self) -> None:
        """Test that is_connected returns False when session is closed."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        mock_session = Mock()
        mock_session.closed = True

        mock_client = Mock()
        mock_client.closed = False
        mock_client.stale = False
        mock_client.current_session = mock_session

        mock_handler = Mock()
        mock_handler.client = mock_client
        runner._handler = mock_handler

        assert runner.is_connected is False

    async def test_is_connected_returns_false_after_stop(self) -> None:
        """Test that is_connected reflects client state after stop."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        # Mock connected state
        mock_session = Mock()
        mock_session.closed = False

        mock_client = Mock()
        mock_client.closed = False
        mock_client.stale = False
        mock_client.current_session = mock_session

        mock_handler = AsyncMock()
        mock_handler.client = mock_client
        mock_handler.close_async = AsyncMock()
        runner._handler = mock_handler

        assert runner.is_connected is True

        # After stop, session should be closed
        mock_session.closed = True
        await runner.stop()

        assert runner.is_connected is False

    def test_is_connected_returns_false_when_handler_is_none(self) -> None:
        """Test that is_connected returns False when handler is None."""
        app = Mock()
        runner = SlackAppRunner(app, "xapp-token")

        runner._handler = None

        assert runner.is_connected is False
