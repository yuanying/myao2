"""Helper functions for use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.memory import (
    MemoryScope,
    MemoryType,
    make_thread_scope_id,
)
from myao2.domain.repositories.channel_repository import ChannelRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.repositories.message_repository import MessageRepository

WORKSPACE_SCOPE_ID = "default"
DEFAULT_MESSAGE_LIMIT = 20


def build_channel_messages(
    messages: list[Message],
    channel: Channel,
) -> ChannelMessages:
    """Build ChannelMessages from message list.

    Thread parent messages are included in both top_level_messages and
    as the first message in their respective thread_messages entry.

    Args:
        messages: List of messages.
        channel: The channel.

    Returns:
        ChannelMessages instance.
    """
    top_level_messages: list[Message] = []
    thread_messages: dict[str, list[Message]] = {}
    messages_by_id: dict[str, Message] = {}

    # First pass: categorize messages and build index
    for msg in messages:
        messages_by_id[msg.id] = msg
        if msg.thread_ts is None:
            top_level_messages.append(msg)
        else:
            if msg.thread_ts not in thread_messages:
                thread_messages[msg.thread_ts] = []
            thread_messages[msg.thread_ts].append(msg)

    # Second pass: prepend parent message to each thread
    for thread_ts, replies in thread_messages.items():
        parent_msg = messages_by_id.get(thread_ts)
        if parent_msg is not None and (not replies or replies[0].id != thread_ts):
            thread_messages[thread_ts] = [parent_msg] + replies

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


def create_bot_message_for_thread(
    response_text: str,
    channel: Channel,
    thread_ts: str | None,
    bot_user_id: str,
    bot_name: str,
) -> Message:
    """Create bot response message for a thread.

    Args:
        response_text: The response text.
        channel: The channel to post to.
        thread_ts: Thread timestamp (None for top-level).
        bot_user_id: The bot's user ID.
        bot_name: The bot's display name.

    Returns:
        Bot response Message.
    """
    return Message(
        id=str(uuid.uuid4()),
        channel=channel,
        user=User(
            id=bot_user_id,
            name=bot_name,
            is_bot=True,
        ),
        text=response_text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=thread_ts,
        mentions=[],
    )


async def build_context_with_memory(
    memory_repository: MemoryRepository,
    message_repository: MessageRepository,
    channel_repository: ChannelRepository,
    persona: PersonaConfig,
    channel: Channel | None = None,
    target_thread_ts: str | None = None,
    message_limit: int = DEFAULT_MESSAGE_LIMIT,
    since: datetime | None = None,
) -> Context:
    """Build Context with memory from repository.

    Retrieves messages from the channel, builds ChannelMessages structure,
    and retrieves workspace, channel, and thread memories from the repository.

    Note:
        All channels are included in channel_memories, even those without
        any memory (long_term_memory and short_term_memory will be None).
        When channel is None, an empty ChannelMessages is created (for
        workspace-level memory generation).

    Args:
        memory_repository: Repository for memory access.
        message_repository: Repository for message access.
        channel_repository: Repository for channel access.
        persona: Persona configuration.
        channel: The target channel (None for workspace-level context).
        target_thread_ts: Target thread timestamp (None for top-level).
        message_limit: Maximum number of messages to retrieve.
        since: Message retrieval start time (optional, for GenerateMemory).

    Returns:
        Context instance with messages and memories populated.
    """
    # Retrieve messages from channel (skip if no channel specified)
    if channel:
        if since:
            messages = await message_repository.find_by_channel_since(
                channel_id=channel.id,
                since=since,
                limit=message_limit,
            )
        else:
            messages = await message_repository.find_all_in_channel(
                channel_id=channel.id,
                limit=message_limit,
            )
        # Build ChannelMessages structure
        channel_messages = build_channel_messages(messages, channel)
    else:
        # Empty ChannelMessages for workspace-level context
        channel_messages = ChannelMessages(channel_id="", channel_name="")

    # Retrieve workspace memories
    ws_long_term = await memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE,
        WORKSPACE_SCOPE_ID,
        MemoryType.LONG_TERM,
    )
    ws_short_term = await memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE,
        WORKSPACE_SCOPE_ID,
        MemoryType.SHORT_TERM,
    )

    # Retrieve channel memories for all channels
    channels = await channel_repository.find_all()
    channel_memories: dict[str, ChannelMemory] = {}
    for ch in channels:
        ch_long = await memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, ch.id, MemoryType.LONG_TERM
        )
        ch_short = await memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, ch.id, MemoryType.SHORT_TERM
        )
        channel_memories[ch.id] = ChannelMemory(
            channel_id=ch.id,
            channel_name=ch.name,
            long_term_memory=ch_long.content if ch_long else None,
            short_term_memory=ch_short.content if ch_short else None,
        )

    # Retrieve thread memory for target thread only (requires channel)
    thread_memories: dict[str, str] = {}
    if channel and target_thread_ts:
        scope_id = make_thread_scope_id(channel.id, target_thread_ts)
        thread_mem = await memory_repository.find_by_scope_and_type(
            MemoryScope.THREAD, scope_id, MemoryType.SHORT_TERM
        )
        if thread_mem:
            thread_memories[target_thread_ts] = thread_mem.content

    return Context(
        persona=persona,
        conversation_history=channel_messages,
        workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
        workspace_short_term_memory=ws_short_term.content if ws_short_term else None,
        channel_memories=channel_memories,
        thread_memories=thread_memories,
        target_thread_ts=target_thread_ts,
    )
