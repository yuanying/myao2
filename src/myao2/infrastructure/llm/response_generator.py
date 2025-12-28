"""LLM response generator."""

import logging

from myao2.domain.entities import Context, Message
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

        Uses Context to build the message list for the LLM.

        Args:
            user_message: User's message to respond to.
            context: Conversation context (history, persona info).

        Returns:
            Generated response text.

        Raises:
            LLMError: If response generation fails.
        """
        messages = context.build_messages_for_llm(user_message)

        if self._should_log():
            self._log_messages(messages)

        response = await self._client.complete(messages)

        if self._should_log():
            self._log_response(response)

        return response

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
