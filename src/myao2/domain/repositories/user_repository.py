"""User repository protocol."""

from typing import Protocol

from myao2.domain.entities import User


class UserRepository(Protocol):
    """ユーザー情報リポジトリの抽象インターフェース

    ユーザー情報の保存・取得を抽象化し、
    永続化層の実装詳細を隠蔽する。
    """

    async def save(self, user: User) -> None:
        """ユーザー情報を保存する

        既存のユーザー（同一の user_id）が存在する場合は更新する。

        Args:
            user: 保存するユーザー
        """
        ...

    async def find_by_id(self, user_id: str) -> User | None:
        """ID でユーザーを検索する

        Args:
            user_id: ユーザー ID

        Returns:
            ユーザー（存在しない場合は None）
        """
        ...
