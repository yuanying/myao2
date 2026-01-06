"""Context entity."""

from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.memo import Memo


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history, channel memories, and thread memories for LLM.
    This is a pure data class - system prompt construction is the
    responsibility of the module that receives the context.

    Attributes:
        persona: Persona configuration with name and system prompt.
        conversation_history: Channel messages structure for target channel.
        workspace_long_term_memory: Workspace long-term memory.
        workspace_short_term_memory: Workspace short-term memory.
        channel_memories: Active channel memories (channel_id -> ChannelMemory).
        thread_memories: Recent thread summaries (thread_ts -> memory).
        target_thread_ts: Target thread timestamp (None for top-level).
        high_priority_memos: High priority memos (priority >= 4, max 20).
        recent_memos: Recent memos (max 5, excluding high_priority_memos).
    """

    persona: PersonaConfig
    conversation_history: ChannelMessages
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None
    channel_memories: dict[str, ChannelMemory] = field(default_factory=dict)
    thread_memories: dict[str, str] = field(default_factory=dict)
    target_thread_ts: str | None = None
    high_priority_memos: list[Memo] = field(default_factory=list)
    recent_memos: list[Memo] = field(default_factory=list)
