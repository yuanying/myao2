"""SQLite implementation of JudgmentCacheRepository."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities.judgment_cache import JudgmentCache
from myao2.infrastructure.persistence.models import JudgmentCacheModel


class SQLiteJudgmentCacheRepository:
    """SQLite 版 JudgmentCacheRepository 実装

    応答判定キャッシュの CRUD 操作を SQLite データベースに対して行う。
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

    async def save(self, cache: JudgmentCache) -> None:
        """キャッシュを保存（upsert）

        channel_id + thread_ts が同じレコードは更新する。

        Args:
            cache: 保存するキャッシュ
        """
        async with self._session_factory() as session:
            # 既存のキャッシュを検索
            existing = await self._find_model_by_scope(
                session, cache.channel_id, cache.thread_ts
            )

            if existing:
                # 更新
                existing.should_respond = cache.should_respond
                existing.confidence = cache.confidence
                existing.reason = cache.reason
                existing.latest_message_ts = cache.latest_message_ts
                existing.next_check_at = cache.next_check_at
                existing.updated_at = cache.updated_at
                session.add(existing)
            else:
                # 新規作成
                model = self._to_model(cache)
                session.add(model)

            await session.commit()

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
        async with self._session_factory() as session:
            model = await self._find_model_by_scope(session, channel_id, thread_ts)
            if model is None:
                return None
            return self._to_entity(model)

    async def delete_expired(self, before: datetime) -> int:
        """期限切れキャッシュを削除

        next_check_at が指定時刻より前のレコードを削除。

        Args:
            before: この時刻より前の next_check_at を持つキャッシュを削除

        Returns:
            削除したレコード数
        """
        async with self._session_factory() as session:
            statement = select(JudgmentCacheModel).where(
                JudgmentCacheModel.next_check_at < before  # type: ignore[union-attr]
            )
            result = await session.exec(statement)
            expired_models = result.all()

            deleted_count = len(expired_models)
            for model in expired_models:
                await session.delete(model)

            await session.commit()
            return deleted_count

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
        async with self._session_factory() as session:
            model = await self._find_model_by_scope(session, channel_id, thread_ts)
            if model:
                await session.delete(model)
                await session.commit()

    async def _find_model_by_scope(
        self,
        session: AsyncSession,
        channel_id: str,
        thread_ts: str | None,
    ) -> JudgmentCacheModel | None:
        """スコープでモデルを検索（内部用）"""
        if thread_ts is None:
            statement = select(JudgmentCacheModel).where(
                JudgmentCacheModel.channel_id == channel_id,
                JudgmentCacheModel.thread_ts.is_(None),  # type: ignore[union-attr]
            )
        else:
            statement = select(JudgmentCacheModel).where(
                JudgmentCacheModel.channel_id == channel_id,
                JudgmentCacheModel.thread_ts == thread_ts,
            )
        result = await session.exec(statement)
        return result.first()

    def _to_entity(self, model: JudgmentCacheModel) -> JudgmentCache:
        """モデルをエンティティに変換

        Args:
            model: JudgmentCacheModel インスタンス

        Returns:
            JudgmentCache エンティティ
        """
        return JudgmentCache(
            channel_id=model.channel_id,
            thread_ts=model.thread_ts,
            should_respond=model.should_respond,
            confidence=model.confidence,
            reason=model.reason,
            latest_message_ts=model.latest_message_ts,
            next_check_at=model.next_check_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: JudgmentCache) -> JudgmentCacheModel:
        """エンティティをモデルに変換

        Args:
            entity: JudgmentCache エンティティ

        Returns:
            JudgmentCacheModel インスタンス
        """
        return JudgmentCacheModel(
            channel_id=entity.channel_id,
            thread_ts=entity.thread_ts,
            should_respond=entity.should_respond,
            confidence=entity.confidence,
            reason=entity.reason,
            latest_message_ts=entity.latest_message_ts,
            next_check_at=entity.next_check_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
