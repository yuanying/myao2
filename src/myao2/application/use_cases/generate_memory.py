"""GenerateMemoryUseCase for generating workspace/channel/thread memories."""

import logging
from datetime import datetime, timedelta, timezone

from myao2.application.use_cases.helpers import build_context_with_memory
from myao2.config.models import MemoryConfig, PersonaConfig
from myao2.domain.entities.channel import Channel
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import (
    MemoryScope,
    MemoryType,
    create_memory,
    make_thread_scope_id,
)
from myao2.domain.repositories.channel_repository import ChannelRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.repositories.message_repository import MessageRepository
from myao2.domain.services.memory_summarizer import MemorySummarizer

logger = logging.getLogger(__name__)


class GenerateMemoryUseCase:
    """Generate memory use case.

    Generates and updates workspace, channel, and thread memories.
    Passes Context to MemorySummarizer for memory generation.
    """

    WORKSPACE_SCOPE_ID = "default"
    DEFAULT_MESSAGE_LIMIT = 1000

    def __init__(
        self,
        memory_repository: MemoryRepository,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        memory_summarizer: MemorySummarizer,
        config: MemoryConfig,
        persona: PersonaConfig,
    ) -> None:
        """Initialize GenerateMemoryUseCase.

        Args:
            memory_repository: Repository for memory persistence.
            message_repository: Repository for message access.
            channel_repository: Repository for channel access.
            memory_summarizer: Service for generating memory summaries.
            config: Memory configuration.
            persona: Persona configuration.
        """
        self._memory_repository = memory_repository
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._memory_summarizer = memory_summarizer
        self._config = config
        self._persona = persona

    def _get_short_term_window_start(self) -> datetime:
        """Get the start time of the short-term window.

        Returns:
            datetime marking the start of the short-term window.
        """
        return datetime.now(timezone.utc) - timedelta(
            hours=self._config.short_term_window_hours
        )

    async def execute(self) -> None:
        """Generate all memories.

        Processing order (based on dependencies):
        1. Generate all channel short-term memories (from messages)
        2. Generate all channel long-term memories (merge short-term)
        3. Generate workspace short-term memory (integrate channel short-term)
        4. Generate workspace long-term memory (integrate channel long-term)
        5. Generate active thread short-term memories
        """
        logger.info("Starting memory generation")

        # Generate channel memories
        (
            channel_memories,
            any_channel_regenerated,
        ) = await self.generate_channel_memories()

        if not channel_memories:
            logger.info("No channels found, skipping workspace memory generation")
            return

        # Generate workspace memories
        await self.generate_workspace_memory(any_channel_regenerated)

        # Generate thread memories for active threads
        channels = await self._channel_repository.find_all()
        for channel in channels:
            try:
                active_threads = await self._get_active_threads(channel.id)
                channel_memory = channel_memories.get(channel.id)

                for thread_ts in active_threads:
                    try:
                        await self.generate_thread_memory(
                            channel, thread_ts, channel_memory
                        )
                    except Exception:
                        logger.exception(
                            "Error generating memory for thread %s in channel %s",
                            thread_ts,
                            channel.id,
                        )
            except Exception:
                logger.exception("Error processing threads for channel %s", channel.id)

        logger.info("Memory generation completed")

    async def generate_channel_memories(
        self,
    ) -> tuple[dict[str, ChannelMemory], bool]:
        """Generate memories for all channels.

        Returns:
            Tuple of (channel_memories, any_channel_regenerated).
            - channel_memories: Map of channel_id to ChannelMemory.
            - any_channel_regenerated: True if any channel memory was regenerated.
        """
        logger.info("Generating channel memories")
        channel_memories: dict[str, ChannelMemory] = {}
        any_channel_regenerated = False

        channels = await self._channel_repository.find_all()
        for channel in channels:
            try:
                # Generate short-term memory
                (
                    short_term,
                    short_term_regenerated,
                ) = await self._generate_channel_short_term_memory(channel)

                # Track if any channel was regenerated
                if short_term_regenerated:
                    any_channel_regenerated = True

                # Generate long-term memory
                long_term = await self._generate_channel_long_term_memory(
                    channel, short_term, short_term_regenerated
                )

                # Build ChannelMemory
                channel_memory = ChannelMemory(
                    channel_id=channel.id,
                    channel_name=channel.name,
                    short_term_memory=short_term,
                    long_term_memory=long_term,
                )
                channel_memories[channel.id] = channel_memory

                logger.debug(
                    "Generated memory for channel %s: short=%s, long=%s",
                    channel.id,
                    short_term is not None,
                    long_term is not None,
                )
            except Exception:
                logger.exception("Error generating memory for channel %s", channel.id)
                # Add empty memory to allow workspace generation to continue
                channel_memories[channel.id] = ChannelMemory(
                    channel_id=channel.id,
                    channel_name=channel.name,
                )

        return channel_memories, any_channel_regenerated

    async def generate_workspace_memory(
        self,
        any_channel_regenerated: bool = True,
    ) -> None:
        """Generate workspace memory using shared Context builder.

        Args:
            any_channel_regenerated: Whether any channel memory was regenerated.
                If False, skip generation and keep existing memory.
        """
        logger.info("Generating workspace memory")

        # Skip if no channel was regenerated
        if not any_channel_regenerated:
            logger.debug(
                "Skipping workspace memory generation (no channel regenerated)"
            )
            return

        # Get existing long-term memory
        existing_long_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.WORKSPACE, self.WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
        )
        existing_long_term_content = (
            existing_long_term.content if existing_long_term else None
        )

        # Build Context using shared function (channel=None for workspace scope)
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            persona=self._persona,
        )

        # Generate short-term memory
        short_term_content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
        )

        # Generate long-term memory
        long_term_content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing_long_term_content,
        )

        # Save memories
        await self._save_memory(
            MemoryScope.WORKSPACE,
            self.WORKSPACE_SCOPE_ID,
            MemoryType.SHORT_TERM,
            short_term_content,
        )
        await self._save_memory(
            MemoryScope.WORKSPACE,
            self.WORKSPACE_SCOPE_ID,
            MemoryType.LONG_TERM,
            long_term_content,
        )

    async def generate_thread_memory(
        self,
        channel: Channel,
        thread_ts: str,
        channel_memory: ChannelMemory | None = None,
    ) -> None:
        """Generate thread memory using shared Context builder.

        Args:
            channel: Channel entity.
            thread_ts: Thread parent message timestamp.
            channel_memory: Channel memory for auxiliary information.
        """
        # Get thread messages to check if generation is needed
        messages = await self._message_repository.find_by_thread(
            channel_id=channel.id,
            thread_ts=thread_ts,
        )

        if not messages:
            return

        # Get latest message ts
        latest_message_ts = max(msg.id for msg in messages)

        # Check existing memory for incremental update
        scope_id = make_thread_scope_id(channel.id, thread_ts)
        existing = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.THREAD, scope_id, MemoryType.SHORT_TERM
        )

        # Skip if no new messages
        if existing and existing.source_latest_message_ts == latest_message_ts:
            logger.debug(
                "Skipping thread %s memory generation (no new messages)",
                thread_ts,
            )
            return

        # Build Context using shared function
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=channel,
            persona=self._persona,
            target_thread_ts=thread_ts,
            message_limit=self.DEFAULT_MESSAGE_LIMIT,
        )

        # Generate short-term memory
        content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        if content:
            await self._save_memory(
                MemoryScope.THREAD,
                scope_id,
                MemoryType.SHORT_TERM,
                content,
                source_message_count=len(messages),
                source_latest_message_ts=latest_message_ts,
            )

    async def _generate_channel_short_term_memory(
        self,
        channel: Channel,
    ) -> tuple[str | None, bool]:
        """Generate channel short-term memory using shared Context builder.

        Args:
            channel: Channel entity.

        Returns:
            Tuple of (content, was_regenerated).
            - content: Generated memory content or None.
            - was_regenerated: True if memory was regenerated, False if skipped.
        """
        since = self._get_short_term_window_start()

        # Get messages within time window to check if generation is needed
        messages = await self._message_repository.find_by_channel_since(
            channel_id=channel.id,
            since=since,
            limit=self.DEFAULT_MESSAGE_LIMIT,
        )

        if not messages:
            return None, False

        # Get latest message ts
        latest_message_ts = max(msg.id for msg in messages)

        # Check existing memory for incremental update
        existing = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.SHORT_TERM
        )

        # Skip if no new messages
        if existing and existing.source_latest_message_ts == latest_message_ts:
            logger.debug(
                "Skipping channel %s short-term memory generation (no new messages)",
                channel.id,
            )
            return existing.content, False

        # Build Context using shared function
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=channel,
            persona=self._persona,
            message_limit=self.DEFAULT_MESSAGE_LIMIT,
            since=since,
        )

        # Generate short-term memory
        content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.SHORT_TERM,
        )

        if content:
            await self._save_memory(
                MemoryScope.CHANNEL,
                channel.id,
                MemoryType.SHORT_TERM,
                content,
                source_message_count=len(messages),
                source_latest_message_ts=latest_message_ts,
            )

        return content or None, True

    async def _generate_channel_long_term_memory(
        self,
        channel: Channel,
        short_term_memory: str | None,
        short_term_regenerated: bool,
    ) -> str | None:
        """Generate channel long-term memory.

        Args:
            channel: Channel entity.
            short_term_memory: Short-term memory to merge.
            short_term_regenerated: Whether short-term memory was regenerated.

        Returns:
            Generated memory content or None.
        """
        # If there's no short-term memory content to merge, keep existing long-term
        if not short_term_memory:
            existing = await self._memory_repository.find_by_scope_and_type(
                MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
            )
            return existing.content if existing else None

        # If short-term memory exists but was not regenerated, keep existing long-term
        if not short_term_regenerated:
            existing = await self._memory_repository.find_by_scope_and_type(
                MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
            )
            return existing.content if existing else None

        # Get existing long-term memory for incremental update
        existing = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
        )
        existing_content = existing.content if existing else None

        # Build Context with short-term memory in channel_memories
        channel_messages = ChannelMessages(
            channel_id=channel.id,
            channel_name=channel.name,
        )
        channel_memory = ChannelMemory(
            channel_id=channel.id,
            channel_name=channel.name,
            short_term_memory=short_term_memory,
        )
        context = Context(
            persona=self._persona,
            conversation_history=channel_messages,
            channel_memories={channel.id: channel_memory},
        )

        # Generate long-term memory
        content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.CHANNEL,
            memory_type=MemoryType.LONG_TERM,
            existing_memory=existing_content,
        )

        if content:
            await self._save_memory(
                MemoryScope.CHANNEL,
                channel.id,
                MemoryType.LONG_TERM,
                content,
            )

        return content or None

    async def _get_active_threads(self, channel_id: str) -> list[str]:
        """Get active threads in a channel.

        Returns thread timestamps that have messages within the short-term window.

        Args:
            channel_id: Channel ID.

        Returns:
            List of thread timestamps.
        """
        since = self._get_short_term_window_start()
        messages = await self._message_repository.find_by_channel_since(
            channel_id=channel_id,
            since=since,
            limit=self.DEFAULT_MESSAGE_LIMIT,
        )

        thread_roots: set[str] = set()
        for msg in messages:
            if msg.thread_ts:
                thread_roots.add(msg.thread_ts)

        return list(thread_roots)

    async def _save_memory(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
        content: str | None,
        source_message_count: int = 0,
        source_latest_message_ts: str | None = None,
    ) -> None:
        """Save memory to repository.

        Args:
            scope: Memory scope.
            scope_id: Scope-specific ID.
            memory_type: Memory type.
            content: Memory content.
            source_message_count: Number of messages used for generation.
            source_latest_message_ts: Latest message timestamp used for generation.
        """
        if not content:
            return

        memory = create_memory(
            scope=scope,
            scope_id=scope_id,
            memory_type=memory_type,
            content=content,
            source_message_count=source_message_count,
            source_latest_message_ts=source_latest_message_ts,
        )
        await self._memory_repository.save(memory)
