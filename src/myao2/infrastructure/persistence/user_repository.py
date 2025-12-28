"""SQLite implementation of UserRepository."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import User
from myao2.infrastructure.persistence.models import UserModel


class SQLiteUserRepository:
    """SQLite 版 UserRepository 実装

    ユーザー情報の CRUD 操作を SQLite データベースに対して行う。
    非同期セッションを使用した非同期操作をサポート。
    """

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        """初期化

        Args:
            session_factory: 非同期セッション生成関数
        """
        self._session_factory = session_factory

    async def save(self, user: User) -> None:
        """ユーザー情報を保存する（upsert）

        既存のユーザーが存在する場合は更新する。

        Args:
            user: 保存するユーザー
        """
        async with self._session_factory() as session:
            result = await session.exec(
                select(UserModel).where(UserModel.user_id == user.id)
            )
            existing = result.first()

            if existing:
                # 更新
                existing.name = user.name
                existing.is_bot = user.is_bot
                existing.updated_at = datetime.now(timezone.utc)
                session.add(existing)
            else:
                # 新規作成
                model = self._to_model(user)
                session.add(model)

            await session.commit()

    async def find_by_id(self, user_id: str) -> User | None:
        """ID でユーザーを検索する

        Args:
            user_id: ユーザー ID

        Returns:
            ユーザー（存在しない場合は None）
        """
        async with self._session_factory() as session:
            statement = select(UserModel).where(UserModel.user_id == user_id)
            result = await session.exec(statement)
            model = result.first()
            if model is None:
                return None
            return self._to_entity(model)

    def _to_entity(self, model: UserModel) -> User:
        """モデルをエンティティに変換する

        Args:
            model: UserModel インスタンス

        Returns:
            User エンティティ
        """
        return User(
            id=model.user_id,
            name=model.name,
            is_bot=model.is_bot,
        )

    def _to_model(self, entity: User) -> UserModel:
        """エンティティをモデルに変換する

        Args:
            entity: User エンティティ

        Returns:
            UserModel インスタンス
        """
        return UserModel(
            user_id=entity.id,
            name=entity.name,
            is_bot=entity.is_bot,
        )
