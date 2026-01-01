"""Domain service protocols."""

from typing import Protocol

from myao2.domain.entities import Context, Message


class ConversationHistoryService(Protocol):
    """Conversation history retrieval abstraction (platform-independent).

    This protocol defines the interface for fetching conversation history
    from any messaging platform (Slack, Discord, etc.).
    """

    async def fetch_thread_history(
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

    async def fetch_channel_history(
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

    async def send_message(
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

    async def generate(
        self,
        context: Context,
    ) -> str:
        """Generate a response.

        The target thread/message is identified by context.target_thread_ts.
        - If target_thread_ts is None, responds to top-level messages
        - If target_thread_ts is set, responds to the specified thread

        Args:
            context: Conversation context (history, persona info, target_thread_ts).

        Returns:
            Generated response text.
        """
        ...
