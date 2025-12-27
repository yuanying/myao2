"""Slack event adapter."""

import re
from datetime import datetime, timezone

from slack_sdk import WebClient

from myao2.domain.entities import Channel, Message, User


class SlackEventAdapter:
    """Convert Slack events to domain entities.

    This adapter translates Slack-specific event payloads into
    platform-independent domain entities.
    """

    MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")

    def __init__(self, client: WebClient) -> None:
        """Initialize the adapter.

        Args:
            client: Slack WebClient for fetching user info.
        """
        self._client = client

    def to_message(self, event: dict) -> Message:
        """Convert a Slack event to a Message entity.

        Args:
            event: Slack app_mention event payload.

        Returns:
            Message entity.
        """
        user_id = event["user"]
        user_info = self._client.users_info(user=user_id)
        user_data = user_info["user"]

        user = User(
            id=user_data["id"],
            name=user_data["name"],
            is_bot=user_data.get("is_bot", False),
        )

        channel = Channel(
            id=event["channel"],
            name="",  # Channel name not provided in event
        )

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

    def extract_mentions(self, text: str) -> list[str]:
        """Extract user mentions from message text.

        Args:
            text: Message text.

        Returns:
            List of mentioned user IDs.
        """
        return self.MENTION_PATTERN.findall(text)
