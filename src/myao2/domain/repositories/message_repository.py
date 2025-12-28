"""Message repository protocol."""

from typing import Protocol

from myao2.domain.entities import Message


class MessageRepository(Protocol):
    """会話履歴リポジトリの抽象インターフェース

    メッセージの保存・取得を抽象化し、
    永続化層の実装詳細を隠蔽する。
    """

    def save(self, message: Message) -> None:
        """メッセージを保存する

        既存のメッセージ（同一の message_id, channel_id）が存在する場合は更新する。

        Args:
            message: 保存するメッセージ
        """
        ...

    def find_by_channel(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルのメッセージ履歴を取得する

        スレッドに属さないメッセージのみを取得する。

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    def find_by_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドのメッセージ履歴を取得する

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    def find_by_id(self, message_id: str, channel_id: str) -> Message | None:
        """ID でメッセージを検索する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID

        Returns:
            メッセージ（存在しない場合は None）
        """
        ...
