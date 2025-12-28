"""Context entity."""

from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history and generates system prompts for LLM.
    Phase 3 will add long-term and short-term memory support.

    Attributes:
        persona: Persona configuration with name and system prompt.
        conversation_history: List of past messages in chronological order.
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    # Phase 3 以降で追加予定
    # long_term_memory: str | None = None
    # short_term_memory: str | None = None

    def build_system_prompt(self) -> str:
        """Build the system prompt.

        Phase 2: Simply returns the persona's system prompt.
        Phase 3+: Will integrate long-term and short-term memory.

        Returns:
            System prompt string.
        """
        return self.persona.system_prompt

    def build_messages_for_llm(
        self,
        user_message: Message,
    ) -> list[dict[str, str]]:
        """Build message list for LLM.

        Constructs an OpenAI-compatible message list from conversation history
        and the current user message. If the current message is already in
        the conversation history, it will not be duplicated.

        Args:
            user_message: Current user message.

        Returns:
            OpenAI format message list:
            [{"role": "system", "content": ...}, ...]
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.build_system_prompt()}
        ]

        # Add conversation history (already in chronological order)
        # Skip the last message if it's the same as user_message to avoid duplication
        history_to_process = self.conversation_history
        if history_to_process and history_to_process[-1].id == user_message.id:
            history_to_process = history_to_process[:-1]

        for msg in history_to_process:
            role = "assistant" if msg.user.is_bot else "user"
            messages.append({"role": role, "content": msg.text})

        # Add current user message
        messages.append({"role": "user", "content": user_message.text})

        return messages
