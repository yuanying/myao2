"""Tests for GenerateMemoryUseCase."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.config import MemoryConfig, PersonaConfig
from myao2.domain.entities import (
    Channel,
    Memory,
    MemoryScope,
    MemoryType,
    Message,
    User,
)
from myao2.domain.entities.channel_messages import ChannelMemory
from myao2.domain.entities.context import Context


@pytest.fixture
def mock_memory_repository() -> Mock:
    """Create mock memory repository."""
    repo = Mock()
    repo.save = AsyncMock()
    repo.find_by_scope_and_type = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_message_repository() -> Mock:
    """Create mock message repository."""
    repo = Mock()
    repo.find_by_channel_since = AsyncMock(return_value=[])
    repo.find_by_thread = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_channel_repository() -> Mock:
    """Create mock channel repository."""
    repo = Mock()
    repo.find_all = AsyncMock(return_value=[])
    repo.find_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_memory_summarizer() -> Mock:
    """Create mock memory summarizer."""
    summarizer = Mock()
    summarizer.summarize = AsyncMock(return_value="summary")
    return summarizer


@pytest.fixture
def memory_config() -> MemoryConfig:
    """Create test memory config."""
    return MemoryConfig(
        database_path=":memory:",
        short_term_window_hours=24,
    )


@pytest.fixture
def persona_config() -> PersonaConfig:
    """Create test persona config."""
    return PersonaConfig(
        name="TestBot",
        system_prompt="You are a test bot.",
    )


@pytest.fixture
def use_case(
    mock_memory_repository: Mock,
    mock_message_repository: Mock,
    mock_channel_repository: Mock,
    mock_memory_summarizer: Mock,
    memory_config: MemoryConfig,
    persona_config: PersonaConfig,
) -> GenerateMemoryUseCase:
    """Create use case instance."""
    return GenerateMemoryUseCase(
        memory_repository=mock_memory_repository,
        message_repository=mock_message_repository,
        channel_repository=mock_channel_repository,
        memory_summarizer=mock_memory_summarizer,
        config=memory_config,
        persona=persona_config,
    )


@pytest.fixture
def channel() -> Channel:
    """Create test channel."""
    return Channel(id="C123", name="general")


@pytest.fixture
def user() -> User:
    """Create test user."""
    return User(id="U123", name="Test User")


@pytest.fixture
def timestamp() -> datetime:
    """Create test timestamp."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_message(
    channel: Channel,
    user: User,
    timestamp: datetime,
    message_id: str = "M001",
    text: str = "Hello",
    thread_ts: str | None = None,
) -> Message:
    """Helper to create test messages."""
    return Message(
        id=message_id,
        channel=channel,
        user=user,
        text=text,
        timestamp=timestamp,
        thread_ts=thread_ts,
    )


