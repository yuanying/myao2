"""Common fixtures for LLM infrastructure tests."""

from datetime import datetime, timezone

import pytest

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.channel_messages import ChannelMessages


@pytest.fixture
def persona_config() -> PersonaConfig:
    """Create test persona config."""
    return PersonaConfig(
        name="myao",
        system_prompt="You are a friendly bot.",
    )


@pytest.fixture
def sample_user() -> User:
    """Create test user."""
    return User(id="U123", name="testuser", is_bot=False)


@pytest.fixture
def sample_bot() -> User:
    """Create test bot."""
    return User(id="B123", name="myao", is_bot=True)


@pytest.fixture
def sample_channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def user_message(
    sample_user: User, sample_channel: Channel, timestamp: datetime
) -> Message:
    """Create test user message."""
    return Message(
        id="1234567890.123456",
        channel=sample_channel,
        user=sample_user,
        text="Hello",
        timestamp=timestamp,
        thread_ts=None,
        mentions=[],
    )


def create_empty_channel_messages(
    channel_id: str = "C123", channel_name: str = "general"
) -> ChannelMessages:
    """Create an empty ChannelMessages instance."""
    return ChannelMessages(channel_id=channel_id, channel_name=channel_name)


@pytest.fixture
def sample_context(persona_config: PersonaConfig) -> Context:
    """Create test context with no history."""
    return Context(
        persona=persona_config,
        conversation_history=create_empty_channel_messages(),
    )
