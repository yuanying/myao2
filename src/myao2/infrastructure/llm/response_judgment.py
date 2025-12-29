"""LLM-based response judgment service."""

import json
import logging
import re
from datetime import datetime, timezone

from myao2.config.models import PersonaConfig
from myao2.domain.entities import Context, Message
from myao2.domain.entities.judgment_result import JudgmentResult
from myao2.infrastructure.llm.client import LLMClient
from myao2.infrastructure.llm.exceptions import LLMError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """あなたは会話への参加判断を行うアシスタントです。
以下の会話を分析し、{persona_name}として応答すべきかを判断してください。

現在時刻: {current_time}

判断基準：
1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

以下の場合は応答しないでください：
- 明らかな独り言
- 活発な会話に無理に割り込む場合

必ずJSON形式で回答してください。他のテキストは含めないでください。
回答形式：
{{"should_respond": true/false, "reason": "理由", "confidence": 0.0-1.0}}

confidence について：
- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）"""


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

    async def judge(self, context: Context, message: Message) -> JudgmentResult:
        """Determine whether to respond.

        Args:
            context: Conversation context.
            message: Target message to judge.

        Returns:
            Judgment result.
        """
        current_time = datetime.now(timezone.utc)

        try:
            messages = self._build_messages(context, message, current_time)
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

    def _build_messages(
        self,
        context: Context,
        message: Message,
        current_time: datetime,
    ) -> list[dict[str, str]]:
        """Build messages for LLM.

        Args:
            context: Conversation context.
            message: Target message to judge.
            current_time: Current time for the prompt.

        Returns:
            OpenAI-format message list.
        """
        system_prompt = self._build_system_prompt(context.persona, current_time)
        conversation = self._format_conversation(context.conversation_history)
        target_msg = self._format_message(message)

        user_content = f"会話履歴:\n{conversation}\n\n判定対象メッセージ:\n{target_msg}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _format_message(self, message: Message) -> str:
        """Format a single message with timestamp.

        Args:
            message: Message to format.

        Returns:
            Formatted message string.
        """
        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] {message.user.name}: {message.text}"

    def _build_system_prompt(
        self,
        persona: PersonaConfig,
        current_time: datetime,
    ) -> str:
        """Build system prompt with current time.

        Args:
            persona: Persona configuration.
            current_time: Current time.

        Returns:
            System prompt string.
        """
        return SYSTEM_PROMPT_TEMPLATE.format(
            persona_name=persona.name,
            current_time=current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    def _format_conversation(self, messages: list[Message]) -> str:
        """Format conversation history with timestamps.

        Args:
            messages: List of messages.

        Returns:
            Formatted conversation string.
        """
        if not messages:
            return "(会話履歴なし)"

        lines = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{timestamp}] {msg.user.name}: {msg.text}")
        return "\n".join(lines)

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
