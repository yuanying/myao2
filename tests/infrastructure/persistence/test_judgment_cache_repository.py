"""Tests for SQLiteJudgmentCacheRepository."""

from datetime import datetime, timedelta, timezone

import pytest

from myao2.domain.entities.judgment_cache import JudgmentCache
from myao2.infrastructure.persistence import DatabaseManager
from myao2.infrastructure.persistence.judgment_cache_repository import (
    SQLiteJudgmentCacheRepository,
)


@pytest.fixture
async def db_manager() -> DatabaseManager:
    """Create an in-memory database manager."""
    manager = DatabaseManager(":memory:")
    await manager.create_tables()
    return manager


@pytest.fixture
def repository(db_manager: DatabaseManager) -> SQLiteJudgmentCacheRepository:
    """Create a repository instance."""
    return SQLiteJudgmentCacheRepository(db_manager.get_session)


@pytest.fixture
def now() -> datetime:
    """Create a fixed current time for testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_cache(now: datetime) -> JudgmentCache:
    """Create a sample JudgmentCache instance."""
    return JudgmentCache(
        channel_id="C123",
        thread_ts="1234567890.123456",
        should_respond=False,
        confidence=0.85,
        reason="Not interesting",
        latest_message_ts="1234567890.999999",
        next_check_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def top_level_cache(now: datetime) -> JudgmentCache:
    """Create a sample JudgmentCache for top-level messages (no thread)."""
    return JudgmentCache(
        channel_id="C456",
        thread_ts=None,
        should_respond=True,
        confidence=0.95,
        reason="User needs help",
        latest_message_ts="9876543210.123456",
        next_check_at=now + timedelta(hours=12),
        created_at=now,
        updated_at=now,
    )


class TestSQLiteJudgmentCacheRepositorySave:
    """Tests for save method."""

    async def test_save_new_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
        sample_cache: JudgmentCache,
    ) -> None:
        """Test saving a new cache."""
        await repository.save(sample_cache)

        # Verify it was saved
        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )

        assert result is not None
        assert result.channel_id == sample_cache.channel_id
        assert result.thread_ts == sample_cache.thread_ts
        assert result.should_respond == sample_cache.should_respond
        assert result.confidence == sample_cache.confidence
        assert result.reason == sample_cache.reason
        assert result.latest_message_ts == sample_cache.latest_message_ts

    async def test_save_top_level_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
        top_level_cache: JudgmentCache,
    ) -> None:
        """Test saving a cache for top-level messages."""
        await repository.save(top_level_cache)

        result = await repository.find_by_scope(
            top_level_cache.channel_id,
            None,
        )

        assert result is not None
        assert result.thread_ts is None
        assert result.should_respond is True

    async def test_save_updates_existing_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
        sample_cache: JudgmentCache,
        now: datetime,
    ) -> None:
        """Test that saving updates an existing cache (upsert)."""
        # Save initial cache
        await repository.save(sample_cache)

        # Create updated cache with same scope
        updated_cache = JudgmentCache(
            channel_id=sample_cache.channel_id,
            thread_ts=sample_cache.thread_ts,
            should_respond=True,  # Changed
            confidence=0.95,  # Changed
            reason="Now interesting",  # Changed
            latest_message_ts="1234567891.000000",  # Changed
            next_check_at=now + timedelta(hours=2),  # Changed
            created_at=sample_cache.created_at,
            updated_at=now + timedelta(minutes=30),  # Changed
        )

        await repository.save(updated_cache)

        # Verify it was updated
        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )

        assert result is not None
        assert result.should_respond is True
        assert result.confidence == 0.95
        assert result.reason == "Now interesting"
        assert result.latest_message_ts == "1234567891.000000"


class TestSQLiteJudgmentCacheRepositoryFindByScope:
    """Tests for find_by_scope method."""

    async def test_find_existing_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
        sample_cache: JudgmentCache,
    ) -> None:
        """Test finding an existing cache."""
        await repository.save(sample_cache)

        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )

        assert result is not None
        assert result.channel_id == sample_cache.channel_id

    async def test_find_nonexistent_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
    ) -> None:
        """Test finding a nonexistent cache returns None."""
        result = await repository.find_by_scope("C999", "nonexistent")

        assert result is None

    async def test_find_top_level_cache(
        self,
        repository: SQLiteJudgmentCacheRepository,
        top_level_cache: JudgmentCache,
    ) -> None:
        """Test finding a top-level cache (thread_ts is None)."""
        await repository.save(top_level_cache)

        result = await repository.find_by_scope(
            top_level_cache.channel_id,
            None,
        )

        assert result is not None
        assert result.thread_ts is None

    async def test_find_distinguishes_thread_and_top_level(
        self,
        repository: SQLiteJudgmentCacheRepository,
        now: datetime,
    ) -> None:
        """Test that thread and top-level caches are distinguished."""
        # Create a thread cache
        thread_cache = JudgmentCache(
            channel_id="C123",
            thread_ts="1234567890.123456",
            should_respond=False,
            confidence=0.5,
            reason="Thread cache",
            latest_message_ts="msg1",
            next_check_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )

        # Create a top-level cache for the same channel
        top_cache = JudgmentCache(
            channel_id="C123",
            thread_ts=None,
            should_respond=True,
            confidence=0.9,
            reason="Top-level cache",
            latest_message_ts="msg2",
            next_check_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )

        await repository.save(thread_cache)
        await repository.save(top_cache)

        # Find thread cache
        thread_result = await repository.find_by_scope("C123", "1234567890.123456")
        assert thread_result is not None
        assert thread_result.reason == "Thread cache"

        # Find top-level cache
        top_result = await repository.find_by_scope("C123", None)
        assert top_result is not None
        assert top_result.reason == "Top-level cache"


class TestSQLiteJudgmentCacheRepositoryDeleteExpired:
    """Tests for delete_expired method."""

    async def test_delete_expired_caches(
        self,
        repository: SQLiteJudgmentCacheRepository,
        now: datetime,
    ) -> None:
        """Test deleting expired caches."""
        # Create an expired cache
        expired_cache = JudgmentCache(
            channel_id="C111",
            thread_ts=None,
            should_respond=False,
            confidence=0.8,
            reason="Expired",
            latest_message_ts="msg1",
            next_check_at=now - timedelta(hours=1),  # Already expired
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )

        # Create a valid cache
        valid_cache = JudgmentCache(
            channel_id="C222",
            thread_ts=None,
            should_respond=True,
            confidence=0.9,
            reason="Valid",
            latest_message_ts="msg2",
            next_check_at=now + timedelta(hours=1),  # Still valid
            created_at=now,
            updated_at=now,
        )

        await repository.save(expired_cache)
        await repository.save(valid_cache)

        # Delete expired (before current time)
        deleted_count = await repository.delete_expired(now)

        assert deleted_count == 1

        # Verify expired cache is gone
        expired_result = await repository.find_by_scope("C111", None)
        assert expired_result is None

        # Verify valid cache still exists
        valid_result = await repository.find_by_scope("C222", None)
        assert valid_result is not None

    async def test_delete_expired_no_expired_caches(
        self,
        repository: SQLiteJudgmentCacheRepository,
        sample_cache: JudgmentCache,
        now: datetime,
    ) -> None:
        """Test delete_expired when no caches are expired."""
        await repository.save(sample_cache)

        # Try to delete before the cache expires
        deleted_count = await repository.delete_expired(now)

        assert deleted_count == 0

        # Verify cache still exists
        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )
        assert result is not None


class TestSQLiteJudgmentCacheRepositoryDeleteByScope:
    """Tests for delete_by_scope method."""

    async def test_delete_by_scope(
        self,
        repository: SQLiteJudgmentCacheRepository,
        sample_cache: JudgmentCache,
    ) -> None:
        """Test deleting a cache by scope."""
        await repository.save(sample_cache)

        # Verify it exists
        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )
        assert result is not None

        # Delete it
        await repository.delete_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )

        # Verify it's gone
        result = await repository.find_by_scope(
            sample_cache.channel_id,
            sample_cache.thread_ts,
        )
        assert result is None

    async def test_delete_by_scope_nonexistent(
        self,
        repository: SQLiteJudgmentCacheRepository,
    ) -> None:
        """Test deleting a nonexistent cache (should not raise)."""
        # This should not raise
        await repository.delete_by_scope("C999", "nonexistent")
