"""Slack event handlers."""

import logging
from typing import Any

from slack_bolt.async_app import AsyncApp

from myao2.domain.entities import Event, EventType
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.infrastructure.events.queue import EventQueue
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
    event_queue: EventQueue,
    event_adapter: SlackEventAdapter,
    bot_user_id: str,
    message_repository: MessageRepository,
    channel_repository: ChannelRepository,
) -> None:
    """Register Slack event handlers.

    Args:
        app: AsyncApp instance.
        event_queue: Event queue for dispatching events.
        event_adapter: Adapter for converting events to entities.
        bot_user_id: The bot's user ID.
        message_repository: Repository for persisting messages.
        channel_repository: Repository for channel information.
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

        # Handle message_deleted (no channel membership check needed)
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

        # Check if bot is a member of this channel
        channel_id = event.get("channel", "")
        channel = await channel_repository.find_by_id(channel_id)
        if channel is None:
            logger.warning(
                "Received message from channel %s that the bot is not recorded "
                "as a member of. This may indicate an OAuth scope issue, "
                "or a recent channel membership change not yet reflected in DB. "
                "Please verify your Slack App's OAuth scopes.",
                channel_id,
            )
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

        # Enqueue MESSAGE event
        try:
            message_event = Event(
                type=EventType.MESSAGE,
                payload={
                    "channel_id": channel_id,
                    "thread_ts": message.thread_ts,
                    "message": message,
                },
            )
            await event_queue.enqueue(message_event)
            logger.info("Enqueued MESSAGE event: %s", event.get("ts"))
        except Exception:
            logger.exception("Error enqueueing message event")

    @app.event("member_left_channel")
    async def handle_member_left_channel(event: dict) -> None:
        """Handle member_left_channel events.

        When the bot leaves a channel, remove it from the database.

        Args:
            event: Slack event payload.
        """
        user = event.get("user")
        channel_id = event.get("channel")

        # Only process if the bot itself left
        if user != bot_user_id:
            return

        if channel_id is None:
            logger.warning("member_left_channel event missing channel ID")
            return

        logger.info("Bot left channel %s, removing from database", channel_id)
        try:
            await channel_repository.delete(channel_id)
        except Exception:
            logger.exception("Error removing channel %s from database", channel_id)
