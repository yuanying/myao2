"""Response judgment service protocol."""

from typing import Protocol

from myao2.domain.entities import Context
from myao2.domain.entities.judgment_result import JudgmentResult


class ResponseJudgment(Protocol):
    """Response judgment service.

    Analyzes conversation context and determines whether
    the bot should respond.
    """

    async def judge(
        self,
        context: Context,
    ) -> JudgmentResult:
        """Determine whether to respond.

        The target thread/message is identified by context.target_thread_ts.
        - If target_thread_ts is None, judges top-level messages
        - If target_thread_ts is set, judges the specified thread

        Args:
            context: Conversation context (including persona,
                conversation_history, and target_thread_ts).

        Returns:
            Judgment result.
        """
        ...