class TestGenerateMemoryUseCaseExecute:
    """Tests for execute method."""

    async def test_no_channels_does_nothing(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_memory_summarizer: Mock,
    ) -> None:
        """Test that nothing happens when no channels exist."""
        mock_channel_repository.find_all.return_value = []

        await use_case.execute()

        mock_channel_repository.find_all.assert_awaited_once()
        mock_memory_summarizer.summarize.assert_not_awaited()

    async def test_generates_all_memories_in_order(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that all memories are generated in correct order."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        # Track call order
        call_order: list[tuple[MemoryScope, MemoryType]] = []

        async def track_summarize(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            call_order.append((scope, memory_type))
            return "summary"

        mock_memory_summarizer.summarize.side_effect = track_summarize

        await use_case.execute()

        # Verify order: channel short -> channel long -> ws short -> ws long
        expected_order = [
            (MemoryScope.CHANNEL, MemoryType.SHORT_TERM),
            (MemoryScope.CHANNEL, MemoryType.LONG_TERM),
            (MemoryScope.WORKSPACE, MemoryType.SHORT_TERM),
            (MemoryScope.WORKSPACE, MemoryType.LONG_TERM),
        ]
        assert call_order == expected_order

    async def test_generates_thread_memories_for_active_threads(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread memories are generated for active threads."""
        mock_channel_repository.find_all.return_value = [channel]
        mock_channel_repository.find_by_id.return_value = channel

        # Messages with a thread
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M001", "Parent"),
            create_message(
                channel, user, timestamp, "M002", "Reply", thread_ts=thread_ts
            ),
        ]
        mock_message_repository.find_by_channel_since.return_value = messages
        mock_message_repository.find_by_thread.return_value = [messages[1]]

        # Track thread memory calls
        thread_calls: list[MemoryScope] = []

        async def track_summarize(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            if scope == MemoryScope.THREAD:
                thread_calls.append(scope)
            return "summary"

        mock_memory_summarizer.summarize.side_effect = track_summarize

        await use_case.execute()

        # Thread memory should be generated
        assert len(thread_calls) == 1
        mock_message_repository.find_by_thread.assert_awaited_once_with(
            channel_id=channel.id,
            thread_ts=thread_ts,
        )

    async def test_continues_on_channel_error(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        user: User,
        timestamp: datetime,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that processing continues when one channel fails."""
        channel1 = Channel(id="C001", name="channel1")
        channel2 = Channel(id="C002", name="channel2")
        mock_channel_repository.find_all.return_value = [channel1, channel2]

        # First channel throws error, second succeeds
        channel_call_count = {"C001": 0, "C002": 0}

        async def find_messages(
            channel_id: str, since: datetime, limit: int
        ) -> list[Message]:
            channel_call_count[channel_id] += 1
            if channel_id == "C001":
                raise RuntimeError("LLM Error")
            return [create_message(channel2, user, timestamp)]

        mock_message_repository.find_by_channel_since.side_effect = find_messages

        with caplog.at_level(logging.ERROR):
            await use_case.execute()

        # Both channels should be attempted at least once
        assert channel_call_count["C001"] >= 1
        assert channel_call_count["C002"] >= 1
        # Error should be logged
        assert "Error generating memory for channel" in caplog.text


class TestGenerateChannelMemories:
    """Tests for generate_channel_memories method."""

    async def test_generates_short_and_long_term_memories(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that both short and long term memories are generated."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        result = await use_case.generate_channel_memories()

        # Should return ChannelMemory for the channel
        assert channel.id in result
        assert result[channel.id].channel_id == channel.id
        assert result[channel.id].channel_name == channel.name
        assert result[channel.id].short_term_memory == "summary"
        assert result[channel.id].long_term_memory == "summary"

    async def test_no_messages_returns_empty_memories(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
    ) -> None:
        """Test that empty messages result in no memory generation."""
        mock_channel_repository.find_all.return_value = [channel]
        mock_message_repository.find_by_channel_since.return_value = []

        result = await use_case.generate_channel_memories()

        # No memory should be generated
        assert channel.id in result
        assert result[channel.id].short_term_memory is None
        assert result[channel.id].long_term_memory is None
        mock_memory_summarizer.summarize.assert_not_awaited()

    async def test_short_term_memory_context_has_messages(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that short term memory context includes messages."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        captured_contexts: list[tuple[Context, MemoryScope, MemoryType]] = []

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            captured_contexts.append((context, scope, memory_type))
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_channel_memories()

        # Find short term memory call
        short_term_call = next(
            (c for c in captured_contexts if c[2] == MemoryType.SHORT_TERM), None
        )
        assert short_term_call is not None
        context = short_term_call[0]

        # conversation_history should have messages
        assert context.conversation_history.channel_id == channel.id
        assert len(context.conversation_history.top_level_messages) == 1
        assert context.conversation_history.top_level_messages[0].text == "Hello"

    async def test_long_term_memory_context_has_short_term_in_channel_memories(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that long term context includes short term in channel_memories."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        captured_contexts: list[tuple[Context, MemoryScope, MemoryType]] = []

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            captured_contexts.append((context, scope, memory_type))
            if memory_type == MemoryType.SHORT_TERM:
                return "short_term_summary"
            return "long_term_summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_channel_memories()

        # Find long term memory call
        long_term_call = next(
            (c for c in captured_contexts if c[2] == MemoryType.LONG_TERM), None
        )
        assert long_term_call is not None
        context = long_term_call[0]

        # channel_memories should have short term memory
        assert channel.id in context.channel_memories
        assert (
            context.channel_memories[channel.id].short_term_memory
            == "short_term_summary"
        )

    async def test_long_term_memory_uses_existing_memory(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that long term memory generation includes existing memory."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        # Set up existing long term memory
        existing_memory = Memory(
            scope=MemoryScope.CHANNEL,
            scope_id=channel.id,
            memory_type=MemoryType.LONG_TERM,
            content="existing long term memory",
            created_at=timestamp,
            updated_at=timestamp,
            source_message_count=5,
        )
        mock_memory_repository.find_by_scope_and_type.return_value = existing_memory

        captured_existing: list[str | None] = []

        async def capture_existing(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            if memory_type == MemoryType.LONG_TERM:
                captured_existing.append(existing_memory)
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_existing

        await use_case.generate_channel_memories()

        # existing_memory should be passed for long term generation
        assert len(captured_existing) == 1
        assert captured_existing[0] == "existing long term memory"

    async def test_no_short_term_keeps_existing_long_term(
        self,
        use_case: GenerateMemoryUseCase,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        channel: Channel,
        timestamp: datetime,
    ) -> None:
        """Test that existing long term memory is kept when no new short term."""
        mock_channel_repository.find_all.return_value = [channel]
        mock_message_repository.find_by_channel_since.return_value = []

        # Set up existing long term memory
        existing_memory = Memory(
            scope=MemoryScope.CHANNEL,
            scope_id=channel.id,
            memory_type=MemoryType.LONG_TERM,
            content="existing content",
            created_at=timestamp,
            updated_at=timestamp,
            source_message_count=5,
        )
        mock_memory_repository.find_by_scope_and_type.return_value = existing_memory

        result = await use_case.generate_channel_memories()

        # Existing long term memory should be preserved
        assert result[channel.id].long_term_memory == "existing content"
        mock_memory_summarizer.summarize.assert_not_awaited()


class TestGenerateWorkspaceMemory:
    """Tests for generate_workspace_memory method."""

    async def test_generates_workspace_memories(
        self,
        use_case: GenerateMemoryUseCase,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
    ) -> None:
        """Test that workspace memories are generated."""
        channel_memories = {
            "C001": ChannelMemory(
                channel_id="C001",
                channel_name="general",
                short_term_memory="channel short term",
                long_term_memory="channel long term",
            )
        }

        await use_case.generate_workspace_memory(channel_memories)

        # Should call summarize twice (short and long term)
        assert mock_memory_summarizer.summarize.await_count == 2
        # Should save two memories
        assert mock_memory_repository.save.await_count == 2

    async def test_workspace_context_has_channel_memories(
        self,
        use_case: GenerateMemoryUseCase,
        mock_memory_summarizer: Mock,
    ) -> None:
        """Test that workspace context includes channel memories."""
        channel_memories = {
            "C001": ChannelMemory(
                channel_id="C001",
                channel_name="general",
                short_term_memory="channel short",
                long_term_memory="channel long",
            )
        }

        captured_contexts: list[tuple[Context, MemoryScope, MemoryType]] = []

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            captured_contexts.append((context, scope, memory_type))
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_workspace_memory(channel_memories)

        # All calls should have channel_memories set
        for context, scope, _ in captured_contexts:
            assert scope == MemoryScope.WORKSPACE
            assert "C001" in context.channel_memories
            assert context.channel_memories["C001"].short_term_memory == "channel short"

    async def test_workspace_long_term_uses_existing_memory(
        self,
        use_case: GenerateMemoryUseCase,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        timestamp: datetime,
    ) -> None:
        """Test that workspace long term uses existing memory."""
        existing_memory = Memory(
            scope=MemoryScope.WORKSPACE,
            scope_id="default",
            memory_type=MemoryType.LONG_TERM,
            content="existing workspace memory",
            created_at=timestamp,
            updated_at=timestamp,
            source_message_count=10,
        )
        mock_memory_repository.find_by_scope_and_type.return_value = existing_memory

        captured_existing: list[str | None] = []

        async def capture_existing(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            if memory_type == MemoryType.LONG_TERM:
                captured_existing.append(existing_memory)
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_existing

        await use_case.generate_workspace_memory({})

        assert captured_existing[0] == "existing workspace memory"


class TestGenerateThreadMemory:
    """Tests for generate_thread_memory method."""

    async def test_generates_thread_short_term_memory(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_summarizer: Mock,
        mock_memory_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread short term memory is generated."""
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M002", "Reply", thread_ts)
        ]
        mock_message_repository.find_by_thread.return_value = messages
        mock_channel_repository.find_by_id.return_value = channel

        await use_case.generate_thread_memory(channel.id, thread_ts)

        mock_memory_summarizer.summarize.assert_awaited_once()
        call_args = mock_memory_summarizer.summarize.call_args
        assert call_args.kwargs["scope"] == MemoryScope.THREAD
        assert call_args.kwargs["memory_type"] == MemoryType.SHORT_TERM

    async def test_no_messages_does_not_generate(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
    ) -> None:
        """Test that no memory is generated when no messages."""
        mock_message_repository.find_by_thread.return_value = []

        await use_case.generate_thread_memory("C123", "1234567890.123456")

        mock_memory_summarizer.summarize.assert_not_awaited()

    async def test_thread_context_has_target_thread_ts(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread context has target_thread_ts set."""
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M002", "Reply", thread_ts)
        ]
        mock_message_repository.find_by_thread.return_value = messages
        mock_channel_repository.find_by_id.return_value = channel

        captured_context: Context | None = None

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            nonlocal captured_context
            captured_context = context
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_thread_memory(channel.id, thread_ts)

        assert captured_context is not None
        assert captured_context.target_thread_ts == thread_ts

    async def test_thread_context_has_channel_memory_when_provided(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread context includes channel memory when provided."""
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M002", "Reply", thread_ts)
        ]
        mock_message_repository.find_by_thread.return_value = messages
        mock_channel_repository.find_by_id.return_value = channel

        channel_memory = ChannelMemory(
            channel_id=channel.id,
            channel_name=channel.name,
            short_term_memory="channel short",
            long_term_memory="channel long",
        )

        captured_context: Context | None = None

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            nonlocal captured_context
            captured_context = context
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_thread_memory(channel.id, thread_ts, channel_memory)

        assert captured_context is not None
        assert channel.id in captured_context.channel_memories
        assert (
            captured_context.channel_memories[channel.id].short_term_memory
            == "channel short"
        )

    async def test_thread_context_conversation_history_has_thread_messages(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        mock_channel_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that thread context has thread messages in conversation_history."""
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M002", "Reply", thread_ts)
        ]
        mock_message_repository.find_by_thread.return_value = messages
        mock_channel_repository.find_by_id.return_value = channel

        captured_context: Context | None = None

        async def capture_context(
            context: Context,
            scope: MemoryScope,
            memory_type: MemoryType,
            existing_memory: str | None = None,
        ) -> str:
            nonlocal captured_context
            captured_context = context
            return "summary"

        mock_memory_summarizer.summarize.side_effect = capture_context

        await use_case.generate_thread_memory(channel.id, thread_ts)

        assert captured_context is not None
        assert thread_ts in captured_context.conversation_history.thread_messages
        assert (
            len(captured_context.conversation_history.thread_messages[thread_ts]) == 1
        )


class TestBuildChannelMessages:
    """Tests for _build_channel_messages helper."""

    async def test_separates_top_level_and_thread_messages(
        self,
        use_case: GenerateMemoryUseCase,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that messages are correctly categorized."""
        thread_ts = "1234567890.123456"
        messages = [
            create_message(channel, user, timestamp, "M001", "Top level"),
            create_message(channel, user, timestamp, "M002", "Reply", thread_ts),
            create_message(
                channel, user, timestamp, "M003", "Another reply", thread_ts
            ),
        ]

        result = use_case._build_channel_messages(channel.id, channel.name, messages)

        assert len(result.top_level_messages) == 1
        assert result.top_level_messages[0].text == "Top level"
        assert thread_ts in result.thread_messages
        assert len(result.thread_messages[thread_ts]) == 2


class TestGetActiveThreads:
    """Tests for _get_active_threads helper."""

    async def test_returns_unique_thread_roots(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that unique thread roots are returned."""
        thread_ts1 = "1234567890.123456"
        thread_ts2 = "1234567890.654321"
        messages = [
            create_message(channel, user, timestamp, "M001", "Top level"),
            create_message(channel, user, timestamp, "M002", "Reply1", thread_ts1),
            create_message(channel, user, timestamp, "M003", "Reply2", thread_ts1),
            create_message(channel, user, timestamp, "M004", "Reply3", thread_ts2),
        ]
        mock_message_repository.find_by_channel_since.return_value = messages

        result = await use_case._get_active_threads(channel.id)

        assert set(result) == {thread_ts1, thread_ts2}

    async def test_returns_empty_when_no_threads(
        self,
        use_case: GenerateMemoryUseCase,
        mock_message_repository: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that empty list is returned when no threads."""
        messages = [
            create_message(channel, user, timestamp, "M001", "Top level 1"),
            create_message(channel, user, timestamp, "M002", "Top level 2"),
        ]
        mock_message_repository.find_by_channel_since.return_value = messages

        result = await use_case._get_active_threads(channel.id)

        assert result == []


class TestSaveMemory:
    """Tests for memory saving."""

    async def test_saves_memory_with_correct_attributes(
        self,
        use_case: GenerateMemoryUseCase,
        mock_memory_repository: Mock,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that memory is saved with correct attributes."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages

        await use_case.generate_channel_memories()

        # Verify save was called with Memory objects
        assert mock_memory_repository.save.await_count >= 1
        saved_memory = mock_memory_repository.save.call_args_list[0][0][0]
        assert isinstance(saved_memory, Memory)
        assert saved_memory.scope == MemoryScope.CHANNEL
        assert saved_memory.scope_id == channel.id

    async def test_does_not_save_empty_content(
        self,
        use_case: GenerateMemoryUseCase,
        mock_memory_repository: Mock,
        mock_channel_repository: Mock,
        mock_message_repository: Mock,
        mock_memory_summarizer: Mock,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that empty content is not saved."""
        mock_channel_repository.find_all.return_value = [channel]
        messages = [create_message(channel, user, timestamp)]
        mock_message_repository.find_by_channel_since.return_value = messages
        mock_memory_summarizer.summarize.return_value = ""

        await use_case.generate_channel_memories()

        # No save should be called when content is empty
        mock_memory_repository.save.assert_not_awaited()
