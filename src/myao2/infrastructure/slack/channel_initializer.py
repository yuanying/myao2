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

    async def sync_channels_with_cleanup(self) -> tuple[list[Channel], list[str]]:
        """Sync channels from Slack API to database with cleanup.

        Fetches all channels the bot has joined, saves them to the database,
        and removes channels that the bot is no longer in.

        Returns:
            Tuple of (synced channels, removed channel IDs).
            Empty lists if API call fails.
        """
        try:
            response = await self._client.users_conversations(
                types="public_channel,private_channel"
            )
            channel_data_list = response.get("channels", [])

            # Get current channel IDs from Slack
            slack_channel_ids = {ch["id"] for ch in channel_data_list}

            # Get existing channel IDs from DB
            existing_channels = await self._channel_repository.find_all()
            existing_channel_ids = {ch.id for ch in existing_channels}

            # Save/update channels from Slack
            channels: list[Channel] = []
            for channel_data in channel_data_list:
                channel = Channel(
                    id=channel_data["id"],
                    name=channel_data["name"],
                )
                await self._channel_repository.save(channel)
                channels.append(channel)

            # Remove channels that are no longer in Slack
            removed_ids: list[str] = []
            for channel_id in existing_channel_ids - slack_channel_ids:
                await self._channel_repository.delete(channel_id)
                removed_ids.append(channel_id)

            logger.info(
                "Synced %d channels, removed %d channels",
                len(channels),
                len(removed_ids),
            )
            return channels, removed_ids

        except Exception as e:
            logger.warning("Failed to sync channels with cleanup: %s", e)
            return [], []

    # Implement ChannelSyncService protocol
    async def sync_with_cleanup(self) -> tuple[list[Channel], list[str]]:
        """Alias for sync_channels_with_cleanup.

        Satisfies the ChannelSyncService protocol.
        """
        return await self.sync_channels_with_cleanup()
