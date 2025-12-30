"""ChannelMessages and ChannelMemory entities."""

from dataclasses import dataclass, field

from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class ChannelMemory:
    """Channel memory data class.

    Attributes:
        channel_id: Channel ID.
        channel_name: Channel name.
        long_term_memory: Long-term memory (timeline summary).
        short_term_memory: Short-term memory (recent summary).
    """

    channel_id: str
    channel_name: str
    long_term_memory: str | None = None
    short_term_memory: str | None = None


@dataclass(frozen=True)
class ChannelMessages:
    """Channel messages data class.

    Holds messages in a structured format with top-level and thread messages.

    Attributes:
        channel_id: Channel ID.
        channel_name: Channel name.
        top_level_messages: Top-level messages (including thread parent messages).
        thread_messages: Thread messages map (thread_ts -> message list).
    """

    channel_id: str
    channel_name: str
    top_level_messages: list[Message] = field(default_factory=list)
    thread_messages: dict[str, list[Message]] = field(default_factory=dict)

    def get_all_messages(self) -> list[Message]:
        """Get all messages in chronological order.

        Returns:
            List of all messages sorted by timestamp.
        """
        all_msgs = list(self.top_level_messages)
        for thread_msgs in self.thread_messages.values():
            all_msgs.extend(thread_msgs)
        return sorted(all_msgs, key=lambda m: m.timestamp)

    def get_thread(self, thread_ts: str) -> list[Message]:
        """Get messages for a specific thread.

        Args:
            thread_ts: Thread parent message timestamp.

        Returns:
            List of messages in the thread (empty if thread doesn't exist).
        """
        return self.thread_messages.get(thread_ts, [])

    @property
    def thread_count(self) -> int:
        """Get the number of threads."""
        return len(self.thread_messages)

    @property
    def total_message_count(self) -> int:
        """Get the total number of messages."""
        return len(self.top_level_messages) + sum(
            len(msgs) for msgs in self.thread_messages.values()
        )
