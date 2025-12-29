"""Tests for SQLiteMessageRepository."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel, Message, User
from myao2.infrastructure.persistence import SQLiteMessageRepository
from myao2.infrastructure.persistence.models import MessageModel


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
def repository(session_factory) -> SQLiteMessageRepository:
    """Create test repository."""
    return SQLiteMessageRepository(session_factory)


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


class TestSave:
    """save method tests."""

    async def test_save_new_message(self, repository: SQLiteMessageRepository) -> None:
        """Test saving a new message."""
        message = create_test_message()

        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is not None
        assert found.id == message.id
        assert found.text == message.text
        assert found.user.id == message.user.id

    async def test_save_updates_existing_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that save updates existing message with same ID."""
        message = create_test_message(text="Original text")
        await repository.save(message)

        # Update message text
        updated_message = create_test_message(text="Updated text")
        await repository.save(updated_message)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is not None
        assert found.text == "Updated text"

    async def test_save_multiple_messages(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test saving multiple different messages."""
        message1 = create_test_message(id="1.001", text="First message")
        message2 = create_test_message(id="1.002", text="Second message")
        message3 = create_test_message(id="1.003", text="Third message")

        await repository.save(message1)
        await repository.save(message2)
        await repository.save(message3)

        assert await repository.find_by_id("1.001", "C123456") is not None
        assert await repository.find_by_id("1.002", "C123456") is not None
        assert await repository.find_by_id("1.003", "C123456") is not None

    async def test_save_with_mentions(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test saving message with mentions."""
        message = create_test_message(mentions=["U111", "U222", "U333"])

        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is not None
        assert found.mentions == ["U111", "U222", "U333"]

    async def test_save_thread_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test saving a thread message."""
        message = create_test_message(thread_ts="1234567890.000000")

        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is not None
        assert found.thread_ts == "1234567890.000000"

    async def test_save_bot_message(self, repository: SQLiteMessageRepository) -> None:
        """Test saving a bot message."""
        message = create_test_message(is_bot=True, user_name="myao")

        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is not None
        assert found.user.is_bot is True


class TestFindByChannel:
    """find_by_channel method tests."""

    async def test_find_multiple_messages_newest_first(
        self, repository: SQLiteMessageRepository
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
            await repository.save(msg)

        result = await repository.find_by_channel("C123456")

        assert len(result) == 5
        # Newest first
        assert result[0].id == "1.004"
        assert result[4].id == "1.000"

    async def test_find_with_limit(self, repository: SQLiteMessageRepository) -> None:
        """Test limit parameter."""
        for i in range(10):
            await repository.save(create_test_message(id=f"1.{i:03d}"))

        result = await repository.find_by_channel("C123456", limit=3)

        assert len(result) == 3

    async def test_find_excludes_thread_messages(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that thread messages are excluded."""
        # Channel message
        channel_msg = create_test_message(id="1.001", thread_ts=None)
        # Thread messages
        thread_msg1 = create_test_message(id="1.002", thread_ts="1.000")
        thread_msg2 = create_test_message(id="1.003", thread_ts="1.000")

        await repository.save(channel_msg)
        await repository.save(thread_msg1)
        await repository.save(thread_msg2)

        result = await repository.find_by_channel("C123456")

        assert len(result) == 1
        assert result[0].id == "1.001"

    async def test_find_empty_channel(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test finding in empty channel."""
        result = await repository.find_by_channel("C999999")

        assert result == []

    async def test_find_excludes_other_channels(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that messages from other channels are excluded."""
        msg_c1 = create_test_message(id="1.001", channel_id="C111111")
        msg_c2 = create_test_message(id="1.002", channel_id="C222222")

        await repository.save(msg_c1)
        await repository.save(msg_c2)

        result = await repository.find_by_channel("C111111")

        assert len(result) == 1
        assert result[0].channel.id == "C111111"


class TestFindByThread:
    """find_by_thread method tests."""

    async def test_find_thread_messages_newest_first(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that thread messages are returned newest first."""
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
            await repository.save(msg)

        result = await repository.find_by_thread("C123456", thread_ts)

        assert len(result) == 3
        assert result[0].id == "1.002"
        assert result[2].id == "1.000"

    async def test_find_thread_with_limit(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test limit parameter for thread."""
        thread_ts = "1.000"
        for i in range(5):
            await repository.save(
                create_test_message(id=f"1.{i:03d}", thread_ts=thread_ts)
            )

        result = await repository.find_by_thread("C123456", thread_ts, limit=2)

        assert len(result) == 2

    async def test_find_excludes_other_threads(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that messages from other threads are excluded."""
        msg1 = create_test_message(id="1.001", thread_ts="thread_a")
        msg2 = create_test_message(id="1.002", thread_ts="thread_b")

        await repository.save(msg1)
        await repository.save(msg2)

        result = await repository.find_by_thread("C123456", "thread_a")

        assert len(result) == 1
        assert result[0].id == "1.001"

    async def test_find_empty_thread(self, repository: SQLiteMessageRepository) -> None:
        """Test finding in empty thread."""
        result = await repository.find_by_thread("C123456", "nonexistent_thread")

        assert result == []


class TestFindById:
    """find_by_id method tests."""

    async def test_find_existing_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test finding existing message by ID."""
        message = create_test_message()
        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)

        assert found is not None
        assert found.id == message.id
        assert found.text == message.text

    async def test_find_nonexistent_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test finding nonexistent message returns None."""
        found = await repository.find_by_id("nonexistent", "C123456")

        assert found is None

    async def test_find_wrong_channel(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that message with same ID but different channel returns None."""
        message = create_test_message(channel_id="C111111")
        await repository.save(message)

        found = await repository.find_by_id(message.id, "C999999")

        assert found is None


class TestFindByChannelSince:
    """find_by_channel_since method tests."""

    async def test_find_messages_after_since(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that only messages after since are returned."""
        base_time = datetime.now(timezone.utc)
        messages = [
            create_test_message(
                id=f"1.{i:03d}",
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(5)
        ]
        for msg in messages:
            await repository.save(msg)

        # Get messages after minute 2
        since = base_time + timedelta(minutes=2)
        result = await repository.find_by_channel_since("C123456", since)

        # Should get messages 3 and 4 (after minute 2)
        assert len(result) == 2
        assert result[0].id == "1.004"  # Newest first
        assert result[1].id == "1.003"

    async def test_find_with_limit(self, repository: SQLiteMessageRepository) -> None:
        """Test limit parameter with since."""
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            await repository.save(
                create_test_message(
                    id=f"1.{i:03d}",
                    timestamp=base_time + timedelta(minutes=i),
                )
            )

        since = base_time + timedelta(minutes=3)
        result = await repository.find_by_channel_since("C123456", since, limit=3)

        assert len(result) == 3

    async def test_find_excludes_thread_messages(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that thread messages are excluded."""
        base_time = datetime.now(timezone.utc)
        # Channel message after since
        channel_msg = create_test_message(
            id="1.001", timestamp=base_time + timedelta(minutes=5), thread_ts=None
        )
        # Thread message after since
        thread_msg = create_test_message(
            id="1.002", timestamp=base_time + timedelta(minutes=6), thread_ts="1.000"
        )

        await repository.save(channel_msg)
        await repository.save(thread_msg)

        since = base_time
        result = await repository.find_by_channel_since("C123456", since)

        assert len(result) == 1
        assert result[0].id == "1.001"

    async def test_find_empty_when_no_messages_after_since(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test empty result when no messages are after since."""
        base_time = datetime.now(timezone.utc)
        message = create_test_message(
            id="1.001", timestamp=base_time - timedelta(minutes=10)
        )
        await repository.save(message)

        since = base_time
        result = await repository.find_by_channel_since("C123456", since)

        assert result == []

    async def test_find_excludes_other_channels(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that messages from other channels are excluded."""
        base_time = datetime.now(timezone.utc)
        msg_c1 = create_test_message(
            id="1.001", channel_id="C111111", timestamp=base_time + timedelta(minutes=5)
        )
        msg_c2 = create_test_message(
            id="1.002", channel_id="C222222", timestamp=base_time + timedelta(minutes=5)
        )

        await repository.save(msg_c1)
        await repository.save(msg_c2)

        since = base_time
        result = await repository.find_by_channel_since("C111111", since)

        assert len(result) == 1
        assert result[0].channel.id == "C111111"


class TestConversion:
    """Entity/Model conversion tests."""

    async def test_to_entity_converts_all_fields(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that _to_entity converts all fields correctly."""
        message = create_test_message(
            id="1.001",
            channel_id="C123",
            user_id="U456",
            user_name="testuser",
            is_bot=True,
            text="Hello",
            thread_ts="1.000",
            mentions=["U111", "U222"],
        )
        await repository.save(message)

        found = await repository.find_by_id("1.001", "C123")

        assert found is not None
        assert found.id == "1.001"
        assert found.channel.id == "C123"
        assert found.user.id == "U456"
        assert found.user.name == "testuser"
        assert found.user.is_bot is True
        assert found.text == "Hello"
        assert found.thread_ts == "1.000"
        assert found.mentions == ["U111", "U222"]

    async def test_to_entity_with_empty_mentions(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that _to_entity handles empty mentions correctly."""
        message = create_test_message(mentions=[])
        await repository.save(message)

        found = await repository.find_by_id(message.id, message.channel.id)

        assert found is not None
        assert found.mentions == []

    async def test_channel_name_is_empty_on_retrieve(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that channel name is empty string after retrieval."""
        message = create_test_message()
        # Original has channel name "general"
        assert message.channel.name == "general"

        await repository.save(message)
        found = await repository.find_by_id(message.id, message.channel.id)

        # Retrieved has empty channel name (not persisted)
        assert found is not None
        assert found.channel.name == ""

    async def test_to_model_serializes_mentions_as_json(
        self, session_factory, repository: SQLiteMessageRepository
    ) -> None:
        """Test that _to_model serializes mentions as JSON."""
        message = create_test_message(mentions=["U111", "U222"])
        await repository.save(message)

        # Directly query the model to check JSON serialization
        async with session_factory() as session:
            statement = select(MessageModel)
            result = await session.exec(statement)
            model = result.first()
            assert model is not None
            assert model.mentions == '["U111", "U222"]'
            # Verify it's valid JSON
            assert json.loads(model.mentions) == ["U111", "U222"]


class TestDelete:
    """delete method tests."""

    async def test_delete_existing_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test deleting an existing message."""
        message = create_test_message()
        await repository.save(message)

        await repository.delete(message.id, message.channel.id)

        found = await repository.find_by_id(message.id, message.channel.id)
        assert found is None

    async def test_delete_nonexistent_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test deleting a nonexistent message does not raise error."""
        # Should not raise
        await repository.delete("nonexistent", "C123456")

    async def test_delete_wrong_channel(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that delete with wrong channel does not delete message."""
        message = create_test_message(channel_id="C111111")
        await repository.save(message)

        # Try to delete with wrong channel
        await repository.delete(message.id, "C999999")

        # Message should still exist
        found = await repository.find_by_id(message.id, "C111111")
        assert found is not None

    async def test_delete_only_specific_message(
        self, repository: SQLiteMessageRepository
    ) -> None:
        """Test that delete only removes the specific message."""
        msg1 = create_test_message(id="1.001")
        msg2 = create_test_message(id="1.002")
        await repository.save(msg1)
        await repository.save(msg2)

        await repository.delete("1.001", "C123456")

        # Only msg1 should be deleted
        assert await repository.find_by_id("1.001", "C123456") is None
        assert await repository.find_by_id("1.002", "C123456") is not None
