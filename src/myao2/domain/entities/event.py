"""Event entity for event-driven architecture."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(Enum):
    """Event types for the event-driven system."""

    MESSAGE = "message"
    SUMMARY = "summary"
    AUTONOMOUS_CHECK = "autonomous_check"
    CHANNEL_SYNC = "channel_sync"


@dataclass(frozen=True)
class Event:
    """Domain event.

    Attributes:
        type: Event type.
        payload: Event-specific data.
        created_at: Event creation time.
    """

    type: EventType
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_identity_key(self) -> str:
        """Get identity key for duplicate detection.

        Returns:
            Unique key based on event type and payload.
        """
        if self.type == EventType.MESSAGE:
            channel_id = self.payload.get("channel_id", "")
            thread_ts = self.payload.get("thread_ts") or ""
            return f"message:{channel_id}:{thread_ts}"
        elif self.type == EventType.SUMMARY:
            return "summary:workspace"
        elif self.type == EventType.AUTONOMOUS_CHECK:
            return "autonomous_check:workspace"
        elif self.type == EventType.CHANNEL_SYNC:
            return "channel_sync:workspace"
        return f"{self.type.value}:unknown"
