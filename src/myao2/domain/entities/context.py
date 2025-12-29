"""Context entity."""

from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history, other channel messages, and memories for LLM.
    This is a pure data class - system prompt construction is the
    responsibility of the module that receives the context.

    Attributes:
        persona: Persona configuration with name and system prompt.
        conversation_history: List of past messages in chronological order.
        other_channel_messages: Messages from other channels, keyed by channel name.
        workspace_long_term_memory: Workspace long-term memory (timeline summary).
        workspace_short_term_memory: Workspace short-term memory (recent summary).
        channel_long_term_memory: Channel long-term memory (timeline summary).
        channel_short_term_memory: Channel short-term memory (recent summary).
        thread_memory: Thread memory (thread summary).
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    other_channel_messages: dict[str, list[Message]] = field(default_factory=dict)

    # 記憶フィールド（Phase 4 追加）
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None
    channel_long_term_memory: str | None = None
    channel_short_term_memory: str | None = None
    thread_memory: str | None = None
