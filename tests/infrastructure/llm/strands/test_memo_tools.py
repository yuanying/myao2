"""Tests for memo tools."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from myao2.domain.entities.memo import Memo, TagStats
from myao2.infrastructure.llm.strands.memo_tools import (
    MEMO_REPOSITORY_KEY,
    MEMO_TOOLS,
    MemoToolsFactory,
    add_memo,
    edit_memo,
    get_memo,
    get_memo_repository,
    list_memo,
    list_memo_tags,
    remove_memo,
)


@pytest.fixture
def mock_memo_repository() -> MagicMock:
    """Create mock MemoRepository."""
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_all = AsyncMock()
    repo.find_by_tag = AsyncMock()
    repo.get_all_tags_with_stats = AsyncMock()
    repo.delete = AsyncMock()
    repo.count = AsyncMock()
    return repo


@pytest.fixture
def mock_tool_context(mock_memo_repository: MagicMock) -> MagicMock:
    """Create mock ToolContext with memo repository in invocation_state."""
    context = MagicMock()
    context.invocation_state = {MEMO_REPOSITORY_KEY: mock_memo_repository}
    return context


@pytest.fixture
def empty_tool_context() -> MagicMock:
    """Create mock ToolContext without memo repository."""
    context = MagicMock()
    context.invocation_state = {}
    return context


@pytest.fixture
def sample_memo() -> Memo:
    """Create sample memo for testing."""
    return Memo(
        id=uuid4(),
        content="Test memo content",
        priority=3,
        tags=["test"],
        detail=None,
        created_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_memo_with_detail() -> Memo:
    """Create sample memo with detail for testing."""
    return Memo(
        id=uuid4(),
        content="Test memo with detail",
        priority=4,
        tags=["preference"],
        detail="Detailed information here",
        created_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
    )


class TestGetMemoRepository:
    """Tests for get_memo_repository helper."""

    def test_returns_repository_from_invocation_state(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test that repository is returned from invocation_state."""
        result = get_memo_repository(mock_tool_context)

        assert result is mock_memo_repository

    def test_raises_runtime_error_when_not_found(
        self, empty_tool_context: MagicMock
    ) -> None:
        """Test that RuntimeError is raised when repository not found."""
        with pytest.raises(RuntimeError, match="MemoRepository not found"):
            get_memo_repository(empty_tool_context)


