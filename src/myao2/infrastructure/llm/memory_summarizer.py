"""LLM-based memory summarizer implementation."""

from myao2.config.models import MemoryConfig
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.domain.services.memory_summarizer import MemorySummarizer
from myao2.infrastructure.llm.client import LLMClient
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class LLMMemorySummarizer(MemorySummarizer):
    """LLM-based memory summarization service."""

    def __init__(
        self,
        client: LLMClient,
        config: MemoryConfig,
    ) -> None:
        """Initialize the summarizer.

        Args:
            client: LLM client for text generation.
            config: Memory configuration.
        """
        self._client = client
        self._config = config
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._template = self._jinja_env.get_template("memory_prompt.j2")

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
            scope: Memory scope determining what to summarize.
            memory_type: Type of memory (long-term or short-term).
            existing_memory: Existing memory for incremental update.

        Returns:
            Generated memory text.
        """
        # Check if there's content to summarize
        if not self._has_content_to_summarize(context, scope, memory_type):
            return existing_memory or ""

        system_prompt = self._build_system_prompt(
            context, scope, memory_type, existing_memory
        )
        max_tokens = self._get_max_tokens(memory_type)

        llm_messages = [{"role": "system", "content": system_prompt}]

        response = await self._client.complete(
            llm_messages,
            max_tokens=max_tokens,
        )

        return response.strip()

    def _has_content_to_summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> bool:
        """Check if there's content to summarize.

        Args:
            context: Conversation context.
            scope: Memory scope.
            memory_type: Type of memory.

        Returns:
            True if there's content to summarize.
        """
        if scope == MemoryScope.THREAD:
            if not context.target_thread_ts:
                return False
            messages = context.conversation_history.get_thread(context.target_thread_ts)
            return len(messages) > 0

        elif scope == MemoryScope.CHANNEL:
            if memory_type == MemoryType.SHORT_TERM:
                messages = context.conversation_history.get_all_messages()
                return len(messages) > 0
            else:
                # Long-term: check for short-term memory
                channel_id = context.conversation_history.channel_id
                if channel_id in context.channel_memories:
                    short_term = context.channel_memories[channel_id].short_term_memory
                    return bool(short_term)
                return False

        else:  # WORKSPACE
            if not context.channel_memories:
                return False
            if memory_type == MemoryType.SHORT_TERM:
                return any(
                    ch.short_term_memory for ch in context.channel_memories.values()
                )
            else:
                return any(
                    ch.long_term_memory for ch in context.channel_memories.values()
                )

    def _build_system_prompt(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None,
    ) -> str:
        """Build system prompt using Jinja2 template.

        Args:
            context: Conversation context.
            scope: Memory scope.
            memory_type: Type of memory.
            existing_memory: Existing memory for incremental update.

        Returns:
            Built system prompt string.
        """
        channel_messages = context.conversation_history

        # Get target thread messages
        target_thread_messages = []
        if context.target_thread_ts:
            target_thread_messages = channel_messages.get_thread(
                context.target_thread_ts
            )

        # Get channel short-term memory (for CHANNEL LONG_TERM)
        channel_short_term_memory = None
        if scope == MemoryScope.CHANNEL and memory_type == MemoryType.LONG_TERM:
            channel_id = channel_messages.channel_id
            if channel_id in context.channel_memories:
                channel_short_term_memory = context.channel_memories[
                    channel_id
                ].short_term_memory

        template_context = {
            "persona": context.persona,
            "scope": scope.value,
            "memory_type": memory_type.value,
            "existing_memory": existing_memory,
            "workspace_long_term_memory": context.workspace_long_term_memory,
            "workspace_short_term_memory": context.workspace_short_term_memory,
            "channel_memories": context.channel_memories,
            "current_channel_name": channel_messages.channel_name,
            "top_level_messages": channel_messages.top_level_messages,
            "thread_messages": channel_messages.thread_messages,
            "target_thread_ts": context.target_thread_ts,
            "target_thread_messages": target_thread_messages,
            "channel_short_term_memory": channel_short_term_memory,
        }

        return self._template.render(**template_context)

    def _get_max_tokens(self, memory_type: MemoryType) -> int:
        """Get maximum tokens for the memory type.

        Args:
            memory_type: Type of memory.

        Returns:
            Maximum tokens.
        """
        if memory_type == MemoryType.LONG_TERM:
            return self._config.long_term_summary_max_tokens
        return self._config.short_term_summary_max_tokens
