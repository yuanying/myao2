"""Tests for SQLiteChannelRepository."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel
from myao2.infrastructure.persistence import SQLiteChannelRepository


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
def repository(session_factory) -> SQLiteChannelRepository:
    """Create test repository."""
    return SQLiteChannelRepository(session_factory)


def create_test_channel(
    id: str = "C123456",
    name: str = "general",
) -> Channel:
    """Create a test Channel entity."""
    return Channel(id=id, name=name)


class TestSave:
    """save method tests."""

    async def test_save_new_channel(self, repository: SQLiteChannelRepository) -> None:
        """Test saving a new channel."""
        channel = create_test_channel()

        await repository.save(channel)

        found = await repository.find_by_id(channel.id)
        assert found is not None
        assert found.id == channel.id
        assert found.name == channel.name

    async def test_save_updates_existing_channel(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test that save updates existing channel with same ID."""
        channel = create_test_channel(name="original-name")
        await repository.save(channel)

        # Update channel name
        updated_channel = create_test_channel(name="updated-name")
        await repository.save(updated_channel)

        found = await repository.find_by_id(channel.id)
        assert found is not None
        assert found.name == "updated-name"

    async def test_save_multiple_channels(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test saving multiple different channels."""
        channel1 = create_test_channel(id="C001", name="channel-one")
        channel2 = create_test_channel(id="C002", name="channel-two")
        channel3 = create_test_channel(id="C003", name="channel-three")

        await repository.save(channel1)
        await repository.save(channel2)
        await repository.save(channel3)

        assert await repository.find_by_id("C001") is not None
        assert await repository.find_by_id("C002") is not None
        assert await repository.find_by_id("C003") is not None


class TestFindAll:
    """find_all method tests."""

    async def test_find_all_with_channels(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test finding all channels when channels exist."""
        channel1 = create_test_channel(id="C001", name="channel-one")
        channel2 = create_test_channel(id="C002", name="channel-two")
        channel3 = create_test_channel(id="C003", name="channel-three")

        await repository.save(channel1)
        await repository.save(channel2)
        await repository.save(channel3)

        result = await repository.find_all()

        assert len(result) == 3
        channel_ids = {c.id for c in result}
        assert channel_ids == {"C001", "C002", "C003"}

    async def test_find_all_empty(self, repository: SQLiteChannelRepository) -> None:
        """Test finding all channels when no channels exist."""
        result = await repository.find_all()

        assert result == []


class TestFindById:
    """find_by_id method tests."""

    async def test_find_existing_channel(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test finding existing channel by ID."""
        channel = create_test_channel()
        await repository.save(channel)

        found = await repository.find_by_id(channel.id)

        assert found is not None
        assert found.id == channel.id
        assert found.name == channel.name

    async def test_find_nonexistent_channel(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test finding nonexistent channel returns None."""
        found = await repository.find_by_id("nonexistent")

        assert found is None


class TestDelete:
    """delete method tests."""

    async def test_delete_existing_channel(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test deleting an existing channel."""
        channel = create_test_channel()
        await repository.save(channel)

        result = await repository.delete(channel.id)

        assert result is True
        assert await repository.find_by_id(channel.id) is None

    async def test_delete_nonexistent_channel(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test deleting a nonexistent channel returns False."""
        result = await repository.delete("nonexistent")

        assert result is False

    async def test_delete_does_not_affect_other_channels(
        self, repository: SQLiteChannelRepository
    ) -> None:
        """Test deleting a channel does not affect other channels."""
        channel1 = create_test_channel(id="C001", name="channel-one")
        channel2 = create_test_channel(id="C002", name="channel-two")
        await repository.save(channel1)
        await repository.save(channel2)

        await repository.delete("C001")

        assert await repository.find_by_id("C001") is None
        assert await repository.find_by_id("C002") is not None
