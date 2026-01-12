"""Tests for memo name migration."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from myao2.infrastructure.persistence.migrations.memo_name_migration import (
    migrate_memo_add_name,
)


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite async engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()


async def create_old_memos_table(engine: AsyncEngine) -> None:
    """Create the old memos table without name column."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE memos (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    tags JSON,
                    detail TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
        )


async def insert_old_memo(
    engine: AsyncEngine,
    memo_id: str,
    content: str = "Test",
    priority: int = 3,
) -> None:
    """Insert a memo into the old table."""
    now = datetime.now(timezone.utc).isoformat()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO memos (id, content, priority, tags, detail, created_at, updated_at)
                VALUES (:id, :content, :priority, '[]', NULL, :now, :now)
            """),
            {"id": memo_id, "content": content, "priority": priority, "now": now},
        )


class TestMigrateMemoAddName:
    """migrate_memo_add_name function tests."""

    async def test_migration_on_empty_table(self, engine: AsyncEngine) -> None:
        """Test migration creates table structure with no data."""
        await create_old_memos_table(engine)

        await migrate_memo_add_name(engine)

        # Verify table has name column
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA table_info(memos)"))
            columns = {row[1] for row in result.fetchall()}

        assert "name" in columns
        assert "id" in columns

    async def test_migration_with_single_memo(self, engine: AsyncEngine) -> None:
        """Test migration assigns name from id[:8]."""
        await create_old_memos_table(engine)
        memo_id = str(uuid4())
        await insert_old_memo(engine, memo_id, "Test content")

        await migrate_memo_add_name(engine)

        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT id, name, content FROM memos WHERE id = :id"),
                {"id": memo_id},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == memo_id
        assert row[1] == memo_id[:8]
        assert row[2] == "Test content"

    async def test_migration_with_duplicate_prefixes(self, engine: AsyncEngine) -> None:
        """Test migration handles duplicate id prefixes with suffix."""
        await create_old_memos_table(engine)

        # Create two memos with same first 8 characters
        prefix = "12345678"
        memo_id1 = prefix + "-aaaa-bbbb-cccc-dddddddddddd"
        memo_id2 = prefix + "-eeee-ffff-gggg-hhhhhhhhhhhh"

        await insert_old_memo(engine, memo_id1, "First memo")
        await insert_old_memo(engine, memo_id2, "Second memo")

        await migrate_memo_add_name(engine)

        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM memos ORDER BY name"))
            names = [row[0] for row in result.fetchall()]

        # One should be "12345678", other should be "12345678-2"
        assert len(names) == 2
        assert prefix in names
        assert f"{prefix}-2" in names

    async def test_migration_skips_if_name_exists(self, engine: AsyncEngine) -> None:
        """Test migration is skipped if name column already exists."""
        # Create table with name column already
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    CREATE TABLE memos (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        content TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        tags JSON,
                        detail TEXT,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                """)
            )
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                text("""
                    INSERT INTO memos
                        (id, name, content, priority, tags, detail,
                         created_at, updated_at)
                    VALUES
                        ('test-id', 'existing-name', 'Test', 3, '[]', NULL,
                         :now, :now)
                """),
                {"now": now},
            )

        await migrate_memo_add_name(engine)

        # Verify original name is preserved
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM memos WHERE id = 'test-id'"))
            row = result.fetchone()

        assert row is not None
        assert row[0] == "existing-name"

    async def test_migration_skips_if_table_not_exists(self, engine: AsyncEngine) -> None:
        """Test migration does nothing if memos table doesn't exist."""
        # Don't create table
        await migrate_memo_add_name(engine)

        # Verify no table was created
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='memos'")
            )
            assert result.fetchone() is None

    async def test_migration_preserves_all_data(self, engine: AsyncEngine) -> None:
        """Test migration preserves all memo data."""
        await create_old_memos_table(engine)

        memo_id = str(uuid4())
        now = datetime.now(timezone.utc)
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO memos (id, content, priority, tags, detail, created_at, updated_at)
                    VALUES (:id, :content, :priority, :tags, :detail, :created_at, :updated_at)
                """),
                {
                    "id": memo_id,
                    "content": "Important memo",
                    "priority": 5,
                    "tags": '["user", "schedule"]',
                    "detail": "Detailed info",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                },
            )

        await migrate_memo_add_name(engine)

        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT * FROM memos WHERE id = :id"), {"id": memo_id}
            )
            row = result.fetchone()

        assert row is not None
        # id, name, content, priority, tags, detail, created_at, updated_at
        assert row[0] == memo_id
        assert row[1] == memo_id[:8]
        assert row[2] == "Important memo"
        assert row[3] == 5
        assert row[4] == '["user", "schedule"]'
        assert row[5] == "Detailed info"
