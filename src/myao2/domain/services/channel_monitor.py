"""Channel monitor protocol."""

from datetime import datetime
from typing import Protocol

from myao2.domain.entities import Channel, Message


class ChannelMonitor(Protocol):
    """チャンネル監視サービス

    ボットが参加しているチャンネルを監視し、
    応答判定が必要なメッセージを検出する。
    """

    async def get_channels(self) -> list[Channel]:
        """ボットが参加しているチャンネル一覧を取得する

        Returns:
            チャンネルリスト
        """
        ...

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルの最近のメッセージを取得する

        Args:
            channel_id: チャンネル ID
            since: この時刻以降のメッセージを取得（None の場合は制限なし）
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    async def get_unreplied_messages(
        self,
        channel_id: str,
        min_wait_seconds: int,
    ) -> list[Message]:
        """未応答メッセージを取得する

        指定時間以上経過し、かつボットが応答していないメッセージを取得する。

        Args:
            channel_id: チャンネル ID
            min_wait_seconds: 最低待機時間（秒）

        Returns:
            未応答メッセージリスト
        """
        ...
