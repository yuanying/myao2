"""Tests for Memory entity."""

from datetime import datetime, timezone

import pytest

from myao2.domain.entities.memory import (
    Memory,
    MemoryScope,
    MemoryType,
    create_memory,
    is_valid_memory_combination,
    make_thread_scope_id,
    parse_thread_scope_id,
)


class TestMemoryScope:
    """Tests for MemoryScope enum."""

    def test_workspace_value(self) -> None:
        """Test WORKSPACE scope value."""
        assert MemoryScope.WORKSPACE.value == "workspace"

    def test_channel_value(self) -> None:
        """Test CHANNEL scope value."""
        assert MemoryScope.CHANNEL.value == "channel"

    def test_thread_value(self) -> None:
        """Test THREAD scope value."""
        assert MemoryScope.THREAD.value == "thread"


class TestMemoryType:
    """Tests for MemoryType enum."""

    def test_long_term_value(self) -> None:
        """Test LONG_TERM type value."""
        assert MemoryType.LONG_TERM.value == "long_term"

    def test_short_term_value(self) -> None:
        """Test SHORT_TERM type value."""
        assert MemoryType.SHORT_TERM.value == "short_term"


class TestIsValidMemoryCombination:
    """Tests for is_valid_memory_combination function."""

    def test_workspace_long_term_is_valid(self) -> None:
        """WORKSPACE + LONG_TERM is valid."""
        assert is_valid_memory_combination(MemoryScope.WORKSPACE, MemoryType.LONG_TERM)

    def test_workspace_short_term_is_valid(self) -> None:
        """WORKSPACE + SHORT_TERM is valid."""
        assert is_valid_memory_combination(MemoryScope.WORKSPACE, MemoryType.SHORT_TERM)

    def test_channel_long_term_is_valid(self) -> None:
        """CHANNEL + LONG_TERM is valid."""
        assert is_valid_memory_combination(MemoryScope.CHANNEL, MemoryType.LONG_TERM)

    def test_channel_short_term_is_valid(self) -> None:
        """CHANNEL + SHORT_TERM is valid."""
        assert is_valid_memory_combination(MemoryScope.CHANNEL, MemoryType.SHORT_TERM)

    def test_thread_short_term_is_valid(self) -> None:
        """THREAD + SHORT_TERM is valid."""
        assert is_valid_memory_combination(MemoryScope.THREAD, MemoryType.SHORT_TERM)

    def test_thread_long_term_is_invalid(self) -> None:
        """THREAD + LONG_TERM is invalid."""
        assert not is_valid_memory_combination(MemoryScope.THREAD, MemoryType.LONG_TERM)


class TestMemory:
    """Tests for Memory entity."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def sample_memory(self, now: datetime) -> Memory:
        """Create a sample Memory instance."""
        return Memory(
            scope=MemoryScope.CHANNEL,
            scope_id="C1234567890",
            memory_type=MemoryType.LONG_TERM,
            content="This is a long-term memory for the channel.",
            created_at=now,
            updated_at=now,
            source_message_count=10,
            source_latest_message_ts="1234567890.123456",
        )

    def test_create_with_valid_combination(self, now: datetime) -> None:
        """Test creating Memory with valid scope and type combination."""
        memory = Memory(
            scope=MemoryScope.CHANNEL,
            scope_id="C1234567890",
            memory_type=MemoryType.LONG_TERM,
            content="Test memory content",
            created_at=now,
            updated_at=now,
            source_message_count=5,
            source_latest_message_ts="1234567890.123456",
        )

        assert memory.scope == MemoryScope.CHANNEL
        assert memory.scope_id == "C1234567890"
        assert memory.memory_type == MemoryType.LONG_TERM
        assert memory.content == "Test memory content"
        assert memory.source_message_count == 5
        assert memory.source_latest_message_ts == "1234567890.123456"

    def test_create_with_invalid_combination_raises_error(self, now: datetime) -> None:
        """Test that invalid combination raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memory(
                scope=MemoryScope.THREAD,
                scope_id="C1234567890:1234567890.123456",
                memory_type=MemoryType.LONG_TERM,
                content="Invalid memory",
                created_at=now,
                updated_at=now,
                source_message_count=1,
            )

        assert "Invalid memory combination" in str(exc_info.value)
        assert "THREAD" in str(exc_info.value)
        assert "LONG_TERM" in str(exc_info.value)

    def test_memory_is_immutable(self, sample_memory: Memory) -> None:
        """Test that Memory is frozen (immutable)."""
        with pytest.raises(AttributeError):
            sample_memory.content = "Modified content"  # type: ignore[misc]

    def test_memory_equality(self, now: datetime) -> None:
        """Test that two Memory instances with same values are equal."""
        memory1 = Memory(
            scope=MemoryScope.WORKSPACE,
            scope_id="default",
            memory_type=MemoryType.SHORT_TERM,
            content="Same content",
            created_at=now,
            updated_at=now,
            source_message_count=3,
        )
        memory2 = Memory(
            scope=MemoryScope.WORKSPACE,
            scope_id="default",
            memory_type=MemoryType.SHORT_TERM,
            content="Same content",
            created_at=now,
            updated_at=now,
            source_message_count=3,
        )

        assert memory1 == memory2

    def test_source_latest_message_ts_defaults_to_none(self, now: datetime) -> None:
        """Test that source_latest_message_ts defaults to None."""
        memory = Memory(
            scope=MemoryScope.WORKSPACE,
            scope_id="default",
            memory_type=MemoryType.LONG_TERM,
            content="Memory without latest ts",
            created_at=now,
            updated_at=now,
            source_message_count=0,
        )

        assert memory.source_latest_message_ts is None


