# 03: MemoryRepository プロトコルと SQLite 実装

## 目的

記憶の永続化を担当するリポジトリを定義・実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/repositories/memory_repository.py` | MemoryRepository Protocol（新規） |
| `src/myao2/domain/repositories/__init__.py` | MemoryRepository エクスポート（修正） |
| `src/myao2/infrastructure/persistence/models.py` | MemoryModel 追加（修正） |
| `src/myao2/infrastructure/persistence/memory_repository.py` | SQLiteMemoryRepository（新規） |
| `src/myao2/infrastructure/persistence/__init__.py` | SQLiteMemoryRepository エクスポート（修正） |
| `tests/infrastructure/persistence/test_memory_repository.py` | リポジトリテスト（新規） |

---

## 依存関係

- タスク 02（Memory エンティティ）に依存

---

## インターフェース設計

### MemoryRepository Protocol

```python
from typing import Protocol

from myao2.domain.entities.memory import Memory, MemoryScope, MemoryType


class MemoryRepository(Protocol):
    """記憶リポジトリ"""

    async def save(self, memory: Memory) -> None:
        """記憶を保存（upsert）

        同じ scope, scope_id, memory_type の記憶が存在する場合は更新する。

        Args:
            memory: 保存する記憶
        """
        ...

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
        ...

    async def find_all_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> list[Memory]:
        """スコープとスコープIDで全記憶を取得

        同じスコープ・スコープIDでも、memory_type が異なる記憶
        （LONG_TERM と SHORT_TERM）が複数存在する可能性があるため
        リストを返す。

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID

        Returns:
            該当する記憶のリスト（最大2件: LONG_TERM と SHORT_TERM）
        """
        ...

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
        ...

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
        ...
```

---

## SQLite モデル

### MemoryModel

```python
from datetime import datetime

from sqlmodel import Field, SQLModel


class MemoryModel(SQLModel, table=True):
    """記憶の永続化モデル"""

    __tablename__ = "memories"

    id: int | None = Field(default=None, primary_key=True)
    scope: str = Field(index=True)
    scope_id: str = Field(index=True)
    memory_type: str = Field(index=True)
    content: str
    created_at: datetime
    updated_at: datetime
    source_message_count: int
    source_latest_message_ts: str | None = None

    class Config:
        # scope, scope_id, memory_type の組み合わせでユニーク
        table_args = (
            UniqueConstraint("scope", "scope_id", "memory_type"),
        )
```

### テーブル定義

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    source_message_count INTEGER NOT NULL,
    source_latest_message_ts TEXT,
    UNIQUE(scope, scope_id, memory_type)
);

CREATE INDEX ix_memories_scope ON memories(scope);
CREATE INDEX ix_memories_scope_id ON memories(scope_id);
CREATE INDEX ix_memories_memory_type ON memories(memory_type);
```

---

## SQLiteMemoryRepository 実装

```python
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from myao2.domain.entities.memory import Memory, MemoryScope, MemoryType
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.infrastructure.persistence.models import MemoryModel


class SQLiteMemoryRepository(MemoryRepository):
    """SQLite による記憶リポジトリ実装"""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, memory: Memory) -> None:
        async with self._session_factory() as session:
            # 既存の記憶を検索
            stmt = select(MemoryModel).where(
                MemoryModel.scope == memory.scope.value,
                MemoryModel.scope_id == memory.scope_id,
                MemoryModel.memory_type == memory.memory_type.value,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # 更新
                existing.content = memory.content
                existing.updated_at = memory.updated_at
                existing.source_message_count = memory.source_message_count
                existing.source_latest_message_ts = memory.source_latest_message_ts
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
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
                MemoryModel.memory_type == memory_type.value,
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None

    async def find_all_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> list[Memory]:
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_entity(m) for m in models]

    async def delete_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
                MemoryModel.memory_type == memory_type.value,
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                await session.delete(model)
                await session.commit()

    async def delete_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(MemoryModel).where(
                MemoryModel.scope == scope.value,
                MemoryModel.scope_id == scope_id,
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
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
            created_at=model.created_at,
            updated_at=model.updated_at,
            source_message_count=model.source_message_count,
            source_latest_message_ts=model.source_latest_message_ts,
        )
```

---

## テストケース

### save

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規保存 | 存在しない記憶 | 記憶が保存される |
| 更新 | 既存の記憶 | 記憶が更新される（ID は維持） |
| upsert | 同じ scope, scope_id, type | 1件のみ存在 |

### find_by_scope_and_type

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 存在する | 該当する記憶あり | Memory が返る |
| 存在しない | 該当する記憶なし | None が返る |

### find_all_by_scope

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数記憶 | 同スコープに LONG_TERM と SHORT_TERM | 2件がリストで返る |
| 記憶なし | 該当する記憶なし | 空リストが返る |

### delete_by_scope_and_type

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 存在する | 該当する記憶あり | 記憶が削除される |
| 存在しない | 該当する記憶なし | エラーなし |

### delete_by_scope

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数記憶 | 同スコープに複数記憶 | 全記憶が削除される |

---

## 完了基準

- [ ] MemoryRepository Protocol が定義されている
- [ ] MemoryModel が定義されている
- [ ] SQLiteMemoryRepository が実装されている
- [ ] save で upsert が行われる
- [ ] 検索メソッドが正しく動作する
- [ ] 削除メソッドが正しく動作する
- [ ] `__init__.py` でエクスポートされている
- [ ] 全テストケースが通過する
