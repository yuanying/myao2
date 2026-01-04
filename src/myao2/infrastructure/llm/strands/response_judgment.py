"""StrandsResponseJudgment implementation."""

from datetime import datetime, timezone

from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig
from myao2.domain.entities import Context, JudgmentResult
from myao2.infrastructure.llm.strands.exceptions import map_strands_exception
from myao2.infrastructure.llm.strands.models import JudgmentOutput
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class StrandsResponseJudgment:
    """strands-agents based ResponseJudgment implementation.

    Uses Structured Output for type-safe JSON output.
    """

    def __init__(
        self,
        model: LiteLLMModel,
        agent_config: AgentConfig | None = None,
    ) -> None:
        """Initialize the judgment.

        Args:
            model: LiteLLMModel instance to be reused across requests.
            agent_config: Agent configuration with optional system_prompt.
        """
        self._model = model
        self._agent_config = agent_config
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("judgment_system.j2")
        self._query_template = self._jinja_env.get_template("judgment_query.j2")

    async def judge(self, context: Context) -> JudgmentResult:
        """Determine whether to respond.

        The target thread/message is identified by context.target_thread_ts.
        - If target_thread_ts is None, judges top-level messages
        - If target_thread_ts is set, judges the specified thread

        Args:
            context: Conversation context.

        Returns:
            JudgmentResult with should_respond, reason, and confidence.
        """
        system_prompt = self._build_system_prompt(context)
        query_prompt = self._build_query_prompt(context)

        # Create Agent per request since system_prompt is dynamic
        agent = Agent(model=self._model, system_prompt=system_prompt)

        try:
            # Use Structured Output for type-safe JSON
            result = await agent.invoke_async(
                query_prompt,
                structured_output_model=JudgmentOutput,
            )
            output = result.structured_output
            if not isinstance(output, JudgmentOutput):
                raise ValueError(
                    f"Expected JudgmentOutput but got {type(output).__name__}"
                )

            return JudgmentResult(
                should_respond=output.should_respond,
                reason=output.reason,
                confidence=output.confidence,
            )
        except Exception as e:
            raise map_strands_exception(e)

    def _build_system_prompt(self, context: Context) -> str:
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

    def _build_query_prompt(self, context: Context) -> str:
        """Build query prompt (dynamic part).

        Args:
            context: Conversation context.

        Returns:
            Rendered query prompt string.
        """
        channel_messages = context.conversation_history
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
            current_time=current_time,
            persona=context.persona,
        )
