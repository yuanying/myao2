"""Tests for Memo entity."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from myao2.domain.entities.memo import Memo, TagStats, create_memo


class TestMemo:
    """Tests for Memo entity."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def memo_id(self) -> UUID:
        """Create a fixed UUID for testing."""
        return UUID("12345678-1234-5678-1234-567812345678")

    @pytest.fixture
    def sample_memo(self, memo_id: UUID, now: datetime) -> Memo:
        """Create a sample Memo instance."""
        return Memo(
            id=memo_id,
            name="test-memo",
            content="Test memo content",
            priority=3,
            tags=["user", "preference"],
            detail=None,
            created_at=now,
            updated_at=now,
        )

    def test_create_with_valid_params(self, memo_id: UUID, now: datetime) -> None:
        """Test creating Memo with valid parameters."""
        memo = Memo(
            id=memo_id,
            name="my-memo",
            content="Test memo content",
            priority=3,
            tags=["user", "preference"],
            detail=None,
            created_at=now,
            updated_at=now,
        )

        assert memo.id == memo_id
        assert memo.name == "my-memo"
        assert memo.content == "Test memo content"
        assert memo.priority == 3
        assert memo.tags == ["user", "preference"]
        assert memo.detail is None
        assert memo.created_at == now
        assert memo.updated_at == now

    def test_create_with_detail(self, memo_id: UUID, now: datetime) -> None:
        """Test creating Memo with detail."""
        memo = Memo(
            id=memo_id,
            name="detail-memo",
            content="Short content",
            priority=4,
            tags=["task"],
            detail="This is a longer detailed description of the memo.",
            created_at=now,
            updated_at=now,
        )

        assert memo.detail == "This is a longer detailed description of the memo."

    def test_has_detail_with_none(self, sample_memo: Memo) -> None:
        """Test has_detail property when detail is None."""
        assert sample_memo.has_detail is False

    def test_has_detail_with_empty_string(self, memo_id: UUID, now: datetime) -> None:
        """Test has_detail property when detail is empty string."""
        memo = Memo(
            id=memo_id,
            name="empty-detail",
            content="Test",
            priority=3,
            tags=[],
            detail="",
            created_at=now,
            updated_at=now,
        )
        assert memo.has_detail is False

    def test_has_detail_with_whitespace_only(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test has_detail property when detail is whitespace only."""
        memo = Memo(
            id=memo_id,
            name="whitespace-detail",
            content="Test",
            priority=3,
            tags=[],
            detail="   \n\t  ",
            created_at=now,
            updated_at=now,
        )
        assert memo.has_detail is False

    def test_has_detail_with_value(self, memo_id: UUID, now: datetime) -> None:
        """Test has_detail property when detail has value."""
        memo = Memo(
            id=memo_id,
            name="has-detail",
            content="Test",
            priority=3,
            tags=[],
            detail="Some detail",
            created_at=now,
            updated_at=now,
        )
        assert memo.has_detail is True

    def test_priority_below_range_raises_error(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test that priority below 1 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="low-priority",
                content="Test",
                priority=0,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Priority must be between 1 and 5" in str(exc_info.value)

    def test_priority_above_range_raises_error(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test that priority above 5 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="high-priority",
                content="Test",
                priority=6,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Priority must be between 1 and 5" in str(exc_info.value)

    def test_empty_content_raises_error(self, memo_id: UUID, now: datetime) -> None:
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="empty-content",
                content="",
                priority=3,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Content cannot be empty" in str(exc_info.value)

    def test_whitespace_only_content_raises_error(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test that whitespace-only content raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="whitespace-content",
                content="   \n\t  ",
                priority=3,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Content cannot be empty" in str(exc_info.value)

    def test_too_many_tags_raises_error(self, memo_id: UUID, now: datetime) -> None:
        """Test that more than 3 tags raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="too-many-tags",
                content="Test",
                priority=3,
                tags=["tag1", "tag2", "tag3", "tag4"],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Maximum 3 tags allowed per memo" in str(exc_info.value)

    def test_three_tags_is_valid(self, memo_id: UUID, now: datetime) -> None:
        """Test that exactly 3 tags is valid."""
        memo = Memo(
            id=memo_id,
            name="three-tags",
            content="Test",
            priority=3,
            tags=["tag1", "tag2", "tag3"],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert len(memo.tags) == 3

    def test_empty_tags_is_valid(self, memo_id: UUID, now: datetime) -> None:
        """Test that empty tags list is valid."""
        memo = Memo(
            id=memo_id,
            name="empty-tags",
            content="Test",
            priority=3,
            tags=[],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert memo.tags == []

    def test_memo_is_immutable(self, sample_memo: Memo) -> None:
        """Test that Memo is frozen (immutable)."""
        with pytest.raises(AttributeError):
            sample_memo.content = "Modified content"  # type: ignore[misc]

    def test_memo_equality(self, memo_id: UUID, now: datetime) -> None:
        """Test that two Memo instances with same values are equal."""
        memo1 = Memo(
            id=memo_id,
            name="equal-memo",
            content="Same content",
            priority=3,
            tags=["tag1"],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        memo2 = Memo(
            id=memo_id,
            name="equal-memo",
            content="Same content",
            priority=3,
            tags=["tag1"],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert memo1 == memo2

    def test_empty_name_raises_error(self, memo_id: UUID, now: datetime) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="",
                content="Test",
                priority=3,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Name cannot be empty" in str(exc_info.value)

    def test_whitespace_only_name_raises_error(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test that whitespace-only name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name="   \n\t  ",
                content="Test",
                priority=3,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Name cannot be empty" in str(exc_info.value)

    def test_name_exceeds_max_length_raises_error(
        self, memo_id: UUID, now: datetime
    ) -> None:
        """Test that name exceeding 32 characters raises ValueError."""
        long_name = "a" * 33
        with pytest.raises(ValueError) as exc_info:
            Memo(
                id=memo_id,
                name=long_name,
                content="Test",
                priority=3,
                tags=[],
                detail=None,
                created_at=now,
                updated_at=now,
            )
        assert "Name must be 32 characters or less" in str(exc_info.value)

    def test_name_at_max_length_is_valid(self, memo_id: UUID, now: datetime) -> None:
        """Test that name with exactly 32 characters is valid."""
        max_name = "a" * 32
        memo = Memo(
            id=memo_id,
            name=max_name,
            content="Test",
            priority=3,
            tags=[],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert memo.name == max_name

    def test_name_with_japanese_characters(self, memo_id: UUID, now: datetime) -> None:
        """Test that name with Japanese characters is valid."""
        memo = Memo(
            id=memo_id,
            name="日本語のメモ名",
            content="Test",
            priority=3,
            tags=[],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert memo.name == "日本語のメモ名"

    def test_name_with_spaces_is_valid(self, memo_id: UUID, now: datetime) -> None:
        """Test that name with spaces is valid."""
        memo = Memo(
            id=memo_id,
            name="my memo name",
            content="Test",
            priority=3,
            tags=[],
            detail=None,
            created_at=now,
            updated_at=now,
        )
        assert memo.name == "my memo name"


class TestCreateMemo:
    """Tests for create_memo factory function."""

    def test_create_memo_with_required_params_only(self) -> None:
        """Test creating Memo with required parameters only."""
        memo = create_memo(
            name="factory-memo",
            content="Factory created memo",
            priority=3,
        )

        assert memo.name == "factory-memo"
        assert memo.content == "Factory created memo"
        assert memo.priority == 3
        assert memo.tags == []
        assert memo.detail is None

    def test_create_memo_with_tags(self) -> None:
        """Test creating Memo with tags."""
        memo = create_memo(
            name="tagged-memo",
            content="Memo with tags",
            priority=4,
            tags=["user", "preference"],
        )

        assert memo.tags == ["user", "preference"]

    def test_create_memo_sets_timestamps(self) -> None:
        """Test that create_memo sets created_at and updated_at."""
        before = datetime.now(timezone.utc)
        memo = create_memo(
            name="timestamp-memo",
            content="Timestamp test",
            priority=3,
        )
        after = datetime.now(timezone.utc)

        assert before <= memo.created_at <= after
        assert memo.created_at == memo.updated_at

    def test_create_memo_generates_unique_id(self) -> None:
        """Test that create_memo generates unique UUID."""
        memo1 = create_memo(name="memo-1", content="Memo 1", priority=3)
        memo2 = create_memo(name="memo-2", content="Memo 2", priority=3)

        assert memo1.id != memo2.id
        assert isinstance(memo1.id, UUID)
        assert isinstance(memo2.id, UUID)

    def test_create_memo_with_validation_error(self) -> None:
        """Test that create_memo raises ValueError for invalid params."""
        with pytest.raises(ValueError):
            create_memo(name="valid", content="", priority=3)

        with pytest.raises(ValueError):
            create_memo(name="valid", content="Valid", priority=0)

        with pytest.raises(ValueError):
            create_memo(name="valid", content="Valid", priority=3, tags=["1", "2", "3", "4"])

    def test_create_memo_with_empty_name_raises_error(self) -> None:
        """Test that create_memo raises ValueError for empty name."""
        with pytest.raises(ValueError):
            create_memo(name="", content="Valid", priority=3)

    def test_create_memo_with_long_name_raises_error(self) -> None:
        """Test that create_memo raises ValueError for name exceeding 32 chars."""
        with pytest.raises(ValueError):
            create_memo(name="a" * 33, content="Valid", priority=3)


class TestTagStats:
    """Tests for TagStats dataclass."""

    @pytest.fixture
    def now(self) -> datetime:
        """Create a fixed current time for testing."""
        return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_create_tag_stats(self, now: datetime) -> None:
        """Test creating TagStats with valid parameters."""
        stats = TagStats(
            tag="user",
            count=10,
            latest_updated_at=now,
        )

        assert stats.tag == "user"
        assert stats.count == 10
        assert stats.latest_updated_at == now

    def test_tag_stats_is_immutable(self, now: datetime) -> None:
        """Test that TagStats is frozen (immutable)."""
        stats = TagStats(tag="user", count=10, latest_updated_at=now)
        with pytest.raises(AttributeError):
            stats.count = 20  # type: ignore[misc]

    def test_tag_stats_equality(self, now: datetime) -> None:
        """Test that two TagStats instances with same values are equal."""
        stats1 = TagStats(tag="user", count=10, latest_updated_at=now)
        stats2 = TagStats(tag="user", count=10, latest_updated_at=now)
        assert stats1 == stats2
