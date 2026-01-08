"""StrandsResponseGenerator implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig
from myao2.domain.entities import Context, GenerationResult, LLMMetrics
from myao2.infrastructure.llm.strands.exceptions import map_strands_exception
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp

if TYPE_CHECKING:
    from myao2.infrastructure.llm.strands.memo_tools import MemoToolsFactory
    from myao2.infrastructure.llm.strands.web_fetch_tools import WebFetchToolsFactory
    from myao2.infrastructure.llm.strands.web_search_tools import WebSearchToolsFactory


class StrandsResponseGenerator:
    """strands-agents based ResponseGenerator implementation.

    This class generates responses using strands-agents Agent framework.
    The Model is reused across requests, while a new Agent is created
    for each request since the system prompt depends on the context.
    """

    def __init__(
        self,
        model: LiteLLMModel,
        agent_config: AgentConfig | None = None,
        memo_tools_factory: MemoToolsFactory | None = None,
        web_fetch_tools_factory: WebFetchToolsFactory | None = None,
        web_search_tools_factory: WebSearchToolsFactory | None = None,
    ) -> None:
        """Initialize the generator.

        Args:
            model: LiteLLMModel instance to be reused across requests.
            agent_config: Agent configuration with optional system_prompt.
            memo_tools_factory: Factory for memo tools (optional).
            web_fetch_tools_factory: Factory for web fetch tools (optional).
            web_search_tools_factory: Factory for web search tools (optional).
        """
        self._model = model
        self._agent_config = agent_config
        self._memo_tools_factory = memo_tools_factory
        self._web_fetch_tools_factory = web_fetch_tools_factory
        self._web_search_tools_factory = web_search_tools_factory
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("response_system.j2")
        self._query_template = self._jinja_env.get_template("response_query.j2")

    async def generate(self, context: Context) -> GenerationResult:
        """Generate a response.

        The target thread/message is identified by context.target_thread_ts.
        - If target_thread_ts is None, responds to top-level messages
        - If target_thread_ts is set, responds to the specified thread

        Args:
            context: Conversation context (history, persona info, target_thread_ts).

        Returns:
            GenerationResult containing the response text and metrics.
        """
        system_prompt = self.build_system_prompt(context)
        query_prompt = self.build_query_prompt(context)

        # Configure tools from available factories
        tools: list = []
        invocation_state: dict = {}
        if self._memo_tools_factory:
            tools.extend(self._memo_tools_factory.tools)
            invocation_state.update(self._memo_tools_factory.get_invocation_state())
        if self._web_fetch_tools_factory:
            tools.extend(self._web_fetch_tools_factory.tools)
            invocation_state.update(
                self._web_fetch_tools_factory.get_invocation_state()
            )
        if self._web_search_tools_factory:
            tools.extend(self._web_search_tools_factory.tools)
            invocation_state.update(
                self._web_search_tools_factory.get_invocation_state()
            )

        # Create Agent per request since system_prompt is dynamic
        agent = Agent(model=self._model, system_prompt=system_prompt, tools=tools)

        try:
            result = await agent.invoke_async(query_prompt, **invocation_state)
            metrics = LLMMetrics.from_strands_result(result)
            return GenerationResult(text=str(result), metrics=metrics)
        except Exception as e:
            raise map_strands_exception(e)

    def build_system_prompt(self, context: Context) -> str:
        """Build system prompt (fixed part).

        Args:
            context: Conversation context.

        Returns:
            Rendered system prompt string.
        """
        agent_system_prompt = (
            self._agent_config.system_prompt if self._agent_config else None
        )
        return self._system_template.render(
            persona=context.persona,
            agent_system_prompt=agent_system_prompt,
        )

    def build_query_prompt(self, context: Context) -> str:
        """Build query prompt (dynamic part).

        Args:
            context: Conversation context.

        Returns:
            Rendered query prompt string.
        """
        channel_messages = context.conversation_history

        if context.target_thread_ts:
            target_thread_messages = channel_messages.get_thread(
                context.target_thread_ts
            )
        else:
            target_thread_messages = channel_messages.top_level_messages

        return self._query_template.render(
            workspace_long_term_memory=context.workspace_long_term_memory,
            workspace_short_term_memory=context.workspace_short_term_memory,
            channel_memories=context.channel_memories,
            current_channel_name=channel_messages.channel_name,
            top_level_messages=channel_messages.top_level_messages,
            thread_messages=channel_messages.thread_messages,
            target_thread_ts=context.target_thread_ts,
            target_thread_messages=target_thread_messages,
            high_priority_memos=context.high_priority_memos,
            recent_memos=context.recent_memos,
        )
