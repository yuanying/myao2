"""Slack event handlers."""

import logging
from typing import Any

from slack_bolt.async_app import AsyncApp

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.domain.repositories import MessageRepository
from myao2.infrastructure.slack import SlackEventAdapter

logger = logging.getLogger(__name__)


def _unwrap_message_changed(event: dict[str, Any]) -> dict[str, Any]:
    """Extract inner message from message_changed event.

    Args:
        event: Slack message_changed event payload.

    Returns:
        Unwrapped message with channel from outer event.
    """
    inner_message = event.get("message", {})
    return {
        **inner_message,
        "channel": event.get("channel"),
    }


def register_handlers(
    app: AsyncApp,
    reply_use_case: ReplyToMentionUseCase,
    event_adapter: SlackEventAdapter,
    bot_user_id: str,
    message_repository: MessageRepository,
) -> None:
    """Register Slack event handlers.

    Args:
        app: AsyncApp instance.
        reply_use_case: Use case for replying to mentions.
        event_adapter: Adapter for converting events to entities.
        bot_user_id: The bot's user ID.
        message_repository: Repository for persisting messages.
    """

    @app.event("app_mention")
    async def handle_app_mention(event: dict) -> None:
        """Handle app_mention events (no-op).

        This handler exists to acknowledge app_mention events and suppress
        slack-bolt warnings. The actual processing is done by handle_message
        which receives the same message event.
        """
        logger.debug("Received app_mention event: %s", event.get("ts"))

    @app.event("message")
    async def handle_message(event: dict) -> None:
        """Handle message events.

        Saves all messages to DB, handles edits and deletes,
        and responds to messages that mention the bot.

        Args:
            event: Slack event payload.
        """
        subtype = event.get("subtype")
        logger.info(
            "Processing message event: ts=%s, subtype=%s, channel=%s",
            event.get("ts"),
            subtype,
            event.get("channel"),
        )

        # Handle message_deleted
        if subtype == "message_deleted":
            try:
                await message_repository.delete(
                    message_id=event.get("deleted_ts", ""),
                    channel_id=event.get("channel", ""),
                )
                logger.debug("Deleted message: %s", event.get("deleted_ts"))
            except Exception:
                logger.exception("Error deleting message")
            return

        # Determine event data to process
        if subtype == "message_changed":
            event_data = _unwrap_message_changed(event)
        elif subtype in {None, "bot_message", "thread_broadcast"}:
            event_data = event
        else:
            # Ignore other subtypes
            return

        # Convert event to message
        try:
            message = await event_adapter.to_message(event_data)
        except Exception:
            logger.exception("Error converting event to message")
            return

        # Save message to DB (continue even if save fails)
        try:
            await message_repository.save(message)
        except Exception:
            logger.exception("Error saving message to DB")

        # For message_changed, we only update DB
        if subtype == "message_changed":
            logger.debug("Updated message: %s", event_data.get("ts"))
            return

        # Check if bot is mentioned in the message
        text = event.get("text", "")
        if f"<@{bot_user_id}>" not in text:
            return

        logger.info("Received message with mention: %s", event.get("ts"))

        try:
            await reply_use_case.execute(message)
        except Exception:
            logger.exception("Error handling message event")
