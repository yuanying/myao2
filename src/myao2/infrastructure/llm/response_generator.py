"""LLM response generator."""

from myao2.domain.entities import Context
from myao2.infrastructure.llm.client import LLMClient
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


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
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._template = self._jinja_env.get_template("system_prompt.j2")

    async def generate(
        self,
        context: Context,
    ) -> str:
        """Generate a response.

        Builds a system prompt from context, then sends it to the LLM.

        Args:
            context: Conversation context (history, persona info, target_thread_ts).

        Returns:
            Generated response text.

        Raises:
            LLMError: If response generation fails.
        """
        system_prompt = self.build_system_prompt(context)
        messages = [{"role": "system", "content": system_prompt}]

        return await self._client.complete(messages, caller="response_generator")

    def build_system_prompt(self, context: Context) -> str:
        """Build system prompt from context.

        Uses Jinja2 template to construct the prompt with memory integration.

        Args:
            context: Conversation context.

        Returns:
            Complete system prompt string.
        """
        channel_messages = context.conversation_history

        # Get target thread messages
        if context.target_thread_ts:
            target_thread_messages = channel_messages.get_thread(
                context.target_thread_ts
            )
        else:
            target_thread_messages = channel_messages.top_level_messages

        # Build template context
        template_context = {
            "persona": context.persona,
            "workspace_long_term_memory": context.workspace_long_term_memory,
            "workspace_short_term_memory": context.workspace_short_term_memory,
            "channel_memories": context.channel_memories,
            "current_channel_name": channel_messages.channel_name,
            "top_level_messages": channel_messages.top_level_messages,
            "thread_messages": channel_messages.thread_messages,
            "target_thread_ts": context.target_thread_ts,
            "target_thread_messages": target_thread_messages,
        }

        return self._template.render(**template_context)
