"""Message formatting utilities for system prompts."""

from myao2.domain.entities.message import Message


def format_message_with_metadata(message: Message) -> str:
    """Format a message with timestamp and username.

    Args:
        message: The message to format.

    Returns:
        Formatted string like "[2024-01-01 12:00:00] username: message text"
    """
    timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message.user.name}: {message.text}"


def format_conversation_history(messages: list[Message]) -> str:
    """Format conversation history as a string.

    Args:
        messages: List of messages in chronological order.

    Returns:
        Formatted string with each message on a new line,
        or "(会話履歴なし)" if empty.
    """
    if not messages:
        return "(会話履歴なし)"
    return "\n".join(format_message_with_metadata(msg) for msg in messages)


def format_other_channels(channels: dict[str, list[Message]]) -> str | None:
    """Format messages from other channels.

    Args:
        channels: Dict mapping channel names to their messages.

    Returns:
        Formatted string with channel sections, or None if no messages.
    """
    if not channels:
        return None

    parts: list[str] = []
    for channel_name, messages in channels.items():
        if messages:
            formatted_msgs = "\n".join(
                f"- {format_message_with_metadata(msg)}" for msg in messages
            )
            channel_section = f"### #{channel_name}\n{formatted_msgs}\n"
            parts.append(channel_section)

    return "\n".join(parts) if parts else None
