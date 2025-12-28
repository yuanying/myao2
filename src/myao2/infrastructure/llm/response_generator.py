"""LLM response generator."""

from myao2.domain.entities import Context, Message
from myao2.infrastructure.llm.client import LLMClient


class LiteLLMResponseGenerator:
    """LiteLLM-based ResponseGenerator implementation.

    This class implements the ResponseGenerator protocol using LiteLLM
    to generate responses with conversation context.
    """

    def __init__(self, client: LLMClient) -> None:
        """Initialize the generator.

        Args:
            client: LLMClient instance.
        """
        self._client = client

    def generate(
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
        return self._client.complete(messages)
