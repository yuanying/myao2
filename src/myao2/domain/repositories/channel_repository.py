"""Channel repository protocol."""

from typing import Protocol

from myao2.domain.entities import Channel


class ChannelRepository(Protocol):
    """チャンネル情報リポジトリの抽象インターフェース

    チャンネル情報の保存・取得を抽象化し、
    永続化層の実装詳細を隠蔽する。
    """

    async def save(self, channel: Channel) -> None:
        """チャンネル情報を保存する

        既存のチャンネル（同一の channel_id）が存在する場合は更新する。

        Args:
            channel: 保存するチャンネル
        """
        ...

    async def find_all(self) -> list[Channel]:
        """全チャンネルを取得する

        Returns:
            チャンネルリスト
        """
        ...

    async def find_by_id(self, channel_id: str) -> Channel | None:
        """ID でチャンネルを検索する

        Args:
            channel_id: チャンネル ID

        Returns:
            チャンネル（存在しない場合は None）
        """
        ...
