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
    bot_user_id: str,
) -> None:
    """Register Slack event handlers.

    Args:
        app: Bolt App instance.
        reply_use_case: Use case for replying to mentions.
        event_adapter: Adapter for converting events to entities.
        bot_user_id: The bot's user ID.
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

    @app.event("message")
    def handle_message(event: dict) -> None:
        """Handle message events.

        Responds to messages that mention the bot when app_mention
        event is not triggered.

        Args:
            event: Slack event payload.
        """
        # Ignore message subtypes (edits, deletes, etc.)
        if event.get("subtype"):
            return

        # Check if bot is mentioned in the message
        text = event.get("text", "")
        if f"<@{bot_user_id}>" not in text:
            return

        logger.info("Received message with mention: %s", event.get("ts"))

        try:
            message = event_adapter.to_message(event)
            reply_use_case.execute(message)
        except Exception:
            logger.exception("Error handling message event")
