"""Slack conversation history service."""

import re
from datetime import datetime, timezone

from slack_sdk.web.async_client import AsyncWebClient

from myao2.domain.entities import Channel, Message, User


class SlackConversationHistoryService:
    """Slack implementation of ConversationHistoryService.

    Fetches conversation history using Slack API.
    """

    MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")
    EXCLUDED_SUBTYPES = frozenset(
        {
            "bot_message",
            "message_changed",
            "message_deleted",
            "channel_join",
            "channel_leave",
        }
    )

    def __init__(self, client: AsyncWebClient) -> None:
        """Initialize the service.

        Args:
            client: Slack AsyncWebClient.
        """
        self._client = client

    async def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch thread history.

        Uses conversations.replies API.
        Returns all messages including the parent message.

        Args:
            channel_id: Channel ID.
            thread_ts: Parent message timestamp.
            limit: Maximum number of messages to fetch.

        Returns:
            List of messages in chronological order (oldest first).
        """
        response = await self._client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=limit,
        )

        messages = []
        for msg in response.get("messages", []):
            if msg.get("subtype") in self.EXCLUDED_SUBTYPES:
                continue
            messages.append(await self._to_message(msg, channel_id))

        return messages  # Already in chronological order

    async def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """Fetch channel history.

        Uses conversations.history API.

        Args:
            channel_id: Channel ID.
            limit: Maximum number of messages to fetch.

        Returns:
            List of messages in chronological order (oldest first).
        """
        response = await self._client.conversations_history(
            channel=channel_id,
            limit=limit,
        )

        messages = []
        for msg in response.get("messages", []):
            if msg.get("subtype") in self.EXCLUDED_SUBTYPES:
                continue
            messages.append(await self._to_message(msg, channel_id))

        # API returns newest first, so reverse to chronological order
        return list(reversed(messages))

    async def _to_message(self, msg: dict, channel_id: str) -> Message:
        """Convert Slack API response to Message entity.

        Args:
            msg: Slack API message object.
            channel_id: Channel ID.

        Returns:
            Message entity.
        """
        user_id = msg.get("user", "")
        if user_id:
            user = await self._get_user_info(user_id)
        else:
            user = User(id="", name="Unknown", is_bot=True)

        ts = float(msg["ts"])
        timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)

        return Message(
            id=msg["ts"],
            channel=Channel(id=channel_id, name=""),
            user=user,
            text=msg.get("text", ""),
            timestamp=timestamp,
            thread_ts=msg.get("thread_ts"),
            mentions=self._extract_mentions(msg.get("text", "")),
        )

    async def _get_user_info(self, user_id: str) -> User:
        """Get user information.

        Args:
            user_id: User ID.

        Returns:
            User entity.
        """
        user_info = await self._client.users_info(user=user_id)
        user_data = user_info["user"]

        return User(
            id=user_data["id"],
            name=user_data["name"],
            is_bot=user_data.get("is_bot", False),
        )

    def _extract_mentions(self, text: str) -> list[str]:
        """Extract mentions from text.

        Args:
            text: Message text.

        Returns:
            List of mentioned user IDs.
        """
        return self.MENTION_PATTERN.findall(text)
