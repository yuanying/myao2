"""Tests for DatabaseManager."""

from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session

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

    def test_create_tables_first_time(self, tmp_path: Path) -> None:
        """Test table creation on first run."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()

        engine = manager.get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "messages" in tables

    def test_create_tables_already_exists(self, tmp_path: Path) -> None:
        """Test table creation when tables already exist."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))

        # Should not raise error on second call
        manager.create_tables()
        manager.create_tables()

        engine = manager.get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "messages" in tables

    def test_get_session(self, tmp_path: Path) -> None:
        """Test session creation."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()

        session = manager.get_session()

        assert isinstance(session, Session)
        session.close()

    def test_in_memory_database(self) -> None:
        """Test in-memory database."""
        manager = DatabaseManager(":memory:")
        manager.create_tables()

        engine = manager.get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "messages" in tables

    def test_messages_table_has_correct_columns(self, tmp_path: Path) -> None:
        """Test that messages table has correct columns."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()

        engine = manager.get_engine()
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("messages")}

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

    def test_messages_table_has_unique_constraint(self, tmp_path: Path) -> None:
        """Test that messages table has unique constraint."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()

        engine = manager.get_engine()
        inspector = inspect(engine)
        unique_constraints = inspector.get_unique_constraints("messages")

        constraint_names = [c["name"] for c in unique_constraints]
        assert "uq_message_channel" in constraint_names