class TestCreateMemory:
    """Tests for create_memory factory function."""

    def test_create_memory_with_required_params(self) -> None:
        """Test creating Memory with required parameters only."""
        memory = create_memory(
            scope=MemoryScope.CHANNEL,
            scope_id="C1234567890",
            memory_type=MemoryType.LONG_TERM,
            content="Factory created memory",
            source_message_count=5,
        )

        assert memory.scope == MemoryScope.CHANNEL
        assert memory.scope_id == "C1234567890"
        assert memory.memory_type == MemoryType.LONG_TERM
        assert memory.content == "Factory created memory"
        assert memory.source_message_count == 5
        assert memory.source_latest_message_ts is None

    def test_create_memory_sets_timestamps(self) -> None:
        """Test that create_memory sets created_at and updated_at."""
        before = datetime.now(timezone.utc)
        memory = create_memory(
            scope=MemoryScope.WORKSPACE,
            scope_id="default",
            memory_type=MemoryType.SHORT_TERM,
            content="Test content",
            source_message_count=1,
        )
        after = datetime.now(timezone.utc)

        assert before <= memory.created_at <= after
        assert memory.created_at == memory.updated_at

    def test_create_memory_with_latest_message_ts(self) -> None:
        """Test creating Memory with source_latest_message_ts."""
        memory = create_memory(
            scope=MemoryScope.THREAD,
            scope_id="C1234567890:1234567890.123456",
            memory_type=MemoryType.SHORT_TERM,
            content="Thread memory",
            source_message_count=3,
            source_latest_message_ts="1234567890.999999",
        )

        assert memory.source_latest_message_ts == "1234567890.999999"

    def test_create_memory_with_invalid_combination_raises_error(self) -> None:
        """Test that invalid combination raises ValueError in factory."""
        with pytest.raises(ValueError):
            create_memory(
                scope=MemoryScope.THREAD,
                scope_id="C1234567890:1234567890.123456",
                memory_type=MemoryType.LONG_TERM,
                content="Invalid memory",
                source_message_count=1,
            )


class TestThreadScopeIdHelpers:
    """Tests for thread scope_id helper functions."""

    def test_make_thread_scope_id(self) -> None:
        """Test making thread scope_id from channel_id and thread_ts."""
        scope_id = make_thread_scope_id("C1234567890", "1234567890.123456")

        assert scope_id == "C1234567890:1234567890.123456"

    def test_parse_thread_scope_id(self) -> None:
        """Test parsing thread scope_id to channel_id and thread_ts."""
        channel_id, thread_ts = parse_thread_scope_id("C1234567890:1234567890.123456")

        assert channel_id == "C1234567890"
        assert thread_ts == "1234567890.123456"

    def test_parse_thread_scope_id_with_colon_in_thread_ts(self) -> None:
        """Test parsing scope_id when thread_ts contains colon."""
        channel_id, thread_ts = parse_thread_scope_id("C1234567890:1234:5678.90")

        assert channel_id == "C1234567890"
        assert thread_ts == "1234:5678.90"

    def test_parse_thread_scope_id_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_thread_scope_id("invalid_scope_id_without_colon")

        assert "Invalid thread scope_id format" in str(exc_info.value)

    def test_roundtrip_make_and_parse(self) -> None:
        """Test that make and parse are inverse operations."""
        original_channel_id = "C9876543210"
        original_thread_ts = "9876543210.654321"

        scope_id = make_thread_scope_id(original_channel_id, original_thread_ts)
        channel_id, thread_ts = parse_thread_scope_id(scope_id)

        assert channel_id == original_channel_id
        assert thread_ts == original_thread_ts
