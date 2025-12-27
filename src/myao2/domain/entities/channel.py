"""Channel entity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    """Channel entity.

    Attributes:
        id: Platform-specific channel ID.
        name: Channel name.
    """

    id: str
    name: str
