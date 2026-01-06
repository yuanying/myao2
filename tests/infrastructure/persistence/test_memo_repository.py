"""Tests for SQLiteMemoRepository."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities.memo import Memo
from myao2.infrastructure.persistence.memo_repository import SQLiteMemoRepository


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
def repository(session_factory) -> SQLiteMemoRepository:
    """Create test repository."""
    return SQLiteMemoRepository(session_factory)


def create_test_memo(
    id: UUID | None = None,
    content: str = "Test memo content",
    priority: int = 3,
    tags: list[str] | None = None,
    detail: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Memo:
    """Create a test Memo entity."""
    now = datetime.now(timezone.utc)
    return Memo(
        id=id or uuid4(),
        content=content,
        priority=priority,
        tags=tags or [],
        detail=detail,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


class TestSave:
    """save method tests."""

    async def test_save_new_memo(self, repository: SQLiteMemoRepository) -> None:
        """Test saving a new memo."""
        memo = create_test_memo()

        await repository.save(memo)

        found = await repository.find_by_id(memo.id)
        assert found is not None
        assert found.id == memo.id
        assert found.content == memo.content
        assert found.priority == memo.priority

    async def test_save_updates_existing_memo(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test that save updates existing memo with same ID (upsert)."""
        memo_id = uuid4()
        original = create_test_memo(id=memo_id, content="Original", priority=3)
        await repository.save(original)

        # Update memo
        now = datetime.now(timezone.utc)
        updated = Memo(
            id=memo_id,
            content="Updated content",
            priority=5,
            tags=["updated"],
            detail="New detail",
            created_at=original.created_at,
            updated_at=now,
        )
        await repository.save(updated)

        found = await repository.find_by_id(memo_id)
        assert found is not None
        assert found.content == "Updated content"
        assert found.priority == 5
        assert found.tags == ["updated"]
        assert found.detail == "New detail"


