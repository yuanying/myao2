"""Tests for JudgmentCache entity."""

from datetime import datetime, timedelta, timezone

import pytest

from myao2.domain.entities.judgment_cache import JudgmentCache


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


class TestJudgmentCacheCreation:
    """Tests for JudgmentCache creation."""

    def test_create_with_all_fields(self, now: datetime) -> None:
        """Test creating JudgmentCache with all fields."""
        cache = JudgmentCache(
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

        assert cache.channel_id == "C123"
        assert cache.thread_ts == "1234567890.123456"
        assert cache.should_respond is False
        assert cache.confidence == 0.85
        assert cache.reason == "Not interesting"
        assert cache.latest_message_ts == "1234567890.999999"
        assert cache.next_check_at == now + timedelta(hours=1)
        assert cache.created_at == now
        assert cache.updated_at == now

    def test_create_top_level_cache(self, now: datetime) -> None:
        """Test creating JudgmentCache for top-level messages."""
        cache = JudgmentCache(
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

        assert cache.channel_id == "C456"
        assert cache.thread_ts is None
        assert cache.should_respond is True

    def test_cache_is_frozen(self, sample_cache: JudgmentCache) -> None:
        """Test that JudgmentCache is immutable (frozen=True)."""
        with pytest.raises(AttributeError):
            sample_cache.channel_id = "C999"  # type: ignore[misc]


class TestJudgmentCacheScopeKey:
    """Tests for scope_key property."""

    def test_scope_key_with_thread_ts(self, sample_cache: JudgmentCache) -> None:
        """Test scope_key with thread_ts."""
        assert sample_cache.scope_key == "C123:1234567890.123456"

    def test_scope_key_without_thread_ts(self, top_level_cache: JudgmentCache) -> None:
        """Test scope_key without thread_ts (top-level)."""
        assert top_level_cache.scope_key == "C456:top"


class TestJudgmentCacheIsValid:
    """Tests for is_valid method."""

    def test_is_valid_before_next_check_at_same_message(
        self, sample_cache: JudgmentCache, now: datetime
    ) -> None:
        """Test cache is valid when before next_check_at and same message."""
        current_time = now + timedelta(minutes=30)  # 30 minutes later
        same_message_ts = sample_cache.latest_message_ts

        assert sample_cache.is_valid(current_time, same_message_ts) is True

    def test_is_invalid_after_next_check_at(
        self, sample_cache: JudgmentCache, now: datetime
    ) -> None:
        """Test cache is invalid when current time >= next_check_at."""
        current_time = now + timedelta(hours=2)  # 2 hours later (after 1 hour)
        same_message_ts = sample_cache.latest_message_ts

        assert sample_cache.is_valid(current_time, same_message_ts) is False

    def test_is_invalid_at_exact_next_check_at(
        self, sample_cache: JudgmentCache, now: datetime
    ) -> None:
        """Test cache is invalid when current time == next_check_at."""
        current_time = sample_cache.next_check_at  # Exactly at next_check_at
        same_message_ts = sample_cache.latest_message_ts

        assert sample_cache.is_valid(current_time, same_message_ts) is False

    def test_is_invalid_with_new_message(
        self, sample_cache: JudgmentCache, now: datetime
    ) -> None:
        """Test cache is invalid when a new message has arrived."""
        current_time = now + timedelta(minutes=30)  # Still within valid time
        new_message_ts = "1234567891.000000"  # Different message

        assert sample_cache.is_valid(current_time, new_message_ts) is False

    def test_is_invalid_after_next_check_at_with_new_message(
        self, sample_cache: JudgmentCache, now: datetime
    ) -> None:
        """Test cache is invalid for both reasons."""
        current_time = now + timedelta(hours=2)  # After next_check_at
        new_message_ts = "1234567891.000000"  # Different message

        assert sample_cache.is_valid(current_time, new_message_ts) is False
