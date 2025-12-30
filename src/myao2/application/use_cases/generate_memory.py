"""GenerateMemoryUseCase for generating workspace/channel/thread memories."""

import logging
from datetime import datetime, timedelta, timezone

from myao2.config.models import MemoryConfig, PersonaConfig
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import (
    MemoryScope,
    MemoryType,
    create_memory,
    make_thread_scope_id,
)
from myao2.domain.entities.message import Message
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
        channel_memories = await self.generate_channel_memories()

        if not channel_memories:
            logger.info("No channels found, skipping workspace memory generation")
            return

        # Generate workspace memories
        await self.generate_workspace_memory(channel_memories)

        # Generate thread memories for active threads
        channels = await self._channel_repository.find_all()
        for channel in channels:
            try:
                active_threads = await self._get_active_threads(channel.id)
                channel_memory = channel_memories.get(channel.id)

                for thread_ts in active_threads:
                    try:
                        await self.generate_thread_memory(
                            channel.id, thread_ts, channel_memory
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

    async def generate_channel_memories(self) -> dict[str, ChannelMemory]:
        """Generate memories for all channels.

        Returns:
            Map of channel_id to ChannelMemory.
        """
        logger.info("Generating channel memories")
        channel_memories: dict[str, ChannelMemory] = {}

        channels = await self._channel_repository.find_all()
        for channel in channels:
            try:
                # Generate short-term memory
                short_term = await self._generate_channel_short_term_memory(
                    channel.id, channel.name
                )

                # Generate long-term memory
                long_term = await self._generate_channel_long_term_memory(
                    channel.id, channel.name, short_term
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

        return channel_memories

    async def generate_workspace_memory(
        self,
        channel_memories: dict[str, ChannelMemory],
    ) -> None:
        """Generate workspace memory.

        Args:
            channel_memories: Channel memories to integrate.
        """
        logger.info("Generating workspace memory")

        # Get existing long-term memory
        existing_long_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.WORKSPACE, self.WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
        )
        existing_long_term_content = (
            existing_long_term.content if existing_long_term else None
        )

        # Create empty conversation_history
        empty_channel_messages = ChannelMessages(
            channel_id="",
            channel_name="",
        )

        # Generate short-term memory
        context_short = Context(
            persona=self._persona,
            conversation_history=empty_channel_messages,
            channel_memories=channel_memories,
        )
        short_term_content = await self._memory_summarizer.summarize(
            context=context_short,
            scope=MemoryScope.WORKSPACE,
            memory_type=MemoryType.SHORT_TERM,
        )

        # Generate long-term memory
        context_long = Context(
            persona=self._persona,
            conversation_history=empty_channel_messages,
            channel_memories=channel_memories,
        )
        long_term_content = await self._memory_summarizer.summarize(
            context=context_long,
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
        channel_id: str,
        thread_ts: str,
        channel_memory: ChannelMemory | None = None,
    ) -> None:
        """Generate thread memory.

        Args:
            channel_id: Channel ID.
            thread_ts: Thread parent message timestamp.
            channel_memory: Channel memory for auxiliary information.
        """
        # Get thread messages
        messages = await self._message_repository.find_by_thread(
            channel_id=channel_id,
            thread_ts=thread_ts,
        )

        if not messages:
            return

        # Get channel info
        channel = await self._channel_repository.find_by_id(channel_id)
        channel_name = channel.name if channel else ""

        # Build ChannelMessages with thread messages
        channel_messages = ChannelMessages(
            channel_id=channel_id,
            channel_name=channel_name,
            thread_messages={thread_ts: messages},
        )

        # Build Context
        channel_memories: dict[str, ChannelMemory] = {}
        if channel_memory:
            channel_memories[channel_id] = channel_memory

        context = Context(
            persona=self._persona,
            conversation_history=channel_messages,
            target_thread_ts=thread_ts,
            channel_memories=channel_memories,
        )

        # Generate short-term memory
        content = await self._memory_summarizer.summarize(
            context=context,
            scope=MemoryScope.THREAD,
            memory_type=MemoryType.SHORT_TERM,
        )

        if content:
            scope_id = make_thread_scope_id(channel_id, thread_ts)
            await self._save_memory(
                MemoryScope.THREAD,
                scope_id,
                MemoryType.SHORT_TERM,
                content,
            )

    async def _generate_channel_short_term_memory(
        self,
        channel_id: str,
        channel_name: str,
    ) -> str | None:
        """Generate channel short-term memory.

        Args:
            channel_id: Channel ID.
            channel_name: Channel name.

        Returns:
            Generated memory content or None.
        """
        # Get messages within time window
        since = datetime.now(timezone.utc) - timedelta(
            hours=self._config.short_term_window_hours
        )
        messages = await self._message_repository.find_by_channel_since(
            channel_id=channel_id,
            since=since,
            limit=self.DEFAULT_MESSAGE_LIMIT,
        )

        if not messages:
            return None

        # Build ChannelMessages
        channel_messages = self._build_channel_messages(
            channel_id, channel_name, messages
        )

        # Build Context
        context = Context(
            persona=self._persona,
            conversation_history=channel_messages,
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
                channel_id,
                MemoryType.SHORT_TERM,
                content,
            )

        return content or None

    async def _generate_channel_long_term_memory(
        self,
        channel_id: str,
        channel_name: str,
        short_term_memory: str | None,
    ) -> str | None:
        """Generate channel long-term memory.

        Args:
            channel_id: Channel ID.
            channel_name: Channel name.
            short_term_memory: Short-term memory to merge.

        Returns:
            Generated memory content or None.
        """
        if not short_term_memory:
            # Keep existing long-term memory when no short-term
            existing = await self._memory_repository.find_by_scope_and_type(
                MemoryScope.CHANNEL, channel_id, MemoryType.LONG_TERM
            )
            return existing.content if existing else None

        # Get existing long-term memory
        existing = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel_id, MemoryType.LONG_TERM
        )
        existing_content = existing.content if existing else None

        # Build Context with short-term memory in channel_memories
        channel_messages = ChannelMessages(
            channel_id=channel_id,
            channel_name=channel_name,
        )
        channel_memory = ChannelMemory(
            channel_id=channel_id,
            channel_name=channel_name,
            short_term_memory=short_term_memory,
        )
        context = Context(
            persona=self._persona,
            conversation_history=channel_messages,
            channel_memories={channel_id: channel_memory},
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
                channel_id,
                MemoryType.LONG_TERM,
                content,
            )

        return content or None

    def _build_channel_messages(
        self,
        channel_id: str,
        channel_name: str,
        messages: list[Message],
    ) -> ChannelMessages:
        """Build ChannelMessages from message list.

        Args:
            channel_id: Channel ID.
            channel_name: Channel name.
            messages: List of messages.

        Returns:
            ChannelMessages instance.
        """
        top_level: list[Message] = []
        threads: dict[str, list[Message]] = {}

        for msg in messages:
            if msg.thread_ts:
                if msg.thread_ts not in threads:
                    threads[msg.thread_ts] = []
                threads[msg.thread_ts].append(msg)
            else:
                top_level.append(msg)

        return ChannelMessages(
            channel_id=channel_id,
            channel_name=channel_name,
            top_level_messages=top_level,
            thread_messages=threads,
        )

    async def _get_active_threads(self, channel_id: str) -> list[str]:
        """Get active threads in a channel.

        Returns thread timestamps that have messages within the short-term window.

        Args:
            channel_id: Channel ID.

        Returns:
            List of thread timestamps.
        """
        since = datetime.now(timezone.utc) - timedelta(
            hours=self._config.short_term_window_hours
        )
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
    ) -> None:
        """Save memory to repository.

        Args:
            scope: Memory scope.
            scope_id: Scope-specific ID.
            memory_type: Memory type.
            content: Memory content.
        """
        if not content:
            return

        memory = create_memory(
            scope=scope,
            scope_id=scope_id,
            memory_type=memory_type,
            content=content,
            source_message_count=0,
        )
        await self._memory_repository.save(memory)
