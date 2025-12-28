"""Tests for DBChannelMonitor."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel, Message, User
from myao2.infrastructure.persistence import (
    SQLiteChannelRepository,
    SQLiteMessageRepository,
)
from myao2.infrastructure.persistence.channel_monitor import DBChannelMonitor


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite async engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine):
    """Create async session factory."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    return get_session


@pytest.fixture
def message_repository(session_factory) -> SQLiteMessageRepository:
    """Create test message repository."""
    return SQLiteMessageRepository(session_factory)


@pytest.fixture
def channel_repository(session_factory) -> SQLiteChannelRepository:
    """Create test channel repository."""
    return SQLiteChannelRepository(session_factory)


@pytest.fixture
def monitor(
    message_repository: SQLiteMessageRepository,
    channel_repository: SQLiteChannelRepository,
) -> DBChannelMonitor:
    """Create test monitor."""
    return DBChannelMonitor(
        message_repository=message_repository,
        channel_repository=channel_repository,
        bot_user_id="BOTUSER",
    )


def create_test_message(
    id: str = "1234567890.123456",
    channel_id: str = "C123456",
    user_id: str = "U123456",
    user_name: str = "testuser",
    is_bot: bool = False,
    text: str = "Hello, world!",
    timestamp: datetime | None = None,
    thread_ts: str | None = None,
    mentions: list[str] | None = None,
) -> Message:
    """Create a test Message entity."""
    return Message(
        id=id,
        channel=Channel(id=channel_id, name="general"),
        user=User(id=user_id, name=user_name, is_bot=is_bot),
        text=text,
        timestamp=timestamp or datetime.now(timezone.utc),
        thread_ts=thread_ts,
        mentions=mentions or [],
    )


class TestGetChannels:
    """get_channels method tests."""

    async def test_get_channels_with_channels(
        self,
        monitor: DBChannelMonitor,
        channel_repository: SQLiteChannelRepository,
    ) -> None:
        """Test getting channels when channels exist."""
        await channel_repository.save(Channel(id="C001", name="general"))
        await channel_repository.save(Channel(id="C002", name="random"))
        await channel_repository.save(Channel(id="C003", name="dev"))

        result = await monitor.get_channels()

        assert len(result) == 3
        channel_ids = {c.id for c in result}
        assert channel_ids == {"C001", "C002", "C003"}

    async def test_get_channels_empty(self, monitor: DBChannelMonitor) -> None:
        """Test getting channels when no channels exist."""
        result = await monitor.get_channels()

        assert result == []


class TestGetRecentMessages:
    """get_recent_messages method tests."""

    async def test_get_recent_messages_newest_first(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that messages are returned newest first."""
        base_time = datetime.now(timezone.utc)
        messages = [
            create_test_message(
                id=f"1.{i:03d}",
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(5)
        ]
        for msg in messages:
            await message_repository.save(msg)

        result = await monitor.get_recent_messages("C123456")

        assert len(result) == 5
        # Newest first
        assert result[0].id == "1.004"
        assert result[4].id == "1.000"

    async def test_get_recent_messages_with_since(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test filtering messages by since parameter."""
        base_time = datetime.now(timezone.utc)
        messages = [
            create_test_message(
                id=f"1.{i:03d}",
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(5)
        ]
        for msg in messages:
            await message_repository.save(msg)

        since = base_time + timedelta(minutes=2)
        result = await monitor.get_recent_messages("C123456", since=since)

        assert len(result) == 2
        assert result[0].id == "1.004"
        assert result[1].id == "1.003"

    async def test_get_recent_messages_with_limit(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test limit parameter."""
        for i in range(10):
            await message_repository.save(create_test_message(id=f"1.{i:03d}"))

        result = await monitor.get_recent_messages("C123456", limit=3)

        assert len(result) == 3

    async def test_get_recent_messages_empty(self, monitor: DBChannelMonitor) -> None:
        """Test getting messages from empty channel."""
        result = await monitor.get_recent_messages("C999999")

        assert result == []


class TestGetUnrepliedMessages:
    """get_unreplied_messages method tests."""

    async def test_get_unreplied_messages_basic(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test getting unreplied messages."""
        now = datetime.now(timezone.utc)
        # Message older than min_wait_seconds
        old_message = create_test_message(
            id="1.001",
            user_id="U111",
            timestamp=now - timedelta(minutes=10),
        )
        await message_repository.save(old_message)

        result = await monitor.get_unreplied_messages("C123456", min_wait_seconds=60)

        assert len(result) == 1
        assert result[0].id == "1.001"

    async def test_get_unreplied_messages_excludes_recent(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that recent messages are excluded."""
        now = datetime.now(timezone.utc)
        # Very recent message
        recent_message = create_test_message(
            id="1.001",
            user_id="U111",
            timestamp=now - timedelta(seconds=10),
        )
        await message_repository.save(recent_message)

        result = await monitor.get_unreplied_messages("C123456", min_wait_seconds=60)

        assert result == []

    async def test_get_unreplied_messages_excludes_bot_messages(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that bot's own messages are excluded."""
        now = datetime.now(timezone.utc)
        # Bot's own message
        bot_message = create_test_message(
            id="1.001",
            user_id="BOTUSER",  # Same as bot_user_id in monitor
            is_bot=True,
            timestamp=now - timedelta(minutes=10),
        )
        await message_repository.save(bot_message)

        result = await monitor.get_unreplied_messages("C123456", min_wait_seconds=60)

        assert result == []

    async def test_get_unreplied_messages_excludes_replied_messages(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that messages with bot reply are excluded."""
        now = datetime.now(timezone.utc)
        # User message
        user_message = create_test_message(
            id="1.001",
            user_id="U111",
            timestamp=now - timedelta(minutes=10),
        )
        # Bot reply after user message
        bot_reply = create_test_message(
            id="1.002",
            user_id="BOTUSER",
            is_bot=True,
            timestamp=now - timedelta(minutes=5),
        )
        await message_repository.save(user_message)
        await message_repository.save(bot_reply)

        result = await monitor.get_unreplied_messages("C123456", min_wait_seconds=60)

        assert result == []

    async def test_get_unreplied_messages_includes_message_after_bot_reply(
        self,
        monitor: DBChannelMonitor,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that message after bot reply is included as unreplied."""
        now = datetime.now(timezone.utc)
        # Bot reply
        bot_reply = create_test_message(
            id="1.001",
            user_id="BOTUSER",
            is_bot=True,
            timestamp=now - timedelta(minutes=10),
        )
        # User message after bot reply
        user_message = create_test_message(
            id="1.002",
            user_id="U111",
            timestamp=now - timedelta(minutes=5),
        )
        await message_repository.save(bot_reply)
        await message_repository.save(user_message)

        result = await monitor.get_unreplied_messages("C123456", min_wait_seconds=60)

        assert len(result) == 1
        assert result[0].id == "1.002"
