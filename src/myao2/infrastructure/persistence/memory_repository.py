"""SQLite implementation of MemoryRepository."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities.memory import Memory, MemoryScope, MemoryType
from myao2.infrastructure.persistence.datetime_utils import normalize_to_utc
from myao2.infrastructure.persistence.models import MemoryModel


class SQLiteMemoryRepository:
    """SQLite による記憶リポジトリ実装"""

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        """初期化

        Args:
            session_factory: 非同期セッション生成関数
        """
        self._session_factory = session_factory

    async def save(self, memory: Memory) -> None:
        """記憶を保存（upsert）

        同じ scope, scope_id, memory_type の記憶が存在する場合は更新する。

        Args:
            memory: 保存する記憶
        """
        async with self._session_factory() as session:
            # 既存の記憶を検索
            stmt = select(MemoryModel).where(
                MemoryModel.scope == memory.scope.value,
                MemoryModel.scope_id == memory.scope_id,
                MemoryModel.memory_type == memory.memory_type.value,
            )
            result = await session.exec(stmt)
            existing = result.first()

            if existing:
                # 更新
                existing.content = memory.content
                existing.updated_at = memory.updated_at
                existing.source_message_count = memory.source_message_count
                existing.source_latest_message_ts = memory.source_latest_message_ts
                session.add(existing)
            else:
                # 新規作成
                model = self._to_model(memory)
                session.add(model)

            await session.commit()

    async def find_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> Memory | None:
        """スコープ、スコープID、タイプで記憶を検索

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
            memory_type: 記憶の種類

        Returns:
            見つかった記憶、または None
        """
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
                MemoryModel.memory_type == memory_type.value,
            )
            result = await session.exec(stmt)
            model = result.first()
            return self._to_entity(model) if model else None

    async def find_all_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> list[Memory]:
        """スコープとスコープIDで全記憶を取得

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID

        Returns:
            該当する記憶のリスト
        """
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
            )
            result = await session.exec(stmt)
            models = result.all()
            return [self._to_entity(m) for m in models]

    async def delete_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> None:
        """スコープ、スコープID、タイプで記憶を削除

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
            memory_type: 記憶の種類
        """
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
                MemoryModel.memory_type == memory_type.value,
            )
            result = await session.exec(stmt)
            model = result.first()
            if model:
                await session.delete(model)
                await session.commit()

    async def delete_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> None:
        """スコープとスコープIDで記憶を削除

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
        """
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
            )
            result = await session.exec(stmt)
            models = result.all()
            for model in models:
                await session.delete(model)
            await session.commit()

    def _to_model(self, memory: Memory) -> MemoryModel:
        """Memory エンティティを MemoryModel に変換"""
        return MemoryModel(
            scope=memory.scope.value,
            scope_id=memory.scope_id,
            memory_type=memory.memory_type.value,
            content=memory.content,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            source_message_count=memory.source_message_count,
            source_latest_message_ts=memory.source_latest_message_ts,
        )

    def _to_entity(self, model: MemoryModel) -> Memory:
        """MemoryModel を Memory エンティティに変換"""
        return Memory(
            scope=MemoryScope(model.scope),
            scope_id=model.scope_id,
            memory_type=MemoryType(model.memory_type),
            content=model.content,
            created_at=normalize_to_utc(model.created_at),
            updated_at=normalize_to_utc(model.updated_at),
            source_message_count=model.source_message_count,
            source_latest_message_ts=model.source_latest_message_ts,
        )
