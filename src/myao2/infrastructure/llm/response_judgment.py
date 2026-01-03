"""LLM-based response judgment service."""

import json
import logging
import re
from datetime import datetime, timezone

from myao2.domain.entities import Context
from myao2.domain.entities.judgment_result import JudgmentResult
from myao2.infrastructure.llm.client import LLMClient
from myao2.infrastructure.llm.exceptions import LLMError
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp

logger = logging.getLogger(__name__)


class LLMResponseJudgment:
    """LLM-based response judgment service.

    Uses LLM to analyze conversation context and determine
    whether the bot should respond.
    """

    def __init__(self, client: LLMClient) -> None:
        """Initialize the judgment service.

        Args:
            client: LLM client for making API calls.
        """
        self._client = client
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._template = self._jinja_env.get_template("judgment_prompt.j2")

    async def judge(self, context: Context) -> JudgmentResult:
        """Determine whether to respond.

        The target thread/message is identified by context.target_thread_ts.

        Args:
            context: Conversation context.

        Returns:
            Judgment result.
        """
        try:
            system_prompt = self._build_system_prompt(context)
            messages = [{"role": "system", "content": system_prompt}]
            response = await self._client.complete(messages)
            logger.debug("LLM judgment response: %s", response)
            result = self._parse_response(response)
            logger.info(
                "Response judgment: should_respond=%s, reason=%s",
                result.should_respond,
                result.reason,
            )
            return result
        except LLMError as e:
            logger.error("LLM error during judgment: %s", e)
            return JudgmentResult(
                should_respond=False,
                reason=f"LLM error: {e}",
            )

    def _build_system_prompt(self, context: Context) -> str:
        """Build system prompt using Jinja2 template.

        Args:
            context: Conversation context.

        Returns:
            Built system prompt string.
        """
        channel_messages = context.conversation_history
        current_time = datetime.now(timezone.utc)

        # Get target thread messages
        target_thread_messages = []
        if context.target_thread_ts:
            target_thread_messages = channel_messages.get_thread(
                context.target_thread_ts
            )

        template_context = {
            "persona": context.persona,
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
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

    def _parse_response(self, response: str) -> JudgmentResult:
        """Parse LLM response to JudgmentResult.

        Attempts to extract JSON from the response.
        Returns should_respond=False on parse failure.

        Args:
            response: LLM response string.

        Returns:
            Parsed judgment result.
        """
        try:
            # Try to extract JSON from response (may be embedded in text)
            json_match = re.search(r"\{[^{}]*\}", response)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
            else:
                data = json.loads(response)

            should_respond = data.get("should_respond", False)
            reason = data.get("reason", "")
            confidence = data.get("confidence", 1.0)

            # Clamp confidence to valid range [0.0, 1.0]
            confidence = max(0.0, min(1.0, float(confidence)))

            return JudgmentResult(
                should_respond=bool(should_respond),
                reason=reason,
                confidence=confidence,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse LLM response: %s", e)
            return JudgmentResult(
                should_respond=False,
                reason=f"Failed to parse LLM response: {e}",
                confidence=0.0,  # パース失敗時は低い confidence
            )
