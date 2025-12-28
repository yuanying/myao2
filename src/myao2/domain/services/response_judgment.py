"""Response judgment service protocol."""

from typing import Protocol

from myao2.domain.entities import Context, Message
from myao2.domain.entities.judgment_result import JudgmentResult


class ResponseJudgment(Protocol):
    """Response judgment service.

    Analyzes conversation context and determines whether
    the bot should respond.
    """

    async def judge(
        self,
        context: Context,
        message: Message,
    ) -> JudgmentResult:
        """Determine whether to respond.

        Args:
            context: Conversation context (including persona and
                conversation_history).
            message: Target message to judge.

        Returns:
            Judgment result.
        """
        ...