class TestAddMemo:
    """Tests for add_memo tool."""

    async def test_add_memo_success(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test successful memo addition."""
        result = await add_memo(
            content="New memo content",
            priority=3,
            tags=None,
            tool_context=mock_tool_context,
        )

        assert "メモを追加しました" in result
        assert "ID:" in result
        mock_memo_repository.save.assert_called_once()
        saved_memo = mock_memo_repository.save.call_args[0][0]
        assert saved_memo.content == "New memo content"
        assert saved_memo.priority == 3
        assert saved_memo.tags == []

    async def test_add_memo_with_tags(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test memo addition with tags."""
        result = await add_memo(
            content="Tagged memo",
            priority=5,
            tags=["user", "schedule"],
            tool_context=mock_tool_context,
        )

        assert "メモを追加しました" in result
        saved_memo = mock_memo_repository.save.call_args[0][0]
        assert saved_memo.tags == ["user", "schedule"]

    async def test_add_memo_invalid_priority(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test memo addition with invalid priority."""
        result = await add_memo(
            content="Invalid priority memo",
            priority=6,
            tags=None,
            tool_context=mock_tool_context,
        )

        assert "メモの作成に失敗しました" in result

    async def test_add_memo_empty_content(self, mock_tool_context: MagicMock) -> None:
        """Test memo addition with empty content."""
        result = await add_memo(
            content="   ",
            priority=3,
            tags=None,
            tool_context=mock_tool_context,
        )

        assert "メモの作成に失敗しました" in result

    async def test_add_memo_too_many_tags(self, mock_tool_context: MagicMock) -> None:
        """Test memo addition with too many tags."""
        result = await add_memo(
            content="Too many tags",
            priority=3,
            tags=["tag1", "tag2", "tag3", "tag4"],
            tool_context=mock_tool_context,
        )

        assert "メモの作成に失敗しました" in result


class TestEditMemo:
    """Tests for edit_memo tool."""

    async def test_edit_memo_all_fields(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test editing all fields of a memo."""
        mock_memo_repository.find_by_id.return_value = sample_memo

        result = await edit_memo(
            memo_id=str(sample_memo.id),
            content="Updated content",
            priority=5,
            tags=["updated"],
            detail="New detail",
            tool_context=mock_tool_context,
        )

        assert "メモを更新しました" in result
        mock_memo_repository.save.assert_called_once()
        saved_memo = mock_memo_repository.save.call_args[0][0]
        assert saved_memo.content == "Updated content"
        assert saved_memo.priority == 5
        assert saved_memo.tags == ["updated"]
        assert saved_memo.detail == "New detail"

    async def test_edit_memo_partial_fields(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test editing only some fields of a memo."""
        mock_memo_repository.find_by_id.return_value = sample_memo

        result = await edit_memo(
            memo_id=str(sample_memo.id),
            content="Updated content only",
            priority=None,
            tags=None,
            detail=None,
            tool_context=mock_tool_context,
        )

        assert "メモを更新しました" in result
        saved_memo = mock_memo_repository.save.call_args[0][0]
        assert saved_memo.content == "Updated content only"
        assert saved_memo.priority == sample_memo.priority
        assert saved_memo.tags == sample_memo.tags

    async def test_edit_memo_add_detail(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test adding detail to a memo."""
        mock_memo_repository.find_by_id.return_value = sample_memo

        result = await edit_memo(
            memo_id=str(sample_memo.id),
            content=None,
            priority=None,
            tags=None,
            detail="Added detail",
            tool_context=mock_tool_context,
        )

        assert "メモを更新しました" in result
        saved_memo = mock_memo_repository.save.call_args[0][0]
        assert saved_memo.detail == "Added detail"

    async def test_edit_memo_not_found(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test editing a non-existent memo."""
        mock_memo_repository.find_by_id.return_value = None
        memo_id = str(uuid4())

        result = await edit_memo(
            memo_id=memo_id,
            content="Updated",
            priority=None,
            tags=None,
            detail=None,
            tool_context=mock_tool_context,
        )

        assert "メモが見つかりません" in result

    async def test_edit_memo_invalid_id_format(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test editing with invalid memo ID format."""
        result = await edit_memo(
            memo_id="invalid-uuid",
            content="Updated",
            priority=None,
            tags=None,
            detail=None,
            tool_context=mock_tool_context,
        )

        assert "無効なメモID" in result

    async def test_edit_memo_invalid_priority(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test editing with invalid priority."""
        mock_memo_repository.find_by_id.return_value = sample_memo

        result = await edit_memo(
            memo_id=str(sample_memo.id),
            content=None,
            priority=0,
            tags=None,
            detail=None,
            tool_context=mock_tool_context,
        )

        assert "メモの更新に失敗しました" in result


class TestRemoveMemo:
    """Tests for remove_memo tool."""

    async def test_remove_memo_success(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test successful memo removal."""
        mock_memo_repository.delete.return_value = True
        memo_id = str(uuid4())

        result = await remove_memo(
            memo_id=memo_id,
            tool_context=mock_tool_context,
        )

        assert "メモを削除しました" in result
        assert memo_id[:8] in result

    async def test_remove_memo_not_found(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test removing a non-existent memo."""
        mock_memo_repository.delete.return_value = False
        memo_id = str(uuid4())

        result = await remove_memo(
            memo_id=memo_id,
            tool_context=mock_tool_context,
        )

        assert "メモが見つかりません" in result

    async def test_remove_memo_invalid_id_format(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test removing with invalid memo ID format."""
        result = await remove_memo(
            memo_id="invalid-uuid",
            tool_context=mock_tool_context,
        )

        assert "無効なメモID" in result


class TestListMemo:
    """Tests for list_memo tool."""

    async def test_list_memo_empty(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test listing when no memos exist."""
        mock_memo_repository.find_all.return_value = []
        mock_memo_repository.count.return_value = 0

        result = await list_memo(
            tag=None,
            offset=None,
            limit=None,
            tool_context=mock_tool_context,
        )

        assert "メモがありません" in result

    async def test_list_memo_multiple(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test listing multiple memos."""
        memo2 = Memo(
            id=uuid4(),
            content="Second memo",
            priority=5,
            tags=["user"],
            detail=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_memo_repository.find_all.return_value = [memo2, sample_memo]
        mock_memo_repository.count.return_value = 2

        result = await list_memo(
            tag=None,
            offset=None,
            limit=None,
            tool_context=mock_tool_context,
        )

        assert "メモ一覧（1-2件 / 全2件）" in result
        assert "Second memo" in result
        assert "Test memo content" in result

    async def test_list_memo_with_tag_filter(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test listing memos filtered by tag."""
        mock_memo_repository.find_by_tag.return_value = [sample_memo]
        mock_memo_repository.count.return_value = 1

        result = await list_memo(
            tag="test",
            offset=None,
            limit=None,
            tool_context=mock_tool_context,
        )

        assert "メモ一覧" in result
        mock_memo_repository.find_by_tag.assert_called_once()

    async def test_list_memo_tag_not_found(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test listing with a tag that has no memos."""
        mock_memo_repository.find_by_tag.return_value = []
        mock_memo_repository.count.return_value = 0

        result = await list_memo(
            tag="nonexistent",
            offset=None,
            limit=None,
            tool_context=mock_tool_context,
        )

        assert "タグ「nonexistent」のメモは見つかりませんでした" in result

    async def test_list_memo_pagination(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test listing with pagination."""
        mock_memo_repository.find_all.return_value = [sample_memo]
        mock_memo_repository.count.return_value = 25

        result = await list_memo(
            tag=None,
            offset=10,
            limit=5,
            tool_context=mock_tool_context,
        )

        assert "11-11件 / 全25件" in result
        mock_memo_repository.find_all.assert_called_with(offset=10, limit=5)

    async def test_list_memo_with_detail_marker(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo_with_detail: Memo,
    ) -> None:
        """Test that detail marker is shown for memos with detail."""
        mock_memo_repository.find_all.return_value = [sample_memo_with_detail]
        mock_memo_repository.count.return_value = 1

        result = await list_memo(
            tag=None,
            offset=None,
            limit=None,
            tool_context=mock_tool_context,
        )

        assert "[詳細あり]" in result


class TestGetMemo:
    """Tests for get_memo tool."""

    async def test_get_memo_success(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo: Memo,
    ) -> None:
        """Test successful memo retrieval."""
        mock_memo_repository.find_by_id.return_value = sample_memo

        result = await get_memo(
            memo_id=str(sample_memo.id),
            tool_context=mock_tool_context,
        )

        assert "メモ詳細:" in result
        assert f"ID: {str(sample_memo.id)[:8]}" in result
        assert "優先度: 3" in result
        assert "タグ: test" in result
        assert "内容: Test memo content" in result
        assert "作成日:" in result
        assert "更新日:" in result

    async def test_get_memo_with_detail(
        self,
        mock_tool_context: MagicMock,
        mock_memo_repository: MagicMock,
        sample_memo_with_detail: Memo,
    ) -> None:
        """Test retrieval of memo with detail."""
        mock_memo_repository.find_by_id.return_value = sample_memo_with_detail

        result = await get_memo(
            memo_id=str(sample_memo_with_detail.id),
            tool_context=mock_tool_context,
        )

        assert "詳細: Detailed information here" in result

    async def test_get_memo_not_found(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test getting a non-existent memo."""
        mock_memo_repository.find_by_id.return_value = None
        memo_id = str(uuid4())

        result = await get_memo(
            memo_id=memo_id,
            tool_context=mock_tool_context,
        )

        assert "メモが見つかりません" in result

    async def test_get_memo_invalid_id_format(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test getting with invalid memo ID format."""
        result = await get_memo(
            memo_id="invalid-uuid",
            tool_context=mock_tool_context,
        )

        assert "無効なメモID" in result


class TestListMemoTags:
    """Tests for list_memo_tags tool."""

    async def test_list_memo_tags_empty(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test listing tags when no tags exist."""
        mock_memo_repository.get_all_tags_with_stats.return_value = []

        result = await list_memo_tags(tool_context=mock_tool_context)

        assert "メモタグがありません" in result

    async def test_list_memo_tags_multiple(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test listing multiple tags."""
        stats = [
            TagStats(
                tag="user",
                count=10,
                latest_updated_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
            ),
            TagStats(
                tag="schedule",
                count=8,
                latest_updated_at=datetime(2024, 1, 19, tzinfo=timezone.utc),
            ),
        ]
        mock_memo_repository.get_all_tags_with_stats.return_value = stats

        result = await list_memo_tags(tool_context=mock_tool_context)

        assert "メモタグ一覧（2種類）:" in result
        assert "user: 10件（最終更新: 2024-01-20）" in result
        assert "schedule: 8件（最終更新: 2024-01-19）" in result

    async def test_list_memo_tags_sorted_by_count(
        self, mock_tool_context: MagicMock, mock_memo_repository: MagicMock
    ) -> None:
        """Test that tags are sorted by count (handled by repository)."""
        stats = [
            TagStats(
                tag="user",
                count=10,
                latest_updated_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
            ),
            TagStats(
                tag="schedule",
                count=5,
                latest_updated_at=datetime(2024, 1, 19, tzinfo=timezone.utc),
            ),
        ]
        mock_memo_repository.get_all_tags_with_stats.return_value = stats

        result = await list_memo_tags(tool_context=mock_tool_context)

        # Verify order in output
        user_pos = result.find("user:")
        schedule_pos = result.find("schedule:")
        assert user_pos < schedule_pos


class TestMemoToolsFactory:
    """Tests for MemoToolsFactory."""

    def test_get_invocation_state(self, mock_memo_repository: MagicMock) -> None:
        """Test invocation_state construction."""
        factory = MemoToolsFactory(mock_memo_repository)

        state = factory.get_invocation_state()

        assert MEMO_REPOSITORY_KEY in state
        assert state[MEMO_REPOSITORY_KEY] is mock_memo_repository

    def test_tools_property(self, mock_memo_repository: MagicMock) -> None:
        """Test tools property returns correct list."""
        factory = MemoToolsFactory(mock_memo_repository)

        tools = factory.tools

        assert tools is MEMO_TOOLS

    def test_tools_contains_all_tools(self, mock_memo_repository: MagicMock) -> None:
        """Test that all expected tools are in the list."""
        factory = MemoToolsFactory(mock_memo_repository)

        tools = factory.tools

        assert len(tools) == 6
        assert add_memo in tools
        assert edit_memo in tools
        assert remove_memo in tools
        assert list_memo in tools
        assert get_memo in tools
        assert list_memo_tags in tools
