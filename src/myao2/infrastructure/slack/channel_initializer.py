"""Slack channel initializer for syncing channels at startup."""

import logging

from slack_sdk.web.async_client import AsyncWebClient

from myao2.domain.entities import Channel
from myao2.domain.repositories import ChannelRepository

logger = logging.getLogger(__name__)


class SlackChannelInitializer:
    """Initializes channel information from Slack API at startup.

    Fetches the list of channels the bot has joined and saves them to
    the database. This is called once at application startup to ensure
    DB has current channel information.
    """

    def __init__(
        self,
        client: AsyncWebClient,
        channel_repository: ChannelRepository,
    ) -> None:
        """Initialize the channel initializer.

        Args:
            client: Slack AsyncWebClient for API calls.
            channel_repository: Repository for saving channel information.
        """
        self._client = client
        self._channel_repository = channel_repository

    async def sync_channels(self) -> list[Channel]:
        """Sync channels from Slack API to database.

        Fetches all channels the bot has joined (public and private)
        and saves them to the database.

        Returns:
            List of synced channels. Empty list if API call fails.
        """
        try:
            response = await self._client.users_conversations(
                types="public_channel,private_channel"
            )
            channel_data_list = response.get("channels", [])

            channels: list[Channel] = []
            for channel_data in channel_data_list:
                channel = Channel(
                    id=channel_data["id"],
                    name=channel_data["name"],
                )
                await self._channel_repository.save(channel)
                channels.append(channel)

            logger.info("Synced %d channels from Slack", len(channels))
            return channels

        except Exception as e:
            logger.warning("Failed to sync channels from Slack: %s", e)
            return []
