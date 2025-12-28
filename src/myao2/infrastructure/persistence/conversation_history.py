"""DB implementation of ConversationHistoryService."""

from myao2.domain.entities import Message
from myao2.domain.repositories import MessageRepository


class DBConversationHistoryService:
    """DB 実装の ConversationHistoryService

    MessageRepository を使用してデータベースから会話履歴を取得する。
    Slack API を呼び出さないため、高速かつレート制限の心配がない。
    """

    def __init__(self, message_repository: MessageRepository) -> None:
        """初期化

        Args:
            message_repository: メッセージリポジトリ
        """
        self._message_repository = message_repository

    async def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッド履歴を DB から取得する

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """
        # MessageRepository は新しい順で返すので、反転して古い順にする
        messages = await self._message_repository.find_by_thread(
            channel_id, thread_ts, limit
        )
        return list(reversed(messages))

    async def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネル履歴を DB から取得する

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """
        # MessageRepository は新しい順で返すので、反転して古い順にする
        messages = await self._message_repository.find_by_channel(channel_id, limit)
        return list(reversed(messages))
