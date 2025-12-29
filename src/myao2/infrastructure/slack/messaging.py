"""Slack messaging service."""

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from myao2.domain.exceptions import ChannelNotAccessibleError

# Error codes that indicate the channel is not accessible
_CHANNEL_NOT_ACCESSIBLE_ERRORS = frozenset(
    {
        "not_in_channel",
        "channel_not_found",
        "is_archived",
    }
)


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
            ChannelNotAccessibleError: If the channel is not accessible
                (not_in_channel, channel_not_found, is_archived).
            SlackApiError: If the API call fails for other reasons.
        """
        try:
            await self._client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts,
            )
        except SlackApiError as e:
            error_code = (
                e.response.get("error", "") if isinstance(e.response, dict) else ""
            )
            if error_code in _CHANNEL_NOT_ACCESSIBLE_ERRORS:
                message = (
                    f"Cannot access channel {channel_id}: {error_code}"
                    if error_code
                    else f"Cannot access channel {channel_id}: {e!s}"
                )
                raise ChannelNotAccessibleError(channel_id, message) from e
            raise

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
