"""Message repository protocol."""

from datetime import datetime
from typing import Protocol

from myao2.domain.entities import Message


class MessageRepository(Protocol):
    """会話履歴リポジトリの抽象インターフェース

    メッセージの保存・取得を抽象化し、
    永続化層の実装詳細を隠蔽する。
    """

    async def save(self, message: Message) -> None:
        """メッセージを保存する

        既存のメッセージ（同一の message_id, channel_id）が存在する場合は更新する。

        Args:
            message: 保存するメッセージ
        """
        ...

    async def find_by_channel(
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

    async def find_by_channel_since(
        self,
        channel_id: str,
        since: datetime,
        limit: int = 20,
    ) -> list[Message]:
        """指定時刻以降のチャンネルメッセージを取得する

        スレッドに属さないメッセージのみを取得する。

        Args:
            channel_id: チャンネル ID
            since: この時刻より後のメッセージを取得
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    async def find_by_thread(
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

    async def find_by_id(self, message_id: str, channel_id: str) -> Message | None:
        """ID でメッセージを検索する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID

        Returns:
            メッセージ（存在しない場合は None）
        """
        ...

    async def delete(self, message_id: str, channel_id: str) -> None:
        """メッセージを削除する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID
        """
        ...

    async def find_all_in_channel(
        self,
        channel_id: str,
        limit: int = 50,
        min_timestamp: datetime | None = None,
        max_timestamp: datetime | None = None,
        exclude_bot_user_id: str | None = None,
    ) -> list[Message]:
        """チャンネルの全メッセージを取得する（スレッド内メッセージを含む）

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数
            min_timestamp: この時刻より後のメッセージを取得
            max_timestamp: この時刻以前のメッセージを取得
            exclude_bot_user_id: 除外するボットのユーザー ID

        Returns:
            メッセージリスト（新しい順）
        """
        ...
