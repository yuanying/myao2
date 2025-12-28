"""SQLite implementation of MessageRepository."""

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities import Channel, Message, User
from myao2.infrastructure.persistence.models import MessageModel


class SQLiteMessageRepository:
    """SQLite 版 MessageRepository 実装

    メッセージの CRUD 操作を SQLite データベースに対して行う。
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

    async def save(self, message: Message) -> None:
        """メッセージを保存する（upsert）

        既存のメッセージが存在する場合は更新する。

        Args:
            message: 保存するメッセージ
        """
        async with self._session_factory() as session:
            result = await session.exec(
                select(MessageModel).where(
                    MessageModel.message_id == message.id,
                    MessageModel.channel_id == message.channel.id,
                )
            )
            existing = result.first()

            if existing:
                # 更新
                existing.text = message.text
                existing.user_name = message.user.name
                existing.mentions = json.dumps(message.mentions)
                session.add(existing)
            else:
                # 新規作成
                model = self._to_model(message)
                session.add(model)

            await session.commit()

    async def find_by_channel(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルのメッセージを取得する

        スレッドに属さないメッセージ（thread_ts が None）のみを取得。
        新しい順（timestamp DESC）で返す。

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        async with self._session_factory() as session:
            statement = (
                select(MessageModel)
                .where(
                    MessageModel.channel_id == channel_id,
                    MessageModel.thread_ts.is_(None),  # type: ignore[union-attr]
                )
                .order_by(MessageModel.timestamp.desc())  # type: ignore[union-attr]
                .limit(limit)
            )
            result = await session.exec(statement)
            models = result.all()
            return [self._to_entity(m) for m in models]

    async def find_by_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドのメッセージを取得する

        指定したスレッドに属するメッセージを取得。
        新しい順（timestamp DESC）で返す。

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        async with self._session_factory() as session:
            statement = (
                select(MessageModel)
                .where(
                    MessageModel.channel_id == channel_id,
                    MessageModel.thread_ts == thread_ts,
                )
                .order_by(MessageModel.timestamp.desc())  # type: ignore[union-attr]
                .limit(limit)
            )
            result = await session.exec(statement)
            models = result.all()
            return [self._to_entity(m) for m in models]

    async def find_by_id(self, message_id: str, channel_id: str) -> Message | None:
        """ID でメッセージを検索する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID

        Returns:
            メッセージ（存在しない場合は None）
        """
        async with self._session_factory() as session:
            statement = select(MessageModel).where(
                MessageModel.message_id == message_id,
                MessageModel.channel_id == channel_id,
            )
            result = await session.exec(statement)
            model = result.first()
            if model is None:
                return None
            return self._to_entity(model)

    def _to_entity(self, model: MessageModel) -> Message:
        """モデルをエンティティに変換する

        Args:
            model: MessageModel インスタンス

        Returns:
            Message エンティティ
        """
        user = User(
            id=model.user_id,
            name=model.user_name,
            is_bot=model.user_is_bot,
        )
        channel = Channel(
            id=model.channel_id,
            name="",  # チャンネル名は永続化しない
        )
        mentions = json.loads(model.mentions) if model.mentions else []

        return Message(
            id=model.message_id,
            channel=channel,
            user=user,
            text=model.text,
            timestamp=model.timestamp,
            thread_ts=model.thread_ts,
            mentions=mentions,
        )

    def _to_model(self, entity: Message) -> MessageModel:
        """エンティティをモデルに変換する

        Args:
            entity: Message エンティティ

        Returns:
            MessageModel インスタンス
        """
        return MessageModel(
            message_id=entity.id,
            channel_id=entity.channel.id,
            user_id=entity.user.id,
            user_name=entity.user.name,
            user_is_bot=entity.user.is_bot,
            text=entity.text,
            timestamp=entity.timestamp,
            thread_ts=entity.thread_ts,
            mentions=json.dumps(entity.mentions),
        )
