"""Domain service protocols."""

from typing import Protocol

from myao2.domain.entities import Context, Message


class ConversationHistoryService(Protocol):
    """Conversation history retrieval abstraction (platform-independent).

    This protocol defines the interface for fetching conversation history
    from any messaging platform (Slack, Discord, etc.).
    """

    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch thread history.

        Args:
            channel_id: Channel ID.
            thread_ts: Parent message timestamp.
            limit: Maximum number of messages to fetch.

        Returns:
            List of messages in chronological order (oldest first).
        """
        ...

    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch channel history.

        Args:
            channel_id: Channel ID.
            limit: Maximum number of messages to fetch.

        Returns:
            List of messages in chronological order (oldest first).
        """
        ...


class MessagingService(Protocol):
    """Messaging abstraction (platform-independent).

    This protocol defines the interface for sending messages
    to any messaging platform (Slack, Discord, etc.).
    """

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> None:
        """Send a message to a channel.

        Args:
            channel_id: Target channel ID.
            text: Message content.
            thread_ts: Thread timestamp for thread replies.
        """
        ...


class ResponseGenerator(Protocol):
    """Response generation abstraction.

    This protocol defines the interface for generating
    responses using LLM or other mechanisms.
    """

    def generate(
        self,
        user_message: Message,
        context: Context,
    ) -> str:
        """Generate a response.

        Args:
            user_message: User's message to respond to.
            context: Conversation context (history, persona info).

        Returns:
            Generated response text.
        """
        ...
