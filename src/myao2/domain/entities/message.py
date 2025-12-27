"""Message entity."""

from dataclasses import dataclass, field
from datetime import datetime

from myao2.domain.entities.channel import Channel
from myao2.domain.entities.user import User


@dataclass(frozen=True)
class Message:
    """Message entity.

    Attributes:
        id: Platform-specific message ID.
        channel: Channel where the message was posted.
        user: User who sent the message.
        text: Message content.
        timestamp: When the message was sent.
        thread_ts: Parent message timestamp (if in a thread).
        mentions: List of user IDs mentioned in the message.
    """

    id: str
    channel: Channel
    user: User
    text: str
    timestamp: datetime
    thread_ts: str | None = None
    mentions: list[str] = field(default_factory=list)

    def is_in_thread(self) -> bool:
        """Check if this message is in a thread.

        Returns:
            True if the message is a thread reply.
        """
        return self.thread_ts is not None

    def mentions_user(self, user_id: str) -> bool:
        """Check if a user is mentioned in this message.

        Args:
            user_id: The user ID to check.

        Returns:
            True if the user is mentioned.
        """
        return user_id in self.mentions
