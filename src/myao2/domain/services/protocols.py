"""Domain service protocols."""

from typing import Protocol


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
        user_message: str,
        system_prompt: str,
    ) -> str:
        """Generate a response.

        Args:
            user_message: User's message to respond to.
            system_prompt: System prompt for the response generator.

        Returns:
            Generated response text.
        """
        ...
