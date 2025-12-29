"""LLM response generator."""

import logging

from myao2.domain.entities import Context, Message
from myao2.domain.services.message_formatter import (
    format_conversation_history,
    format_message_with_metadata,
    format_other_channels,
)
from myao2.infrastructure.llm.client import LLMClient

logger = logging.getLogger(__name__)


class LiteLLMResponseGenerator:
    """LiteLLM-based ResponseGenerator implementation.

    This class implements the ResponseGenerator protocol using LiteLLM
    to generate responses with conversation context.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        debug_llm_messages: bool = False,
    ) -> None:
        """Initialize the generator.

        Args:
            client: LLMClient instance.
            debug_llm_messages: If True, log LLM messages at INFO level.
        """
        self._client = client
        self._debug_llm_messages = debug_llm_messages

    async def generate(
        self,
        user_message: Message,
        context: Context,
    ) -> str:
        """Generate a response.

        Builds a system prompt from context and user message,
        then sends it to the LLM.

        Args:
            user_message: User's message to respond to.
            context: Conversation context (history, persona info).

        Returns:
            Generated response text.

        Raises:
            LLMError: If response generation fails.
        """
        system_prompt = self._build_system_prompt(context, user_message)
        messages = [{"role": "system", "content": system_prompt}]

        if self._should_log():
            self._log_messages(messages)

        response = await self._client.complete(messages)

        if self._should_log():
            self._log_response(response)

        return response

    def _build_system_prompt(self, context: Context, current_message: Message) -> str:
        """Build system prompt from context and current message.

        Args:
            context: Conversation context.
            current_message: Current user message to respond to.

        Returns:
            Complete system prompt string.
        """
        parts = [context.persona.system_prompt]

        # Add conversation history
        parts.append("\n\n## 会話履歴")
        parts.append(format_conversation_history(context.conversation_history))

        # Add current message to respond to
        parts.append("\n\n## 返答すべきメッセージ")
        parts.append(format_message_with_metadata(current_message))

        # Add other channel messages if present
        other_channels = format_other_channels(context.other_channel_messages)
        if other_channels:
            parts.append("\n\n## 他のチャンネルでの最近の会話")
            parts.append(other_channels)

        # Add instruction
        parts.append("\n\n---")
        parts.append(
            "\n上記の会話履歴と参考情報を元に、"
            "「返答すべきメッセージ」に対して自然な返答を生成してください。"
        )

        return "\n".join(parts)

    def _should_log(self) -> bool:
        """Check if logging should occur."""
        return self._debug_llm_messages or logger.isEnabledFor(logging.DEBUG)

    def _log_messages(self, messages: list[dict[str, str]]) -> None:
        """Log LLM request messages."""
        log_func = logger.info if self._debug_llm_messages else logger.debug
        log_func("=== LLM Request Messages ===")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            log_func("[%d] role=%s", i, role)
            log_func("    content: %s", content)
        log_func("=== End of Messages ===")

    def _log_response(self, response: str) -> None:
        """Log LLM response."""
        log_func = logger.info if self._debug_llm_messages else logger.debug
        log_func("=== LLM Response ===")
        log_func("response: %s", response)
        log_func("=== End of Response ===")
