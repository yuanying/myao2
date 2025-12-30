"""Memory summarizer protocol."""

from typing import Protocol

from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType


class MemorySummarizer(Protocol):
    """Memory summarization service protocol.

    Generates memory summaries based on context and scope.
    The behavior differs depending on the scope:

    - THREAD: Summarizes messages from context.target_thread_ts
    - CHANNEL: Summarizes all messages (top-level + threads) from
      context.conversation_history
    - WORKSPACE: Integrates channel memories from context.channel_memories
    """

    async def summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        """Generate memory summary from context.

        Args:
            context: Conversation context containing messages and memories.
            scope: Memory scope determining what to summarize:
                - THREAD: Uses messages from target_thread_ts
                - CHANNEL: Uses all messages from conversation_history
                - WORKSPACE: Integrates channel_memories
            memory_type: Type of memory (long-term or short-term).
            existing_memory: Existing memory for incremental update
                (used only for long-term memory).

        Returns:
            Generated memory text. Returns empty string or existing_memory
            if there's nothing to summarize.
        """
        ...