class TestFindById:
    """find_by_id method tests."""

    async def test_find_existing_memo(self, repository: SQLiteMemoRepository) -> None:
        """Test finding existing memo by ID."""
        memo = create_test_memo()
        await repository.save(memo)

        found = await repository.find_by_id(memo.id)

        assert found is not None
        assert found.id == memo.id
        assert found.content == memo.content

    async def test_find_nonexistent_memo(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test finding nonexistent memo returns None."""
        found = await repository.find_by_id(uuid4())

        assert found is None


class TestFindAll:
    """find_all method tests."""

    async def test_find_all_empty(self, repository: SQLiteMemoRepository) -> None:
        """Test find_all on empty database."""
        result = await repository.find_all()

        assert result == []

    async def test_find_all_multiple_sorted(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test find_all returns memos sorted by priority desc, then updated_at desc."""
        base_time = datetime.now(timezone.utc)

        # Create memos with different priorities and times
        memo1 = create_test_memo(
            content="Priority 3 older",
            priority=3,
            updated_at=base_time - timedelta(hours=1),
        )
        memo2 = create_test_memo(
            content="Priority 5",
            priority=5,
            updated_at=base_time,
        )
        memo3 = create_test_memo(
            content="Priority 3 newer",
            priority=3,
            updated_at=base_time,
        )

        await repository.save(memo1)
        await repository.save(memo2)
        await repository.save(memo3)

        result = await repository.find_all()

        assert len(result) == 3
        # Priority 5 first
        assert result[0].content == "Priority 5"
        # Priority 3 newer second
        assert result[1].content == "Priority 3 newer"
        # Priority 3 older last
        assert result[2].content == "Priority 3 older"

    async def test_find_all_with_offset_limit(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test find_all with offset and limit."""
        for i in range(5):
            await repository.save(create_test_memo(content=f"Memo {i}", priority=5 - i))

        # Get 2 memos starting from offset 1
        result = await repository.find_all(offset=1, limit=2)

        assert len(result) == 2


class TestFindByPriorityGte:
    """find_by_priority_gte method tests."""

    async def test_find_by_priority_gte(self, repository: SQLiteMemoRepository) -> None:
        """Test finding memos with priority >= min_priority."""
        memo1 = create_test_memo(content="Priority 2", priority=2)
        memo2 = create_test_memo(content="Priority 4", priority=4)
        memo3 = create_test_memo(content="Priority 5", priority=5)
        memo4 = create_test_memo(content="Priority 3", priority=3)

        await repository.save(memo1)
        await repository.save(memo2)
        await repository.save(memo3)
        await repository.save(memo4)

        # Get memos with priority >= 4
        result = await repository.find_by_priority_gte(4)

        assert len(result) == 2
        assert all(m.priority >= 4 for m in result)
        # Sorted by priority desc
        assert result[0].priority == 5
        assert result[1].priority == 4

    async def test_find_by_priority_gte_with_limit(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test find_by_priority_gte respects limit."""
        for i in range(10):
            await repository.save(create_test_memo(content=f"Memo {i}", priority=5))

        result = await repository.find_by_priority_gte(4, limit=3)

        assert len(result) == 3


class TestFindRecent:
    """find_recent method tests."""

    async def test_find_recent(self, repository: SQLiteMemoRepository) -> None:
        """Test finding recent memos sorted by updated_at desc."""
        base_time = datetime.now(timezone.utc)

        for i in range(5):
            await repository.save(
                create_test_memo(
                    content=f"Memo {i}",
                    priority=3,
                    updated_at=base_time + timedelta(minutes=i),
                )
            )

        result = await repository.find_recent(limit=3)

        assert len(result) == 3
        # Most recent first (Memo 4, 3, 2)
        assert result[0].content == "Memo 4"
        assert result[1].content == "Memo 3"
        assert result[2].content == "Memo 2"


class TestFindByTag:
    """find_by_tag method tests."""

    async def test_find_by_tag(self, repository: SQLiteMemoRepository) -> None:
        """Test finding memos by tag."""
        memo1 = create_test_memo(content="Has target tag", tags=["user", "schedule"])
        memo2 = create_test_memo(content="No target tag", tags=["other"])
        memo3 = create_test_memo(content="Also has target tag", tags=["user"])

        await repository.save(memo1)
        await repository.save(memo2)
        await repository.save(memo3)

        result = await repository.find_by_tag("user")

        assert len(result) == 2
        assert all("user" in m.tags for m in result)

    async def test_find_by_tag_no_match(self, repository: SQLiteMemoRepository) -> None:
        """Test find_by_tag returns empty when no match."""
        await repository.save(create_test_memo(tags=["other"]))

        result = await repository.find_by_tag("nonexistent")

        assert result == []

    async def test_find_by_tag_with_offset_limit(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test find_by_tag with offset and limit."""
        for i in range(5):
            await repository.save(
                create_test_memo(content=f"Memo {i}", tags=["common"], priority=5 - i)
            )

        result = await repository.find_by_tag("common", offset=1, limit=2)

        assert len(result) == 2


class TestGetAllTagsWithStats:
    """get_all_tags_with_stats method tests."""

    async def test_get_all_tags_with_stats(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test getting tag statistics."""
        base_time = datetime.now(timezone.utc)

        await repository.save(
            create_test_memo(
                tags=["user", "schedule"], updated_at=base_time - timedelta(hours=1)
            )
        )
        await repository.save(create_test_memo(tags=["user"], updated_at=base_time))
        await repository.save(
            create_test_memo(tags=["preference"], updated_at=base_time)
        )

        result = await repository.get_all_tags_with_stats()

        assert len(result) == 3
        # Sorted by count desc
        user_tag = next(t for t in result if t.tag == "user")
        assert user_tag.count == 2

        schedule_tag = next(t for t in result if t.tag == "schedule")
        assert schedule_tag.count == 1

    async def test_get_all_tags_with_stats_empty(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test get_all_tags_with_stats on empty database."""
        result = await repository.get_all_tags_with_stats()

        assert result == []


class TestDelete:
    """delete method tests."""

    async def test_delete_existing_memo(self, repository: SQLiteMemoRepository) -> None:
        """Test deleting an existing memo."""
        memo = create_test_memo()
        await repository.save(memo)

        result = await repository.delete(memo.id)

        assert result is True
        found = await repository.find_by_id(memo.id)
        assert found is None

    async def test_delete_nonexistent_memo(
        self, repository: SQLiteMemoRepository
    ) -> None:
        """Test deleting a nonexistent memo returns False."""
        result = await repository.delete(uuid4())

        assert result is False


class TestCount:
    """count method tests."""

    async def test_count_all(self, repository: SQLiteMemoRepository) -> None:
        """Test counting all memos."""
        for i in range(5):
            await repository.save(create_test_memo(content=f"Memo {i}"))

        result = await repository.count()

        assert result == 5

    async def test_count_by_tag(self, repository: SQLiteMemoRepository) -> None:
        """Test counting memos with specific tag."""
        await repository.save(create_test_memo(tags=["user"]))
        await repository.save(create_test_memo(tags=["user", "schedule"]))
        await repository.save(create_test_memo(tags=["other"]))

        result = await repository.count(tag="user")

        assert result == 2

    async def test_count_empty(self, repository: SQLiteMemoRepository) -> None:
        """Test count on empty database."""
        result = await repository.count()

        assert result == 0
