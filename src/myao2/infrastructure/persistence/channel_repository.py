"""SQLite implementation of ChannelRepository."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel
from myao2.infrastructure.persistence.models import ChannelModel


class SQLiteChannelRepository:
    """SQLite 版 ChannelRepository 実装

    チャンネル情報の CRUD 操作を SQLite データベースに対して行う。
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

    async def save(self, channel: Channel) -> None:
        """チャンネル情報を保存する（upsert）

        既存のチャンネルが存在する場合は更新する。

        Args:
            channel: 保存するチャンネル
        """
        async with self._session_factory() as session:
            result = await session.exec(
                select(ChannelModel).where(ChannelModel.channel_id == channel.id)
            )
            existing = result.first()

            if existing:
                # 更新
                existing.name = channel.name
                existing.updated_at = datetime.now(timezone.utc)
                session.add(existing)
            else:
                # 新規作成
                model = self._to_model(channel)
                session.add(model)

            await session.commit()

    async def find_all(self) -> list[Channel]:
        """全チャンネルを取得する

        Returns:
            チャンネルリスト
        """
        async with self._session_factory() as session:
            statement = select(ChannelModel)
            result = await session.exec(statement)
            models = result.all()
            return [self._to_entity(m) for m in models]

    async def find_by_id(self, channel_id: str) -> Channel | None:
        """ID でチャンネルを検索する

        Args:
            channel_id: チャンネル ID

        Returns:
            チャンネル（存在しない場合は None）
        """
        async with self._session_factory() as session:
            statement = select(ChannelModel).where(
                ChannelModel.channel_id == channel_id
            )
            result = await session.exec(statement)
            model = result.first()
            if model is None:
                return None
            return self._to_entity(model)

    def _to_entity(self, model: ChannelModel) -> Channel:
        """モデルをエンティティに変換する

        Args:
            model: ChannelModel インスタンス

        Returns:
            Channel エンティティ
        """
        return Channel(
            id=model.channel_id,
            name=model.name,
        )

    def _to_model(self, entity: Channel) -> ChannelModel:
        """エンティティをモデルに変換する

        Args:
            entity: Channel エンティティ

        Returns:
            ChannelModel インスタンス
        """
        return ChannelModel(
            channel_id=entity.id,
            name=entity.name,
        )
