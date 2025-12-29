"""Tests for SQLiteMemoryRepository."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities.memory import Memory, MemoryScope, MemoryType
from myao2.infrastructure.persistence import DatabaseManager
from myao2.infrastructure.persistence.memory_repository import (
    SQLiteMemoryRepository,
)


@pytest.fixture
async def db_manager() -> DatabaseManager:
    """Create an in-memory database manager."""
    manager = DatabaseManager(":memory:")
    await manager.create_tables()
    return manager


@pytest.fixture
def repository(db_manager: DatabaseManager) -> SQLiteMemoryRepository:
    """Create a repository instance."""
    return SQLiteMemoryRepository(db_manager.get_session)


@pytest.fixture
def now() -> datetime:
    """Create a fixed current time for testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def channel_long_term_memory(now: datetime) -> Memory:
    """Create a sample channel long-term memory."""
    return Memory(
        scope=MemoryScope.CHANNEL,
        scope_id="C1234567890",
        memory_type=MemoryType.LONG_TERM,
        content="Channel long-term memory content",
        created_at=now,
        updated_at=now,
        source_message_count=10,
        source_latest_message_ts="1234567890.123456",
    )


@pytest.fixture
def channel_short_term_memory(now: datetime) -> Memory:
    """Create a sample channel short-term memory."""
    return Memory(
        scope=MemoryScope.CHANNEL,
        scope_id="C1234567890",
        memory_type=MemoryType.SHORT_TERM,
        content="Channel short-term memory content",
        created_at=now,
        updated_at=now,
        source_message_count=5,
        source_latest_message_ts="1234567890.654321",
    )


@pytest.fixture
def workspace_memory(now: datetime) -> Memory:
    """Create a sample workspace memory."""
    return Memory(
        scope=MemoryScope.WORKSPACE,
        scope_id="default",
        memory_type=MemoryType.LONG_TERM,
        content="Workspace long-term memory content",
        created_at=now,
        updated_at=now,
        source_message_count=100,
        source_latest_message_ts="9876543210.123456",
    )


@pytest.fixture
def thread_memory(now: datetime) -> Memory:
    """Create a sample thread short-term memory."""
    return Memory(
        scope=MemoryScope.THREAD,
        scope_id="C1234567890:1234567890.123456",
        memory_type=MemoryType.SHORT_TERM,
        content="Thread short-term memory content",
        created_at=now,
        updated_at=now,
        source_message_count=3,
    )


class TestSQLiteMemoryRepositorySave:
    """Tests for save method."""

    async def test_save_new_memory(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
    ) -> None:
        """Test saving a new memory."""
        await repository.save(channel_long_term_memory)

        result = await repository.find_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )

        assert result is not None
        assert result.scope == channel_long_term_memory.scope
        assert result.scope_id == channel_long_term_memory.scope_id
        assert result.memory_type == channel_long_term_memory.memory_type
        assert result.content == channel_long_term_memory.content
        assert (
            result.source_message_count == channel_long_term_memory.source_message_count
        )
        assert (
            result.source_latest_message_ts
            == channel_long_term_memory.source_latest_message_ts
        )

    async def test_save_updates_existing_memory(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        now: datetime,
    ) -> None:
        """Test that saving updates an existing memory (upsert)."""
        await repository.save(channel_long_term_memory)

        updated_memory = Memory(
            scope=channel_long_term_memory.scope,
            scope_id=channel_long_term_memory.scope_id,
            memory_type=channel_long_term_memory.memory_type,
            content="Updated content",
            created_at=channel_long_term_memory.created_at,
            updated_at=datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc),
            source_message_count=20,
            source_latest_message_ts="1234567891.000000",
        )

        await repository.save(updated_memory)

        result = await repository.find_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )

        assert result is not None
        assert result.content == "Updated content"
        assert result.source_message_count == 20
        assert result.source_latest_message_ts == "1234567891.000000"

    async def test_save_upsert_keeps_single_record(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        now: datetime,
    ) -> None:
        """Test that upsert keeps only one record per scope/type."""
        await repository.save(channel_long_term_memory)

        updated_memory = Memory(
            scope=channel_long_term_memory.scope,
            scope_id=channel_long_term_memory.scope_id,
            memory_type=channel_long_term_memory.memory_type,
            content="Updated again",
            created_at=channel_long_term_memory.created_at,
            updated_at=datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            source_message_count=30,
        )

        await repository.save(updated_memory)
        await repository.save(updated_memory)

        memories = await repository.find_all_by_scope(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
        )

        assert len(memories) == 1

    async def test_save_workspace_memory(
        self,
        repository: SQLiteMemoryRepository,
        workspace_memory: Memory,
    ) -> None:
        """Test saving a workspace memory."""
        await repository.save(workspace_memory)

        result = await repository.find_by_scope_and_type(
            MemoryScope.WORKSPACE,
            "default",
            MemoryType.LONG_TERM,
        )

        assert result is not None
        assert result.scope == MemoryScope.WORKSPACE

    async def test_save_thread_memory(
        self,
        repository: SQLiteMemoryRepository,
        thread_memory: Memory,
    ) -> None:
        """Test saving a thread memory."""
        await repository.save(thread_memory)

        result = await repository.find_by_scope_and_type(
            MemoryScope.THREAD,
            "C1234567890:1234567890.123456",
            MemoryType.SHORT_TERM,
        )

        assert result is not None
        assert result.scope == MemoryScope.THREAD
        assert result.source_latest_message_ts is None


