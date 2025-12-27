"""Slack Bolt client and runner."""

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from myao2.config import SlackConfig


def create_slack_app(config: SlackConfig) -> App:
    """Create a Slack Bolt application.

    Args:
        config: Slack connection settings.

    Returns:
        Configured Bolt App instance.
    """
    return App(token=config.bot_token)


class SlackAppRunner:
    """Manage Slack application execution.

    This class handles starting and stopping the Slack app
    using Socket Mode.
    """

    def __init__(self, app: App, app_token: str) -> None:
        """Initialize the runner.

        Args:
            app: Bolt App instance.
            app_token: App-Level Token for Socket Mode.
        """
        self._app = app
        self._handler = SocketModeHandler(app, app_token)

    def start(self) -> None:
        """Start the app using Socket Mode (blocking)."""
        self._handler.start()

    def stop(self) -> None:
        """Stop the app."""
        self._handler.close()
