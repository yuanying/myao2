"""User entity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """User entity (platform-independent).

    Attributes:
        id: Platform-specific user ID.
        name: Display name.
        is_bot: Whether the user is a bot.
    """

    id: str
    name: str
    is_bot: bool = False
