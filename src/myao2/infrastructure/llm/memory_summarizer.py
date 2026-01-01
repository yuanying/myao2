"""LLM-based memory summarizer implementation."""

from myao2.config.models import MemoryConfig
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.domain.entities.message import Message
from myao2.domain.services.memory_summarizer import MemorySummarizer
from myao2.infrastructure.llm.client import LLMClient
from myao2.infrastructure.llm.templates import create_jinja_env

# Scope name mapping
_SCOPE_NAMES: dict[MemoryScope, str] = {
    MemoryScope.WORKSPACE: "ワークスペース",
    MemoryScope.CHANNEL: "チャンネル",
    MemoryScope.THREAD: "スレッド",
}


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
        # Get content to summarize based on scope and memory type
        content = self._get_content_for_scope(context, scope, memory_type)
        if not content:
            return existing_memory or ""

        prompt = self._build_prompt(
            content, scope, memory_type, existing_memory, context
        )
        max_tokens = self._get_max_tokens(memory_type)

        llm_messages = [
            {"role": "system", "content": self._get_system_prompt(scope, memory_type)},
            {"role": "user", "content": prompt},
        ]

        response = await self._client.complete(
            llm_messages,
            max_tokens=max_tokens,
        )

        return response.strip()

    def _get_content_for_scope(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> str:
        """Get content to summarize based on scope and memory type.

        Content source differs by scope and memory type:
        - THREAD: Always uses messages from target_thread_ts
        - CHANNEL short-term: Uses all messages
        - CHANNEL long-term: Uses channel's short-term memory
        - WORKSPACE short-term: Uses channel short-term memories
        - WORKSPACE long-term: Uses channel long-term memories

        Args:
            context: Conversation context.
            scope: Memory scope.
            memory_type: Type of memory.

        Returns:
            Content string to summarize, empty if nothing to summarize.
        """
        if scope == MemoryScope.THREAD:
            return self._get_thread_content(context)
        elif scope == MemoryScope.CHANNEL:
            return self._get_channel_content(context, memory_type)
        else:  # WORKSPACE
            return self._get_workspace_content(context, memory_type)

    def _get_thread_content(self, context: Context) -> str:
        """Get thread messages for summarization.

        Args:
            context: Conversation context.

        Returns:
            Formatted thread messages, empty if no target thread.
        """
        if not context.target_thread_ts:
            return ""

        messages = context.conversation_history.get_thread(context.target_thread_ts)
        return self._format_messages(messages)

    def _get_channel_content(self, context: Context, memory_type: MemoryType) -> str:
        """Get content for channel summarization.

        For short-term: Uses all messages (top-level + threads).
        For long-term: Uses channel's short-term memory.

        Args:
            context: Conversation context.
            memory_type: Type of memory.

        Returns:
            Content string to summarize.
        """
        if memory_type == MemoryType.SHORT_TERM:
            messages = context.conversation_history.get_all_messages()
            return self._format_messages(messages)
        else:
            # Long-term: use channel's short-term memory
            channel_id = context.conversation_history.channel_id
            if channel_id in context.channel_memories:
                short_term = context.channel_memories[channel_id].short_term_memory
                return short_term or ""
            return ""

    def _get_workspace_content(self, context: Context, memory_type: MemoryType) -> str:
        """Get channel memories for workspace summarization.

        For short-term: Uses only channel short-term memories.
        For long-term: Uses only channel long-term memories.

        Args:
            context: Conversation context.
            memory_type: Type of memory.

        Returns:
            Formatted channel memories.
        """
        if not context.channel_memories:
            return ""

        sections: list[str] = []
        for channel_mem in context.channel_memories.values():
            if memory_type == MemoryType.SHORT_TERM:
                # Use only short-term memories
                if channel_mem.short_term_memory:
                    sections.append(
                        f"## チャンネル: {channel_mem.channel_name}\n"
                        f"{channel_mem.short_term_memory}"
                    )
            else:
                # Use only long-term memories
                if channel_mem.long_term_memory:
                    sections.append(
                        f"## チャンネル: {channel_mem.channel_name}\n"
                        f"{channel_mem.long_term_memory}"
                    )

        return "\n\n".join(sections)

    def _build_prompt(
        self,
        content: str,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None,
        context: Context,
    ) -> str:
        """Build the user prompt.

        Args:
            content: Content to summarize.
            scope: Memory scope.
            memory_type: Type of memory.
            existing_memory: Existing memory for incremental update.
            context: Conversation context for auxiliary info.

        Returns:
            Built prompt string.
        """
        scope_name = self._get_scope_name(scope)
        auxiliary_info = self._build_auxiliary_info(scope, context)

        if scope == MemoryScope.WORKSPACE:
            # Workspace uses channel memories as input
            if memory_type == MemoryType.LONG_TERM:
                if existing_memory:
                    base_prompt = (
                        f"以下の各チャンネルの記憶を、"
                        "既存のワークスペース要約に統合・更新してください。\n\n"
                        f"既存の要約:\n{existing_memory}\n\n"
                        f"チャンネル記憶:\n{content}\n\n"
                        "既存の要約を維持しつつ、新しい情報を統合してください。"
                    )
                else:
                    base_prompt = (
                        f"以下の各チャンネルの記憶を統合し、"
                        "ワークスペース全体の要約を作成してください。\n\n"
                        f"チャンネル記憶:\n{content}"
                    )
            else:
                base_prompt = (
                    f"以下の各チャンネルの記憶から、"
                    "ワークスペース全体の現在の状況を要約してください。\n\n"
                    f"チャンネル記憶:\n{content}"
                )
        else:
            # Thread and Channel use messages
            if memory_type == MemoryType.LONG_TERM:
                if existing_memory:
                    base_prompt = (
                        f"以下の{scope_name}の会話履歴を、"
                        "既存の要約に追加・更新してください。\n\n"
                        f"既存の要約:\n{existing_memory}\n\n"
                        f"新しい会話履歴:\n{content}\n\n"
                        "既存の要約を維持しつつ、新しい情報を時系列順に追加してください。\n"
                        "古い情報は必要に応じて要約・統合しても構いません。"
                    )
                else:
                    base_prompt = (
                        f"以下の{scope_name}の会話履歴から、"
                        "長期的な傾向を時系列で要約してください。\n\n"
                        f"会話履歴:\n{content}"
                    )
            else:
                base_prompt = (
                    f"以下の{scope_name}の直近の会話から、"
                    "現在の状況を要約してください。\n\n"
                    f"会話履歴:\n{content}"
                )

        if auxiliary_info:
            return f"{base_prompt}\n\n{auxiliary_info}"
        return base_prompt

    def _get_system_prompt(
        self,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> str:
        """Get the system prompt.

        Args:
            scope: Memory scope.
            memory_type: Type of memory.

        Returns:
            System prompt string.
        """
        return self._template.render(
            scope=scope.value,
            memory_type=memory_type.value,
        )

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

    def _get_scope_name(self, scope: MemoryScope) -> str:
        """Get the Japanese name for a scope.

        Args:
            scope: Memory scope.

        Returns:
            Japanese scope name.
        """
        return _SCOPE_NAMES[scope]

    def _format_messages(self, messages: list[Message]) -> str:
        """Format messages for prompt.

        Args:
            messages: Messages to format.

        Returns:
            Formatted message string.
        """
        lines = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            user = msg.user.name
            text = msg.text
            lines.append(f"[{timestamp}] {user}: {text}")
        return "\n".join(lines)

    def _build_auxiliary_info(
        self,
        scope: MemoryScope,
        context: Context,
    ) -> str:
        """Build auxiliary information from context for the given scope.

        For channel scope: includes workspace memory.
        For thread scope: includes channel and workspace memory.
        For workspace scope: no auxiliary info (highest level).

        Args:
            scope: Target memory scope.
            context: Conversation context with memories.

        Returns:
            Formatted auxiliary information string, empty if none available.
        """
        sections: list[str] = []

        if scope == MemoryScope.CHANNEL:
            # For channel summarization, include workspace context
            if context.workspace_long_term_memory:
                sections.append(
                    f"ワークスペースの概要:\n{context.workspace_long_term_memory}"
                )
        elif scope == MemoryScope.THREAD:
            # For thread summarization, include channel and workspace context
            channel_id = context.conversation_history.channel_id
            if channel_id in context.channel_memories:
                channel_mem = context.channel_memories[channel_id]
                if channel_mem.long_term_memory:
                    sections.append(
                        f"チャンネル「{channel_mem.channel_name}」の概要:\n"
                        f"{channel_mem.long_term_memory}"
                    )
                elif channel_mem.short_term_memory:
                    sections.append(
                        f"チャンネル「{channel_mem.channel_name}」の最近の状況:\n"
                        f"{channel_mem.short_term_memory}"
                    )
            if context.workspace_long_term_memory:
                sections.append(
                    f"ワークスペースの概要:\n{context.workspace_long_term_memory}"
                )

        if not sections:
            return ""

        return "参考情報:\n" + "\n\n".join(sections)
