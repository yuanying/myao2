"""Tests for use case helper functions."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from myao2.application.use_cases.helpers import (
    WORKSPACE_SCOPE_ID,
    build_channel_messages,
    build_context_with_memory,
    get_memos_for_context,
)
from myao2.config import PersonaConfig
from myao2.domain.entities import (
    Channel,
    Memory,
    MemoryScope,
    MemoryType,
    Message,
    User,
)
from myao2.domain.entities.channel_messages import ChannelMessages
from myao2.domain.entities.memo import Memo
from myao2.domain.entities.memory import make_thread_scope_id


@pytest.fixture
def mock_memory_repository() -> Mock:
    """Create mock memory repository."""
    repo = Mock()
    repo.find_by_scope_and_type = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_message_repository() -> Mock:
    """Create mock message repository."""
    repo = Mock()
    repo.find_all_in_channel = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_channel_repository() -> Mock:
    """Create mock channel repository."""
    repo = Mock()
    repo.find_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def persona_config() -> PersonaConfig:
    """Create test persona config."""
    return PersonaConfig(
        name="TestBot",
        system_prompt="You are a test bot.",
    )


@pytest.fixture
def channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def user() -> User:
    """Create test user."""
    return User(id="U123", name="testuser", is_bot=False)


def create_memory(
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    content: str,
) -> Memory:
    """Create a test memory."""
    now = datetime.now(timezone.utc)
    return Memory(
        scope=scope,
        scope_id=scope_id,
        memory_type=memory_type,
        content=content,
        created_at=now,
        updated_at=now,
        source_message_count=0,
    )


class TestBuildChannelMessages:
    """Tests for build_channel_messages function."""

    def test_empty_messages(self, channel: Channel) -> None:
        """Test with empty message list."""
        result = build_channel_messages([], channel)

        assert result.channel_id == channel.id
        assert result.channel_name == channel.name
        assert result.top_level_messages == []
        assert result.thread_messages == {}

    def test_top_level_messages_only(self, channel: Channel, user: User) -> None:
        """Test with top-level messages only."""
        messages = [
            Message(
                id="1",
                channel=channel,
                user=user,
                text="Hello",
                timestamp=datetime.now(timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="2",
                channel=channel,
                user=user,
                text="World",
                timestamp=datetime.now(timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
        ]

        result = build_channel_messages(messages, channel)

        assert len(result.top_level_messages) == 2
        assert result.thread_messages == {}

    def test_thread_messages_only(self, channel: Channel, user: User) -> None:
        """Test with thread messages only (no parent message in input)."""
        messages = [
            Message(
                id="1.1",
                channel=channel,
                user=user,
                text="Reply 1",
                timestamp=datetime.now(timezone.utc),
                thread_ts="1",
                mentions=[],
            ),
            Message(
                id="1.2",
                channel=channel,
                user=user,
                text="Reply 2",
                timestamp=datetime.now(timezone.utc),
                thread_ts="1",
                mentions=[],
            ),
        ]

        result = build_channel_messages(messages, channel)

        assert result.top_level_messages == []
        assert "1" in result.thread_messages
        # Parent not in input, so only replies are present
        assert len(result.thread_messages["1"]) == 2

    def test_thread_with_parent_includes_parent_in_both(
        self, channel: Channel, user: User
    ) -> None:
        """Test that thread parent is included in both top_level and thread_messages."""
        parent_msg = Message(
            id="1",
            channel=channel,
            user=user,
            text="Parent message",
            timestamp=datetime.now(timezone.utc),
            thread_ts=None,
            mentions=[],
        )
        reply_msg = Message(
            id="1.1",
            channel=channel,
            user=user,
            text="Reply message",
            timestamp=datetime.now(timezone.utc),
            thread_ts="1",
            mentions=[],
        )
        messages = [parent_msg, reply_msg]

        result = build_channel_messages(messages, channel)

        # Parent should be in top_level_messages
        assert len(result.top_level_messages) == 1
        assert result.top_level_messages[0].id == "1"

        # Thread should contain parent as first message, then reply
        assert "1" in result.thread_messages
        assert len(result.thread_messages["1"]) == 2
        assert result.thread_messages["1"][0].id == "1"
        assert result.thread_messages["1"][1].id == "1.1"

    def test_multiple_threads_with_parents(self, channel: Channel, user: User) -> None:
        """Test multiple threads each with parent included."""
        messages = [
            Message(
                id="1",
                channel=channel,
                user=user,
                text="Thread 1 parent",
                timestamp=datetime.now(timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="2",
                channel=channel,
                user=user,
                text="Thread 2 parent",
                timestamp=datetime.now(timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
            Message(
                id="1.1",
                channel=channel,
                user=user,
                text="Reply to thread 1",
                timestamp=datetime.now(timezone.utc),
                thread_ts="1",
                mentions=[],
            ),
            Message(
                id="2.1",
                channel=channel,
                user=user,
                text="Reply to thread 2",
                timestamp=datetime.now(timezone.utc),
                thread_ts="2",
                mentions=[],
            ),
        ]

        result = build_channel_messages(messages, channel)

        # Both parents in top_level
        assert len(result.top_level_messages) == 2

        # Thread 1: parent + reply
        assert len(result.thread_messages["1"]) == 2
        assert result.thread_messages["1"][0].id == "1"
        assert result.thread_messages["1"][1].id == "1.1"

        # Thread 2: parent + reply
        assert len(result.thread_messages["2"]) == 2
        assert result.thread_messages["2"][0].id == "2"
        assert result.thread_messages["2"][1].id == "2.1"


class TestBuildContextWithMemory:
    """Tests for build_context_with_memory function."""

    @pytest.mark.asyncio
    async def test_no_memories(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test with no memories in repository."""
        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        assert result.persona == persona_config
        assert isinstance(result.conversation_history, ChannelMessages)
        assert result.conversation_history.channel_id == channel.id
        assert result.workspace_long_term_memory is None
        assert result.workspace_short_term_memory is None
        assert result.channel_memories == {}
        assert result.thread_memories == {}
        assert result.target_thread_ts is None

    @pytest.mark.asyncio
    async def test_with_workspace_memories(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test with workspace memories."""
        ws_long = create_memory(
            MemoryScope.WORKSPACE,
            WORKSPACE_SCOPE_ID,
            MemoryType.LONG_TERM,
            "workspace long-term memory",
        )
        ws_short = create_memory(
            MemoryScope.WORKSPACE,
            WORKSPACE_SCOPE_ID,
            MemoryType.SHORT_TERM,
            "workspace short-term memory",
        )

        def find_by_scope_and_type(
            scope: MemoryScope, scope_id: str, memory_type: MemoryType
        ) -> Memory | None:
            if scope == MemoryScope.WORKSPACE:
                if memory_type == MemoryType.LONG_TERM:
                    return ws_long
                elif memory_type == MemoryType.SHORT_TERM:
                    return ws_short
            return None

        mock_memory_repository.find_by_scope_and_type = AsyncMock(
            side_effect=find_by_scope_and_type
        )

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        assert result.workspace_long_term_memory == "workspace long-term memory"
        assert result.workspace_short_term_memory == "workspace short-term memory"

    @pytest.mark.asyncio
    async def test_with_channel_memories(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test with channel memories."""
        ch_long = create_memory(
            MemoryScope.CHANNEL,
            channel.id,
            MemoryType.LONG_TERM,
            "channel long-term memory",
        )
        ch_short = create_memory(
            MemoryScope.CHANNEL,
            channel.id,
            MemoryType.SHORT_TERM,
            "channel short-term memory",
        )

        mock_channel_repository.find_all = AsyncMock(return_value=[channel])

        def find_by_scope_and_type(
            scope: MemoryScope, scope_id: str, memory_type: MemoryType
        ) -> Memory | None:
            if scope == MemoryScope.CHANNEL and scope_id == channel.id:
                if memory_type == MemoryType.LONG_TERM:
                    return ch_long
                elif memory_type == MemoryType.SHORT_TERM:
                    return ch_short
            return None

        mock_memory_repository.find_by_scope_and_type = AsyncMock(
            side_effect=find_by_scope_and_type
        )

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        assert channel.id in result.channel_memories
        ch_mem = result.channel_memories[channel.id]
        assert ch_mem.channel_id == channel.id
        assert ch_mem.channel_name == channel.name
        assert ch_mem.long_term_memory == "channel long-term memory"
        assert ch_mem.short_term_memory == "channel short-term memory"

    @pytest.mark.asyncio
    async def test_with_thread_memory(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test with thread memory."""
        thread_ts = "12345.67890"
        scope_id = make_thread_scope_id(channel.id, thread_ts)

        thread_mem = create_memory(
            MemoryScope.THREAD,
            scope_id,
            MemoryType.SHORT_TERM,
            "thread memory content",
        )

        def find_by_scope_and_type(
            scope: MemoryScope, scope_id_arg: str, memory_type: MemoryType
        ) -> Memory | None:
            if (
                scope == MemoryScope.THREAD
                and scope_id_arg == scope_id
                and memory_type == MemoryType.SHORT_TERM
            ):
                return thread_mem
            return None

        mock_memory_repository.find_by_scope_and_type = AsyncMock(
            side_effect=find_by_scope_and_type
        )

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
            target_thread_ts=thread_ts,
        )

        assert result.target_thread_ts == thread_ts
        assert thread_ts in result.thread_memories
        assert result.thread_memories[thread_ts] == "thread memory content"

    @pytest.mark.asyncio
    async def test_no_thread_memory_without_target_thread_ts(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test that thread memory is not retrieved without target_thread_ts."""
        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
            target_thread_ts=None,
        )

        assert result.thread_memories == {}

    @pytest.mark.asyncio
    async def test_channel_without_memory_included_with_none_values(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test channels without memory are included with None values."""
        mock_channel_repository.find_all = AsyncMock(return_value=[channel])
        mock_memory_repository.find_by_scope_and_type = AsyncMock(return_value=None)

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        # Channel should be included even without memory (with None values)
        assert channel.id in result.channel_memories
        assert result.channel_memories[channel.id].long_term_memory is None
        assert result.channel_memories[channel.id].short_term_memory is None

    @pytest.mark.asyncio
    async def test_channel_with_partial_memory(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
    ) -> None:
        """Test channel with only short-term memory is included."""
        ch_short = create_memory(
            MemoryScope.CHANNEL,
            channel.id,
            MemoryType.SHORT_TERM,
            "channel short-term only",
        )

        mock_channel_repository.find_all = AsyncMock(return_value=[channel])

        def find_by_scope_and_type(
            scope: MemoryScope, scope_id: str, memory_type: MemoryType
        ) -> Memory | None:
            if (
                scope == MemoryScope.CHANNEL
                and scope_id == channel.id
                and memory_type == MemoryType.SHORT_TERM
            ):
                return ch_short
            return None

        mock_memory_repository.find_by_scope_and_type = AsyncMock(
            side_effect=find_by_scope_and_type
        )

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        assert channel.id in result.channel_memories
        ch_mem = result.channel_memories[channel.id]
        assert ch_mem.long_term_memory is None
        assert ch_mem.short_term_memory == "channel short-term only"

    @pytest.mark.asyncio
    async def test_fetches_messages_from_repository(
        self,
        mock_memory_repository: Mock,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        persona_config: PersonaConfig,
        channel: Channel,
        user: User,
    ) -> None:
        """Test that messages are fetched from message repository."""
        messages = [
            Message(
                id="1",
                channel=channel,
                user=user,
                text="Hello",
                timestamp=datetime.now(timezone.utc),
                thread_ts=None,
                mentions=[],
            ),
        ]
        mock_message_repository.find_all_in_channel = AsyncMock(return_value=messages)

        result = await build_context_with_memory(
            memory_repository=mock_memory_repository,
            message_repository=mock_message_repository,
            channel_repository=mock_channel_repository,
            channel=channel,
            persona=persona_config,
        )

        mock_message_repository.find_all_in_channel.assert_awaited_once_with(
            channel_id=channel.id,
            limit=20,
        )
        assert result.conversation_history.get_all_messages() == messages


def create_test_memo(
    content: str = "Test memo",
    priority: int = 3,
    tags: list[str] | None = None,
    detail: str | None = None,
) -> Memo:
    """Create a test Memo instance."""
    now = datetime.now(timezone.utc)
    return Memo(
        id=uuid4(),
        content=content,
        priority=priority,
        tags=tags or [],
        detail=detail,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_memo_repository() -> Mock:
    """Create mock memo repository."""
    repo = Mock()
    repo.find_by_priority_gte = AsyncMock(return_value=[])
    repo.find_recent = AsyncMock(return_value=[])
    return repo


class TestGetMemosForContext:
    """Tests for get_memos_for_context function."""

    @pytest.mark.asyncio
    async def test_returns_empty_lists_when_no_memos(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test returns empty lists when no memos exist."""
        mock_memo_repository.find_by_priority_gte = AsyncMock(return_value=[])
        mock_memo_repository.find_recent = AsyncMock(return_value=[])

        high_priority, recent = await get_memos_for_context(mock_memo_repository)

        assert high_priority == []
        assert recent == []

    @pytest.mark.asyncio
    async def test_returns_high_priority_memos(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test returns high priority memos (priority >= 4)."""
        memos = [
            create_test_memo("Important", priority=5),
            create_test_memo("Also important", priority=4),
        ]
        mock_memo_repository.find_by_priority_gte = AsyncMock(return_value=memos)

        high_priority, recent = await get_memos_for_context(mock_memo_repository)

        assert len(high_priority) == 2
        assert high_priority[0].priority == 5
        mock_memo_repository.find_by_priority_gte.assert_awaited_once_with(4, limit=20)

    @pytest.mark.asyncio
    async def test_returns_recent_memos_excluding_duplicates(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test recent memos excludes high priority memos."""
        # Create memos with specific IDs for duplicate detection
        high_priority_memo = create_test_memo("Important", priority=5)
        recent_only_memo = create_test_memo("Recent only", priority=3)

        mock_memo_repository.find_by_priority_gte = AsyncMock(
            return_value=[high_priority_memo]
        )
        # Recent includes both the high priority memo and a new one
        mock_memo_repository.find_recent = AsyncMock(
            return_value=[high_priority_memo, recent_only_memo]
        )

        high_priority, recent = await get_memos_for_context(mock_memo_repository)

        # High priority should have 1 memo
        assert len(high_priority) == 1
        # Recent should only have the non-duplicate memo
        assert len(recent) == 1
        assert recent[0].id == recent_only_memo.id

    @pytest.mark.asyncio
    async def test_returns_empty_recent_when_all_are_high_priority(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test recent is empty when all recent memos are high priority."""
        high_priority_memo = create_test_memo("Important", priority=5)

        mock_memo_repository.find_by_priority_gte = AsyncMock(
            return_value=[high_priority_memo]
        )
        mock_memo_repository.find_recent = AsyncMock(return_value=[high_priority_memo])

        high_priority, recent = await get_memos_for_context(mock_memo_repository)

        assert len(high_priority) == 1
        assert recent == []

    @pytest.mark.asyncio
    async def test_high_priority_limit_is_20(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test high priority memo limit is 20."""
        await get_memos_for_context(mock_memo_repository)

        mock_memo_repository.find_by_priority_gte.assert_awaited_once_with(4, limit=20)

    @pytest.mark.asyncio
    async def test_recent_limit_is_5(
        self,
        mock_memo_repository: Mock,
    ) -> None:
        """Test recent memo limit is 5."""
        await get_memos_for_context(mock_memo_repository)

        mock_memo_repository.find_recent.assert_awaited_once_with(limit=5)
