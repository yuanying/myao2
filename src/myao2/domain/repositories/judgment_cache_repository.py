"""JudgmentCache repository protocol."""

from datetime import datetime
from typing import Protocol

from myao2.domain.entities.judgment_cache import JudgmentCache


class JudgmentCacheRepository(Protocol):
    """応答判定キャッシュリポジトリ"""

    async def save(self, cache: JudgmentCache) -> None:
        """キャッシュを保存（upsert）

        channel_id + thread_ts が同じレコードは更新する。

        Args:
            cache: 保存するキャッシュ
        """
        ...

    async def find_by_scope(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> JudgmentCache | None:
        """スコープでキャッシュを検索

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッド識別子（トップレベルは None）

        Returns:
            キャッシュ（存在しない場合は None）
        """
        ...

    async def delete_expired(self, before: datetime) -> int:
        """期限切れキャッシュを削除

        next_check_at が指定時刻より前のレコードを削除。
        定期的なクリーンアップ用。

        Args:
            before: この時刻より前の next_check_at を持つキャッシュを削除

        Returns:
            削除したレコード数
        """
        ...

    async def delete_by_scope(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> None:
        """スコープのキャッシュを削除

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッド識別子（トップレベルは None）
        """
        ...
