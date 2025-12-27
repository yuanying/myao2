"""LLM response generator."""

from myao2.infrastructure.llm.client import LLMClient


class LiteLLMResponseGenerator:
    """LiteLLM-based ResponseGenerator implementation.

    This class implements the ResponseGenerator protocol using LiteLLM
    to generate responses to user messages.
    """

    def __init__(self, client: LLMClient) -> None:
        """Initialize the generator.

        Args:
            client: LLMClient instance.
        """
        self._client = client

    def generate(
        self,
        user_message: str,
        system_prompt: str,
    ) -> str:
        """Generate a response.

        Args:
            user_message: User's message to respond to.
            system_prompt: System prompt (persona settings, etc.).

        Returns:
            Generated response text.

        Raises:
            LLMError: If response generation fails.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        return self._client.complete(messages)
