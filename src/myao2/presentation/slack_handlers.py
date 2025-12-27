"""Slack event handlers."""

import logging

from slack_bolt import App

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.infrastructure.slack import SlackEventAdapter

logger = logging.getLogger(__name__)


def register_handlers(
    app: App,
    reply_use_case: ReplyToMentionUseCase,
    event_adapter: SlackEventAdapter,
) -> None:
    """Register Slack event handlers.

    Args:
        app: Bolt App instance.
        reply_use_case: Use case for replying to mentions.
        event_adapter: Adapter for converting events to entities.
    """

    @app.event("app_mention")
    def handle_app_mention(event: dict) -> None:
        """Handle app_mention events.

        Args:
            event: Slack event payload.
        """
        logger.info("Received app_mention event: %s", event.get("ts"))

        try:
            message = event_adapter.to_message(event)
            reply_use_case.execute(message)
        except Exception:
            logger.exception("Error handling app_mention event")
