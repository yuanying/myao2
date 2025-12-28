"""Slack event adapter."""

import re
from datetime import datetime, timezone

from slack_sdk.web.async_client import AsyncWebClient

from myao2.domain.entities import Channel, Message, User
from myao2.domain.repositories import ChannelRepository, UserRepository


class SlackEventAdapter:
    """Convert Slack events to domain entities.

    This adapter translates Slack-specific event payloads into
    platform-independent domain entities. It also caches user and
    channel information to minimize Slack API calls.
    """

    MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")

    def __init__(
        self,
        client: AsyncWebClient,
        user_repository: UserRepository | None = None,
        channel_repository: ChannelRepository | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            client: Slack AsyncWebClient for fetching user info.
            user_repository: Optional user repository for caching.
            channel_repository: Optional channel repository for caching.
        """
        self._client = client
        self._user_repository = user_repository
        self._channel_repository = channel_repository

    async def to_message(self, event: dict) -> Message:
        """Convert a Slack event to a Message entity.

        Args:
            event: Slack app_mention event payload.

        Returns:
            Message entity.
        """
        user_id = event["user"]
        user = await self._get_or_fetch_user(user_id)

        channel_id = event["channel"]
        channel = Channel(
            id=channel_id,
            name="",  # Channel name not provided in event
        )

        # Save channel info to cache if repository is available
        if self._channel_repository is not None:
            await self._channel_repository.save(channel)

        ts = event["ts"]
        timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)

        mentions = self.extract_mentions(event["text"])

        return Message(
            id=ts,
            channel=channel,
            user=user,
            text=event["text"],
            timestamp=timestamp,
            thread_ts=event.get("thread_ts"),
            mentions=mentions,
        )

    async def _get_or_fetch_user(self, user_id: str) -> User:
        """Get user from cache or fetch from Slack API.

        Args:
            user_id: Slack user ID.

        Returns:
            User entity.
        """
        # Try to get from cache first
        if self._user_repository is not None:
            cached_user = await self._user_repository.find_by_id(user_id)
            if cached_user is not None:
                return cached_user

        # Fetch from Slack API
        user_info = await self._client.users_info(user=user_id)
        user_data = user_info["user"]

        user = User(
            id=user_data["id"],
            name=user_data["name"],
            is_bot=user_data.get("is_bot", False),
        )

        # Save to cache if repository is available
        if self._user_repository is not None:
            await self._user_repository.save(user)

        return user

    def extract_mentions(self, text: str) -> list[str]:
        """Extract user mentions from message text.

        Args:
            text: Message text.

        Returns:
            List of mentioned user IDs.
        """
        return self.MENTION_PATTERN.findall(text)
