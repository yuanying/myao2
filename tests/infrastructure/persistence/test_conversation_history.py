"""Tests for DBConversationHistoryService."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel, Message, User
from myao2.infrastructure.persistence import SQLiteMessageRepository
from myao2.infrastructure.persistence.conversation_history import (
    DBConversationHistoryService,
)


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
def service(message_repository) -> DBConversationHistoryService:
    """Create test service."""
    return DBConversationHistoryService(message_repository)


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


class TestFetchThreadHistory:
    """fetch_thread_history method tests."""

    async def test_fetch_returns_messages_oldest_first(
        self,
        service: DBConversationHistoryService,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that messages are returned in chronological order (oldest first)."""
        base_time = datetime.now(timezone.utc)
        thread_ts = "1.000"
        messages = [
            create_test_message(
                id=f"1.{i:03d}",
                thread_ts=thread_ts,
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(3)
        ]
        for msg in messages:
            await message_repository.save(msg)

        result = await service.fetch_thread_history("C123456", thread_ts)

        assert len(result) == 3
        # Oldest first
        assert result[0].id == "1.000"
        assert result[1].id == "1.001"
        assert result[2].id == "1.002"

    async def test_fetch_with_limit(
        self,
        service: DBConversationHistoryService,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test limit parameter."""
        thread_ts = "1.000"
        for i in range(10):
            await message_repository.save(
                create_test_message(id=f"1.{i:03d}", thread_ts=thread_ts)
            )

        result = await service.fetch_thread_history("C123456", thread_ts, limit=3)

        assert len(result) == 3

    async def test_fetch_empty_thread(
        self,
        service: DBConversationHistoryService,
    ) -> None:
        """Test fetching from empty thread."""
        result = await service.fetch_thread_history("C123456", "nonexistent")

        assert result == []


class TestFetchChannelHistory:
    """fetch_channel_history method tests."""

    async def test_fetch_returns_messages_oldest_first(
        self,
        service: DBConversationHistoryService,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that messages are returned in chronological order (oldest first)."""
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

        result = await service.fetch_channel_history("C123456")

        assert len(result) == 5
        # Oldest first
        assert result[0].id == "1.000"
        assert result[4].id == "1.004"

    async def test_fetch_with_limit(
        self,
        service: DBConversationHistoryService,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test limit parameter."""
        for i in range(10):
            await message_repository.save(create_test_message(id=f"1.{i:03d}"))

        result = await service.fetch_channel_history("C123456", limit=3)

        assert len(result) == 3

    async def test_fetch_excludes_thread_messages(
        self,
        service: DBConversationHistoryService,
        message_repository: SQLiteMessageRepository,
    ) -> None:
        """Test that thread messages are excluded."""
        # Channel message
        channel_msg = create_test_message(id="1.001", thread_ts=None)
        # Thread messages
        thread_msg1 = create_test_message(id="1.002", thread_ts="1.000")
        thread_msg2 = create_test_message(id="1.003", thread_ts="1.000")

        await message_repository.save(channel_msg)
        await message_repository.save(thread_msg1)
        await message_repository.save(thread_msg2)

        result = await service.fetch_channel_history("C123456")

        assert len(result) == 1
        assert result[0].id == "1.001"

    async def test_fetch_empty_channel(
        self,
        service: DBConversationHistoryService,
    ) -> None:
        """Test fetching from empty channel."""
        result = await service.fetch_channel_history("C999999")

        assert result == []