class TestSQLiteMemoryRepositoryFindByScopeAndType:
    """Tests for find_by_scope_and_type method."""

    async def test_find_existing_memory(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
    ) -> None:
        """Test finding an existing memory."""
        await repository.save(channel_long_term_memory)

        result = await repository.find_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )

        assert result is not None
        assert result.content == channel_long_term_memory.content

    async def test_find_nonexistent_memory(
        self,
        repository: SQLiteMemoryRepository,
    ) -> None:
        """Test finding a nonexistent memory returns None."""
        result = await repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C_nonexistent",
            MemoryType.LONG_TERM,
        )

        assert result is None

    async def test_find_distinguishes_memory_types(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        channel_short_term_memory: Memory,
    ) -> None:
        """Test that different memory types are distinguished."""
        await repository.save(channel_long_term_memory)
        await repository.save(channel_short_term_memory)

        long_term = await repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C1234567890",
            MemoryType.LONG_TERM,
        )
        short_term = await repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C1234567890",
            MemoryType.SHORT_TERM,
        )

        assert long_term is not None
        assert short_term is not None
        assert long_term.content == "Channel long-term memory content"
        assert short_term.content == "Channel short-term memory content"


class TestSQLiteMemoryRepositoryFindAllByScope:
    """Tests for find_all_by_scope method."""

    async def test_find_multiple_memories(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        channel_short_term_memory: Memory,
    ) -> None:
        """Test finding multiple memories with same scope."""
        await repository.save(channel_long_term_memory)
        await repository.save(channel_short_term_memory)

        memories = await repository.find_all_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )

        assert len(memories) == 2
        memory_types = {m.memory_type for m in memories}
        assert memory_types == {MemoryType.LONG_TERM, MemoryType.SHORT_TERM}

    async def test_find_empty_list_when_no_memories(
        self,
        repository: SQLiteMemoryRepository,
    ) -> None:
        """Test finding memories returns empty list when none exist."""
        memories = await repository.find_all_by_scope(
            MemoryScope.CHANNEL,
            "C_nonexistent",
        )

        assert memories == []

    async def test_find_does_not_include_other_scopes(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        workspace_memory: Memory,
    ) -> None:
        """Test that find_all_by_scope does not include other scopes."""
        await repository.save(channel_long_term_memory)
        await repository.save(workspace_memory)

        channel_memories = await repository.find_all_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )

        assert len(channel_memories) == 1
        assert channel_memories[0].scope == MemoryScope.CHANNEL


class TestSQLiteMemoryRepositoryDeleteByScopeAndType:
    """Tests for delete_by_scope_and_type method."""

    async def test_delete_existing_memory(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
    ) -> None:
        """Test deleting an existing memory."""
        await repository.save(channel_long_term_memory)

        result = await repository.find_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )
        assert result is not None

        await repository.delete_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )

        result = await repository.find_by_scope_and_type(
            channel_long_term_memory.scope,
            channel_long_term_memory.scope_id,
            channel_long_term_memory.memory_type,
        )
        assert result is None

    async def test_delete_nonexistent_memory_does_not_raise(
        self,
        repository: SQLiteMemoryRepository,
    ) -> None:
        """Test deleting a nonexistent memory does not raise."""
        await repository.delete_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C_nonexistent",
            MemoryType.LONG_TERM,
        )

    async def test_delete_only_deletes_specified_type(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        channel_short_term_memory: Memory,
    ) -> None:
        """Test that delete only removes the specified memory type."""
        await repository.save(channel_long_term_memory)
        await repository.save(channel_short_term_memory)

        await repository.delete_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C1234567890",
            MemoryType.LONG_TERM,
        )

        long_term = await repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C1234567890",
            MemoryType.LONG_TERM,
        )
        short_term = await repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            "C1234567890",
            MemoryType.SHORT_TERM,
        )

        assert long_term is None
        assert short_term is not None


class TestSQLiteMemoryRepositoryDeleteByScope:
    """Tests for delete_by_scope method."""

    async def test_delete_all_memories_in_scope(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        channel_short_term_memory: Memory,
    ) -> None:
        """Test deleting all memories in a scope."""
        await repository.save(channel_long_term_memory)
        await repository.save(channel_short_term_memory)

        memories = await repository.find_all_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )
        assert len(memories) == 2

        await repository.delete_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )

        memories = await repository.find_all_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )
        assert len(memories) == 0

    async def test_delete_does_not_affect_other_scopes(
        self,
        repository: SQLiteMemoryRepository,
        channel_long_term_memory: Memory,
        workspace_memory: Memory,
    ) -> None:
        """Test that delete_by_scope does not affect other scopes."""
        await repository.save(channel_long_term_memory)
        await repository.save(workspace_memory)

        await repository.delete_by_scope(
            MemoryScope.CHANNEL,
            "C1234567890",
        )

        workspace_result = await repository.find_by_scope_and_type(
            MemoryScope.WORKSPACE,
            "default",
            MemoryType.LONG_TERM,
        )
        assert workspace_result is not None

    async def test_delete_empty_scope_does_not_raise(
        self,
        repository: SQLiteMemoryRepository,
    ) -> None:
        """Test deleting an empty scope does not raise."""
        await repository.delete_by_scope(
            MemoryScope.CHANNEL,
            "C_nonexistent",
        )
