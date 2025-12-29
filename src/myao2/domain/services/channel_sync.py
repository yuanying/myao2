"""Channel sync service protocol."""

from typing import Protocol

from myao2.domain.entities import Channel


class ChannelSyncService(Protocol):
    """チャンネル同期サービスの抽象インターフェース

    外部サービス（Slack等）からチャンネル情報を取得し、
    データベースと同期する機能を提供する。
    """

    async def sync_with_cleanup(self) -> tuple[list[Channel], list[str]]:
        """チャンネルを同期し、不要なチャンネルを削除する

        外部サービスからチャンネル一覧を取得し、DBと同期する。
        外部サービスに存在しないチャンネルはDBから削除する。

        Returns:
            tuple[list[Channel], list[str]]: 同期されたチャンネルリストと
                削除されたチャンネルIDのリスト
        """
        ...
