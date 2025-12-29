"""Context entity."""

from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history and other channel messages for LLM.
    This is a pure data class - system prompt construction is the
    responsibility of the module that receives the context.

    Attributes:
        persona: Persona configuration with name and system prompt.
        conversation_history: List of past messages in chronological order.
        other_channel_messages: Messages from other channels, keyed by channel name.
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    other_channel_messages: dict[str, list[Message]] = field(default_factory=dict)
    # Phase 4 以降で追加予定
    # long_term_memory: str | None = None
    # short_term_memory: str | None = None
