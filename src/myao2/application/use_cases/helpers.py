"""Helper functions for use cases."""

import uuid
from datetime import datetime, timezone

from myao2.domain.entities import Channel, Message, User
from myao2.domain.entities.channel_messages import ChannelMessages


def build_channel_messages(
    messages: list[Message],
    channel: Channel,
) -> ChannelMessages:
    """Build ChannelMessages from message list (interim implementation).

    Note: This is an interim implementation for task 04a.
    Thread parent messages are NOT added to thread_messages; only messages
    with thread_ts set are added. Task 08 will implement proper handling
    where thread parent messages are included in both top_level_messages
    and as the first message in their respective thread_messages entry.

    Args:
        messages: List of messages.
        channel: The channel.

    Returns:
        ChannelMessages instance.
    """
    top_level_messages: list[Message] = []
    thread_messages: dict[str, list[Message]] = {}

    for msg in messages:
        if msg.thread_ts is None:
            top_level_messages.append(msg)
        else:
            if msg.thread_ts not in thread_messages:
                thread_messages[msg.thread_ts] = []
            thread_messages[msg.thread_ts].append(msg)

    return ChannelMessages(
        channel_id=channel.id,
        channel_name=channel.name,
        top_level_messages=top_level_messages,
        thread_messages=thread_messages,
    )


def create_bot_message(
    response_text: str,
    original_message: Message,
    bot_user_id: str,
    bot_name: str,
) -> Message:
    """Create bot response message.

    Args:
        response_text: The response text.
        original_message: The original message being replied to.
        bot_user_id: The bot's user ID.
        bot_name: The bot's display name.

    Returns:
        Bot response Message.
    """
    return Message(
        id=str(uuid.uuid4()),
        channel=original_message.channel,
        user=User(
            id=bot_user_id,
            name=bot_name,
            is_bot=True,
        ),
        text=response_text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=original_message.thread_ts,
        mentions=[],
    )
