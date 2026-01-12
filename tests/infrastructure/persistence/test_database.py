"""Tests for DatabaseManager."""

from pathlib import Path

from sqlalchemy import inspect

from myao2.infrastructure.persistence import DatabaseManager


class TestDatabaseManager:
    """DatabaseManager tests."""

    def test_get_engine_with_valid_path(self, tmp_path: Path) -> None:
        """Test engine creation with valid path."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))

        engine = manager.get_engine()

        assert engine is not None
        assert "sqlite" in str(engine.url)

    def test_get_engine_creates_parent_directory(self, tmp_path: Path) -> None:
        """Test that parent directory is created if not exists."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        manager = DatabaseManager(str(db_path))

        manager.get_engine()

        assert db_path.parent.exists()

    async def test_create_tables_first_time(self, tmp_path: Path) -> None:
        """Test table creation on first run."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        engine = manager.get_engine()
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        assert "messages" in tables

    async def test_create_tables_already_exists(self, tmp_path: Path) -> None:
        """Test table creation when tables already exist."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))

        # Should not raise error on second call
        await manager.create_tables()
        await manager.create_tables()

        engine = manager.get_engine()
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        assert "messages" in tables

    async def test_get_session(self, tmp_path: Path) -> None:
        """Test session creation."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        async with manager.get_session() as session:
            assert session is not None

    async def test_in_memory_database(self) -> None:
        """Test in-memory database."""
        manager = DatabaseManager(":memory:")
        await manager.create_tables()

        engine = manager.get_engine()
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        assert "messages" in tables

    async def test_messages_table_has_correct_columns(self, tmp_path: Path) -> None:
        """Test that messages table has correct columns."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        engine = manager.get_engine()
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {
                    col["name"] for col in inspect(sync_conn).get_columns("messages")
                }
            )

        expected_columns = {
            "id",
            "message_id",
            "channel_id",
            "user_id",
            "user_name",
            "user_is_bot",
            "text",
            "timestamp",
            "thread_ts",
            "mentions",
            "created_at",
        }
        assert columns == expected_columns

    async def test_messages_table_has_unique_constraint(self, tmp_path: Path) -> None:
        """Test that messages table has unique constraint."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        engine = manager.get_engine()
        async with engine.connect() as conn:
            unique_constraints = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_unique_constraints("messages")
            )

        constraint_names = [c["name"] for c in unique_constraints]
        assert "uq_message_channel" in constraint_names

    async def test_close_disposes_engine(self, tmp_path: Path) -> None:
        """Test that close disposes engine and clears references."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        # Engine should be initialized
        assert manager._engine is not None
        assert manager._session_factory is not None

        await manager.close()

        # After close, references should be cleared
        assert manager._engine is None
        assert manager._session_factory is None

    async def test_close_without_engine(self) -> None:
        """Test that close does nothing if engine was never created."""
        manager = DatabaseManager(":memory:")

        # Engine not created yet
        assert manager._engine is None

        # Should not raise
        await manager.close()

        assert manager._engine is None


class TestDatabaseManagerIsHealthy:
    """Tests for is_healthy method."""

    async def test_is_healthy_returns_true_when_connected(self, tmp_path: Path) -> None:
        """Test that is_healthy returns True when database is accessible."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        result = await manager.is_healthy()

        assert result is True

    async def test_is_healthy_returns_true_for_in_memory_db(self) -> None:
        """Test that is_healthy returns True for in-memory database."""
        manager = DatabaseManager(":memory:")
        await manager.create_tables()

        result = await manager.is_healthy()

        assert result is True

    async def test_is_healthy_returns_false_when_engine_is_none(self) -> None:
        """Test that is_healthy returns False when engine is not initialized."""
        manager = DatabaseManager(":memory:")
        # Don't call create_tables - engine is None

        result = await manager.is_healthy()

        assert result is False

    async def test_is_healthy_returns_false_after_close(self, tmp_path: Path) -> None:
        """Test that is_healthy returns False after close() is called."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        await manager.create_tables()

        # Should be healthy before close
        assert await manager.is_healthy() is True

        await manager.close()

        # Should not be healthy after close
        assert await manager.is_healthy() is False
