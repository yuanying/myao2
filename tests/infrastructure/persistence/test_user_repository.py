"""Tests for SQLiteUserRepository."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import User
from myao2.infrastructure.persistence import SQLiteUserRepository


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
def repository(session_factory) -> SQLiteUserRepository:
    """Create test repository."""
    return SQLiteUserRepository(session_factory)


def create_test_user(
    id: str = "U123456",
    name: str = "testuser",
    is_bot: bool = False,
) -> User:
    """Create a test User entity."""
    return User(id=id, name=name, is_bot=is_bot)


class TestSave:
    """save method tests."""

    async def test_save_new_user(self, repository: SQLiteUserRepository) -> None:
        """Test saving a new user."""
        user = create_test_user()

        await repository.save(user)

        found = await repository.find_by_id(user.id)
        assert found is not None
        assert found.id == user.id
        assert found.name == user.name
        assert found.is_bot == user.is_bot

    async def test_save_updates_existing_user(
        self, repository: SQLiteUserRepository
    ) -> None:
        """Test that save updates existing user with same ID."""
        user = create_test_user(name="Original Name")
        await repository.save(user)

        # Update user name
        updated_user = create_test_user(name="Updated Name")
        await repository.save(updated_user)

        found = await repository.find_by_id(user.id)
        assert found is not None
        assert found.name == "Updated Name"

    async def test_save_multiple_users(self, repository: SQLiteUserRepository) -> None:
        """Test saving multiple different users."""
        user1 = create_test_user(id="U001", name="User One")
        user2 = create_test_user(id="U002", name="User Two")
        user3 = create_test_user(id="U003", name="User Three")

        await repository.save(user1)
        await repository.save(user2)
        await repository.save(user3)

        assert await repository.find_by_id("U001") is not None
        assert await repository.find_by_id("U002") is not None
        assert await repository.find_by_id("U003") is not None

    async def test_save_bot_user(self, repository: SQLiteUserRepository) -> None:
        """Test saving a bot user."""
        user = create_test_user(is_bot=True, name="myao")

        await repository.save(user)

        found = await repository.find_by_id(user.id)
        assert found is not None
        assert found.is_bot is True


class TestFindById:
    """find_by_id method tests."""

    async def test_find_existing_user(self, repository: SQLiteUserRepository) -> None:
        """Test finding existing user by ID."""
        user = create_test_user()
        await repository.save(user)

        found = await repository.find_by_id(user.id)

        assert found is not None
        assert found.id == user.id
        assert found.name == user.name

    async def test_find_nonexistent_user(
        self, repository: SQLiteUserRepository
    ) -> None:
        """Test finding nonexistent user returns None."""
        found = await repository.find_by_id("nonexistent")

        assert found is None
