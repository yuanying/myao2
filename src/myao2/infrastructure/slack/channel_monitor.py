"""Slack channel monitor implementation."""

import logging
import re
from datetime import datetime, timezone

from slack_sdk.web.async_client import AsyncWebClient

from myao2.domain.entities import Channel, Message, User

logger = logging.getLogger(__name__)


class SlackChannelMonitor:
    """Slack implementation of ChannelMonitor.

    Monitors channels the bot has joined and detects unreplied messages.
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

    def __init__(
        self,
        client: AsyncWebClient,
        bot_user_id: str,
        message_limit: int = 20,
    ) -> None:
        """Initialize the monitor.

        Args:
            client: Slack AsyncWebClient.
            bot_user_id: Bot's user ID.
            message_limit: Maximum number of messages to fetch.
        """
        self._client = client
        self._bot_user_id = bot_user_id
        self._message_limit = message_limit

    async def get_channels(self) -> list[Channel]:
        """Get channels the bot has joined.

        Returns:
            List of channels.
        """
        try:
            response = await self._client.users_conversations(
                types="public_channel,private_channel",
            )
            channels = []
            for channel_data in response.get("channels", []):
                channels.append(
                    Channel(
                        id=channel_data["id"],
                        name=channel_data["name"],
                    )
                )
            return channels
        except Exception as e:
            logger.warning(f"Failed to get channels: {e}")
            return []

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """Get recent messages from a channel.

        Args:
            channel_id: Channel ID.
            since: Only return messages after this time.
            limit: Maximum number of messages to fetch.

        Returns:
            List of messages in newest first order.
        """
        try:
            response = await self._client.conversations_history(
                channel=channel_id,
                limit=limit,
            )

            messages = []
            for msg in response.get("messages", []):
                if msg.get("subtype") in self.EXCLUDED_SUBTYPES:
                    continue

                message = await self._to_message(msg, channel_id)

                # Filter by since if specified
                if since is not None and message.timestamp <= since:
                    continue

                messages.append(message)

            # API returns newest first, keep that order
            return messages

        except Exception as e:
            logger.warning(f"Failed to get messages from channel {channel_id}: {e}")
            return []

    async def get_unreplied_messages(
        self,
        channel_id: str,
        min_wait_seconds: int,
    ) -> list[Message]:
        """Get unreplied messages from a channel.

        Finds messages that:
        - Are older than min_wait_seconds
        - Are not from the bot itself
        - Have not been replied to by the bot

        Args:
            channel_id: Channel ID.
            min_wait_seconds: Minimum wait time in seconds.

        Returns:
            List of unreplied messages.
        """
        try:
            response = await self._client.conversations_history(
                channel=channel_id,
                limit=self._message_limit,
            )

            raw_messages = response.get("messages", [])
            if not raw_messages:
                return []

            now = datetime.now(timezone.utc)
            cutoff_time = now.timestamp() - min_wait_seconds

            # Convert all messages and build context
            all_messages: list[Message] = []
            for msg in raw_messages:
                if msg.get("subtype") in self.EXCLUDED_SUBTYPES:
                    continue
                message = await self._to_message(msg, channel_id)
                all_messages.append(message)

            # Find bot messages for quick lookup
            bot_message_times: list[float] = []
            for msg in all_messages:
                if msg.user.id == self._bot_user_id:
                    bot_message_times.append(msg.timestamp.timestamp())

            unreplied_messages: list[Message] = []

            for msg in all_messages:
                # Skip if bot's own message
                if msg.user.id == self._bot_user_id:
                    continue

                # Skip if too recent
                msg_ts = msg.timestamp.timestamp()
                if msg_ts > cutoff_time:
                    continue

                # Check if bot replied after this message
                bot_replied = False

                # For thread messages, check thread replies
                if msg.thread_ts:
                    bot_replied = await self._check_bot_replied_in_thread(
                        channel_id, msg.thread_ts, msg_ts
                    )
                else:
                    # For channel messages, check if bot replied after this message
                    for bot_time in bot_message_times:
                        if bot_time > msg_ts:
                            bot_replied = True
                            break

                if not bot_replied:
                    unreplied_messages.append(msg)

            return unreplied_messages

        except Exception as e:
            logger.warning(
                f"Failed to get unreplied messages from channel {channel_id}: {e}"
            )
            return []

    async def _check_bot_replied_in_thread(
        self,
        channel_id: str,
        thread_ts: str,
        message_ts: float,
    ) -> bool:
        """Check if bot has replied in a thread after a specific message.

        Args:
            channel_id: Channel ID.
            thread_ts: Thread timestamp.
            message_ts: Message timestamp to check for replies after.

        Returns:
            True if bot has replied after the message.
        """
        try:
            response = await self._client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=self._message_limit,
            )

            for msg in response.get("messages", []):
                msg_ts = float(msg["ts"])
                user_id = msg.get("user", "")

                # Check if bot replied after the message
                if user_id == self._bot_user_id and msg_ts > message_ts:
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check thread replies: {e}")
            return False

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
            # System messages (e.g., channel events) don't have a user field.
            # Mark as bot to exclude from response consideration.
            user = User(id="system", name="System", is_bot=True)

        ts = float(msg["ts"])
        timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)

        # Channel name is left empty to avoid extra API calls.
        # The channel ID is sufficient for message processing.
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
