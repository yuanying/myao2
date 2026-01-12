"""MemoRepository Protocol."""

from typing import Protocol
from uuid import UUID

from myao2.domain.entities.memo import Memo, TagStats


class MemoRepository(Protocol):
    """メモリポジトリ"""

    async def save(self, memo: Memo) -> None:
        """メモを保存（upsert）

        同じ ID のメモが存在する場合は更新する。

        Args:
            memo: 保存するメモ
        """
        ...

    async def find_by_id(self, memo_id: UUID) -> Memo | None:
        """ID でメモを検索

        Args:
            memo_id: メモの ID

        Returns:
            見つかったメモ、または None
        """
        ...

    async def find_by_name(self, name: str) -> Memo | None:
        """name でメモを検索

        Args:
            name: メモの name

        Returns:
            見つかったメモ、または None
        """
        ...

    async def exists_by_name(self, name: str) -> bool:
        """指定された name のメモが存在するか確認

        Args:
            name: 確認する name

        Returns:
            存在する場合 True、存在しない場合 False
        """
        ...

    async def find_all(
        self,
        offset: int = 0,
        limit: int = 10,
    ) -> list[Memo]:
        """全メモを取得

        優先度降順 → 更新日時降順でソート。

        Args:
            offset: スキップする件数
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        ...

    async def find_by_priority_gte(
        self,
        min_priority: int,
        limit: int = 20,
    ) -> list[Memo]:
        """指定優先度以上のメモを取得

        優先度降順 → 更新日時降順でソート。

        Args:
            min_priority: 最小優先度
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        ...

    async def find_recent(self, limit: int = 5) -> list[Memo]:
        """直近のメモを取得

        更新日時降順でソート。

        Args:
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        ...

    async def find_by_tag(
        self,
        tag: str,
        offset: int = 0,
        limit: int = 10,
    ) -> list[Memo]:
        """タグでメモを検索

        優先度降順 → 更新日時降順でソート。

        Args:
            tag: 検索するタグ
            offset: スキップする件数
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        ...

    async def get_all_tags_with_stats(self) -> list[TagStats]:
        """全タグの統計情報を取得

        使用数降順でソート。

        Returns:
            TagStats のリスト
        """
        ...

    async def delete_by_name(self, name: str) -> bool:
        """メモを削除

        Args:
            name: 削除するメモの name

        Returns:
            削除成功の場合 True、メモが存在しない場合 False
        """
        ...

    async def count(self, tag: str | None = None) -> int:
        """メモの件数を取得

        Args:
            tag: 指定した場合、そのタグを持つメモの件数を返す

        Returns:
            メモの件数
        """
        ...
