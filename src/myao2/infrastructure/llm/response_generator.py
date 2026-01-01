"""LLM response generator."""

import logging
from datetime import datetime

from jinja2 import Environment, PackageLoader, select_autoescape

from myao2.domain.entities import Context
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
        self._jinja_env = self._create_jinja_env()
        self._template = self._jinja_env.get_template("system_prompt.j2")

    def _create_jinja_env(self) -> Environment:
        """Create Jinja2 environment.

        Returns:
            Configured Jinja2 environment.
        """
        env = Environment(
            loader=PackageLoader("myao2.infrastructure.llm", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["format_timestamp"] = self._format_timestamp
        return env

    @staticmethod
    def _format_timestamp(timestamp: datetime) -> str:
        """Format datetime to readable string.

        Args:
            timestamp: datetime object.

        Returns:
            Formatted string in YYYY-MM-DD HH:MM:SS format.
        """
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

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
        system_prompt = self._build_system_prompt(context)
        messages = [{"role": "system", "content": system_prompt}]

        if self._should_log():
            self._log_messages(messages)

        response = await self._client.complete(messages)

        if self._should_log():
            self._log_response(response)

        return response

    def _build_system_prompt(self, context: Context) -> str:
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
