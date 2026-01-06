"""StrandsMemorySummarizer implementation."""

from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig, MemoryConfig
from myao2.domain.entities import Context, LLMMetrics, SummarizationResult
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.infrastructure.llm.strands.exceptions import map_strands_exception
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class StrandsMemorySummarizer:
    """strands-agents based MemorySummarizer implementation.

    This class generates memory summaries using strands-agents Agent framework.
    The Model is reused across requests, while a new Agent is created
    for each request since the system prompt depends on the context.
    """

    def __init__(
        self,
        model: LiteLLMModel,
        config: MemoryConfig,
        agent_config: AgentConfig | None = None,
    ) -> None:
        """Initialize the summarizer.

        Args:
            model: LiteLLMModel instance to be reused across requests.
            config: Memory configuration.
            agent_config: Agent configuration with optional system_prompt.
        """
        self._model = model
        self._config = config
        self._agent_config = agent_config
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("memory_system.j2")
        self._query_template = self._jinja_env.get_template("memory_query.j2")

    async def summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> SummarizationResult:
        """Generate memory summary from context.

        Args:
            context: Conversation context containing messages and memories.
            scope: Memory scope determining what to summarize.
            memory_type: Type of memory (long-term or short-term).
            existing_memory: Existing memory for incremental update.

        Returns:
            SummarizationResult containing the memory text and metrics.
        """
        if not self._has_content_to_summarize(context, scope, memory_type):
            return SummarizationResult(text=existing_memory or "", metrics=None)

        system_prompt = self.build_system_prompt(context, scope, memory_type)
        query_prompt = self.build_query_prompt(
            context, scope, memory_type, existing_memory
        )

        # Create Agent per request since system_prompt is dynamic
        agent = Agent(model=self._model, system_prompt=system_prompt)

        try:
            result = await agent.invoke_async(query_prompt)
            metrics = LLMMetrics.from_strands_result(result)
            return SummarizationResult(text=str(result), metrics=metrics)
        except Exception as e:
            raise map_strands_exception(e)

    def build_system_prompt(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> str:
        """Build system prompt (fixed part).

        Args:
            context: Conversation context.
            scope: Memory scope.
            memory_type: Type of memory.

        Returns:
            Rendered system prompt string.
        """
        agent_system_prompt = (
            self._agent_config.system_prompt if self._agent_config else None
        )
        return self._system_template.render(
            persona=context.persona,
            agent_system_prompt=agent_system_prompt,
            scope=scope.value,
            memory_type=memory_type.value,
        )

    def build_query_prompt(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None,
    ) -> str:
        """Build query prompt (dynamic part).

        Args:
            context: Conversation context.
            scope: Memory scope.
            memory_type: Type of memory.
            existing_memory: Existing memory for incremental update.

        Returns:
            Rendered query prompt string.
        """
        channel_messages = context.conversation_history

        # Get target thread messages
        target_thread_messages = []
        if context.target_thread_ts:
            target_thread_messages = channel_messages.get_thread(
                context.target_thread_ts
            )

        # Get channel short-term memory (for CHANNEL LONG_TERM)
        channel_short_term_memory = self._get_channel_short_term_memory(context)

        return self._query_template.render(
            scope=scope.value,
            memory_type=memory_type.value,
            existing_memory=existing_memory,
            workspace_long_term_memory=context.workspace_long_term_memory,
            workspace_short_term_memory=context.workspace_short_term_memory,
            channel_memories=context.channel_memories,
            current_channel_name=channel_messages.channel_name,
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=context.target_thread_ts,
            target_thread_messages=target_thread_messages,
            channel_short_term_memory=channel_short_term_memory,
        )

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

    def _get_channel_short_term_memory(self, context: Context) -> str | None:
        """Get short-term memory for the current channel.

        Args:
            context: Conversation context.

        Returns:
            Short-term memory for the current channel, or None.
        """
        if not context.channel_memories:
            return None
        channel_id = context.conversation_history.channel_id
        if channel_id in context.channel_memories:
            return context.channel_memories[channel_id].short_term_memory
        return None
