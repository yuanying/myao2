"""Slack messaging service."""

from slack_sdk.web.async_client import AsyncWebClient


class SlackMessagingService:
    """Slack implementation of MessagingService.

    This class implements the MessagingService protocol for Slack,
    providing message sending capabilities.
    """

    def __init__(self, client: AsyncWebClient) -> None:
        """Initialize the service.

        Args:
            client: Slack AsyncWebClient instance.
        """
        self._client = client
        self._bot_user_id: str | None = None

    async def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> None:
        """Send a message to a Slack channel.

        Args:
            channel_id: Target channel ID.
            text: Message content.
            thread_ts: Thread timestamp for thread replies.

        Raises:
            SlackApiError: If the API call fails.
        """
        await self._client.chat_postMessage(
            channel=channel_id,
            text=text,
            thread_ts=thread_ts,
        )

    async def get_bot_user_id(self) -> str:
        """Get the bot's user ID.

        Returns:
            The bot's user ID.

        Note:
            The result is cached after the first call.
        """
        if self._bot_user_id is None:
            response = await self._client.auth_test()
            self._bot_user_id = response["user_id"]
        return self._bot_user_id
