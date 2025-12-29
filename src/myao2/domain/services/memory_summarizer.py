"""Memory summarizer protocol."""

from typing import Protocol

from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.domain.entities.message import Message


class MemorySummarizer(Protocol):
    """Memory summarization service protocol.

    Generates memory summaries from message lists.
    """

    async def summarize(
        self,
        messages: list[Message],
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        """Generate memory from message list.

        Args:
            messages: Messages to summarize.
            scope: Memory scope.
            memory_type: Type of memory.
            existing_memory: Existing memory for incremental update
                (used only for long-term memory).

        Returns:
            Generated memory text.
        """
        ...
