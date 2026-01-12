"""SQLite implementation of MemoRepository."""

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import delete, func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from myao2.domain.entities.memo import Memo, TagStats
from myao2.infrastructure.persistence.models import MemoModel


class SQLiteMemoRepository:
    """SQLite 版 MemoRepository 実装

    メモの CRUD 操作を SQLite データベースに対して行う。
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

    async def save(self, memo: Memo) -> None:
        """メモを保存（upsert）

        同じ ID のメモが存在する場合は更新する。

        Args:
            memo: 保存するメモ
        """
        async with self._session_factory() as session:
            model = MemoModel(
                id=str(memo.id),
                name=memo.name,
                content=memo.content,
                priority=memo.priority,
                tags=memo.tags,
                detail=memo.detail,
                created_at=memo.created_at,
                updated_at=memo.updated_at,
            )
            await session.merge(model)
            await session.commit()

    async def find_by_id(self, memo_id: UUID) -> Memo | None:
        """ID でメモを検索

        Args:
            memo_id: メモの ID

        Returns:
            見つかったメモ、または None
        """
        async with self._session_factory() as session:
            result = await session.get(MemoModel, str(memo_id))
            if result is None:
                return None
            return self._to_entity(result)

    async def find_by_name(self, name: str) -> Memo | None:
        """name でメモを検索

        Args:
            name: メモの name

        Returns:
            見つかったメモ、または None
        """
        async with self._session_factory() as session:
            stmt = select(MemoModel).where(MemoModel.name == name)
            result = await session.exec(stmt)
            model = result.first()
            if model is None:
                return None
            return self._to_entity(model)

    async def exists_by_name(self, name: str) -> bool:
        """指定された name のメモが存在するか確認

        Args:
            name: 確認する name

        Returns:
            存在する場合 True、存在しない場合 False
        """
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(MemoModel)
                .where(MemoModel.name == name)
            )
            result = await session.execute(stmt)
            count = result.scalar() or 0
            return count > 0

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
        async with self._session_factory() as session:
            stmt = (
                select(MemoModel)
                .order_by(
                    MemoModel.priority.desc(),  # type: ignore[union-attr]
                    MemoModel.updated_at.desc(),  # type: ignore[union-attr]
                )
                .offset(offset)
                .limit(limit)
            )
            result = await session.exec(stmt)
            return [self._to_entity(row) for row in result.all()]

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
        async with self._session_factory() as session:
            stmt = (
                select(MemoModel)
                .where(MemoModel.priority >= min_priority)
                .order_by(
                    MemoModel.priority.desc(),  # type: ignore[union-attr]
                    MemoModel.updated_at.desc(),  # type: ignore[union-attr]
                )
                .limit(limit)
            )
            result = await session.exec(stmt)
            return [self._to_entity(row) for row in result.all()]

    async def find_recent(self, limit: int = 5) -> list[Memo]:
        """直近のメモを取得

        更新日時降順でソート。

        Args:
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        async with self._session_factory() as session:
            stmt = (
                select(MemoModel)
                .order_by(MemoModel.updated_at.desc())  # type: ignore[union-attr]
                .limit(limit)
            )
            result = await session.exec(stmt)
            return [self._to_entity(row) for row in result.all()]

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
        async with self._session_factory() as session:
            # json_each() を使用してタグを検索
            stmt = text("""
                SELECT DISTINCT m.*
                FROM memos m, json_each(m.tags) AS t
                WHERE t.value = :tag
                ORDER BY m.priority DESC, m.updated_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await session.execute(
                stmt, {"tag": tag, "limit": limit, "offset": offset}
            )
            rows = result.mappings().all()
            return [
                self._row_to_entity(row)  # type: ignore[arg-type]
                for row in rows
            ]

    async def get_all_tags_with_stats(self) -> list[TagStats]:
        """全タグの統計情報を取得

        使用数降順でソート。

        Returns:
            TagStats のリスト
        """
        async with self._session_factory() as session:
            stmt = text("""
                SELECT
                    t.value AS tag,
                    COUNT(*) AS count,
                    MAX(m.updated_at) AS latest_updated_at
                FROM memos m, json_each(m.tags) AS t
                GROUP BY t.value
                ORDER BY count DESC
            """)
            result = await session.execute(stmt)
            rows = result.mappings().all()
            return [
                TagStats(
                    tag=row["tag"],
                    count=row["count"],
                    latest_updated_at=self._parse_datetime_field(
                        row["latest_updated_at"]
                    ),
                )
                for row in rows
            ]

    async def delete_by_name(self, name: str) -> bool:
        """メモを削除

        Args:
            name: 削除するメモの name

        Returns:
            削除成功の場合 True、メモが存在しない場合 False
        """
        async with self._session_factory() as session:
            stmt = delete(MemoModel).where(
                MemoModel.name == name  # type: ignore[arg-type]
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]

    async def count(self, tag: str | None = None) -> int:
        """メモの件数を取得

        Args:
            tag: 指定した場合、そのタグを持つメモの件数を返す

        Returns:
            メモの件数
        """
        async with self._session_factory() as session:
            if tag is None:
                stmt = select(func.count()).select_from(MemoModel)
                result = await session.execute(stmt)
                return result.scalar() or 0
            else:
                stmt = text("""
                    SELECT COUNT(DISTINCT m.id)
                    FROM memos m, json_each(m.tags) AS t
                    WHERE t.value = :tag
                """)
                result = await session.execute(stmt, {"tag": tag})
                return result.scalar() or 0

    @staticmethod
    def _parse_json_field(value: Any) -> list[str]:
        """JSON フィールドをパース

        Args:
            value: JSON 文字列または list

        Returns:
            list[str]
        """
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _parse_datetime_field(value: Any) -> datetime:
        """datetime フィールドをパース

        Args:
            value: ISO形式の文字列または datetime

        Returns:
            datetime
        """
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    def _to_entity(self, model: MemoModel) -> Memo:
        """MemoModel を Memo エンティティに変換

        Args:
            model: MemoModel インスタンス

        Returns:
            Memo エンティティ
        """
        return Memo(
            id=UUID(model.id),
            name=model.name,
            content=model.content,
            priority=model.priority,
            tags=model.tags,
            detail=model.detail,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _row_to_entity(self, row: Mapping[str, Any]) -> Memo:
        """SQL結果行を Memo エンティティに変換

        Args:
            row: SQL結果行

        Returns:
            Memo エンティティ
        """
        return Memo(
            id=UUID(row["id"]),
            name=row["name"],
            content=row["content"],
            priority=row["priority"],
            tags=self._parse_json_field(row["tags"]),
            detail=row["detail"],
            created_at=self._parse_datetime_field(row["created_at"]),
            updated_at=self._parse_datetime_field(row["updated_at"]),
        )
