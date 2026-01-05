# 01c: リポジトリの履歴対応

## 目的

MemoryRepository に履歴を取得・管理するメソッドを追加する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/repositories/memory_repository.py` | Protocol に履歴メソッド追加（修正） |
| `src/myao2/infrastructure/persistence/memory_repository.py` | SQLite 実装に履歴メソッド追加（修正） |
| `tests/infrastructure/persistence/test_memory_repository.py` | 履歴メソッドテスト追加（修正） |

---

## インターフェース設計

### MemoryRepository Protocol の拡張

```python
class MemoryRepository(Protocol):
    """記憶リポジトリ Protocol"""

    # 既存メソッド
    async def save(self, memory: Memory) -> None:
        """記憶を保存（upsert）

        長期記憶: version=1 で上書き
        スレッド短期記憶: version=1 で上書き
        """
        ...

    async def find_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> Memory | None:
        """スコープとタイプで記憶を取得（最新バージョン）"""
        ...

    async def find_all_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> list[Memory]:
        """スコープで全記憶を取得"""
        ...

    async def delete_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> None:
        """スコープとタイプで記憶を削除（全バージョン）"""
        ...

    async def delete_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> None:
        """スコープで記憶を削除"""
        ...

    # 追加メソッド
    async def save_as_new_version(self, memory: Memory) -> Memory:
        """新しいバージョンとして保存

        チャンネル短期記憶の履歴化に使用。
        現在の最大 version + 1 で保存し、保存後の Memory を返す。

        Args:
            memory: 保存する記憶（version は無視され、新しい version が割り当てられる）

        Returns:
            新しい version が設定された Memory
        """
        ...

    async def find_history_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
        limit: int = 10,
    ) -> list[Memory]:
        """履歴を取得（新しい順）

        Args:
            scope: スコープ
            scope_id: スコープ ID
            memory_type: 記憶タイプ
            limit: 取得件数

        Returns:
            Memory のリスト（version 降順）
        """
        ...

    async def get_latest_version(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> int:
        """最新バージョン番号を取得

        Args:
            scope: スコープ
            scope_id: スコープ ID
            memory_type: 記憶タイプ

        Returns:
            最新の version 番号。存在しない場合は 0
        """
        ...
```

---

## SQLiteMemoryRepository の実装

### save_as_new_version

```python
async def save_as_new_version(self, memory: Memory) -> Memory:
    """新しいバージョンとして保存"""
    # 1. 現在の最新 version を取得
    latest_version = await self.get_latest_version(
        memory.scope, memory.scope_id, memory.memory_type
    )

    # 2. 新しい version で Memory を作成
    new_version = latest_version + 1
    new_memory = Memory(
        scope=memory.scope,
        scope_id=memory.scope_id,
        memory_type=memory.memory_type,
        content=memory.content,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        source_message_count=memory.source_message_count,
        source_latest_message_ts=memory.source_latest_message_ts,
        version=new_version,
    )

    # 3. INSERT（新規作成）
    with Session(self._engine) as session:
        model = MemoryModel(
            scope=new_memory.scope.value,
            scope_id=new_memory.scope_id,
            memory_type=new_memory.memory_type.value,
            content=new_memory.content,
            created_at=new_memory.created_at,
            updated_at=new_memory.updated_at,
            source_message_count=new_memory.source_message_count,
            source_latest_message_ts=new_memory.source_latest_message_ts,
            version=new_memory.version,
        )
        session.add(model)
        session.commit()

    return new_memory
```

### find_history_by_scope_and_type

```python
async def find_history_by_scope_and_type(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    limit: int = 10,
) -> list[Memory]:
    """履歴を取得（新しい順）"""
    with Session(self._engine) as session:
        statement = (
            select(MemoryModel)
            .where(MemoryModel.scope == scope.value)
            .where(MemoryModel.scope_id == scope_id)
            .where(MemoryModel.memory_type == memory_type.value)
            .order_by(MemoryModel.version.desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [self._to_entity(model) for model in results]
```

### get_latest_version

```python
async def get_latest_version(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
) -> int:
    """最新バージョン番号を取得"""
    with Session(self._engine) as session:
        statement = (
            select(func.max(MemoryModel.version))
            .where(MemoryModel.scope == scope.value)
            .where(MemoryModel.scope_id == scope_id)
            .where(MemoryModel.memory_type == memory_type.value)
        )
        result = session.exec(statement).one_or_none()
        return result if result is not None else 0
```

---

## 既存メソッドの変更

### find_by_scope_and_type

最新バージョンを返すように変更：

```python
async def find_by_scope_and_type(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
) -> Memory | None:
    """スコープとタイプで記憶を取得（最新バージョン）"""
    with Session(self._engine) as session:
        statement = (
            select(MemoryModel)
            .where(MemoryModel.scope == scope.value)
            .where(MemoryModel.scope_id == scope_id)
            .where(MemoryModel.memory_type == memory_type.value)
            .order_by(MemoryModel.version.desc())
            .limit(1)
        )
        model = session.exec(statement).first()
        return self._to_entity(model) if model else None
```

### delete_by_scope_and_type

全バージョンを削除：

```python
async def delete_by_scope_and_type(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
) -> None:
    """スコープとタイプで記憶を削除（全バージョン）"""
    with Session(self._engine) as session:
        statement = (
            delete(MemoryModel)
            .where(MemoryModel.scope == scope.value)
            .where(MemoryModel.scope_id == scope_id)
            .where(MemoryModel.memory_type == memory_type.value)
        )
        session.exec(statement)
        session.commit()
```

---

## テストケース

### save_as_new_version

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 初回保存 | 履歴なしで保存 | version=1 で保存される |
| 2回目保存 | 1件の履歴がある状態で保存 | version=2 で保存される |
| 連続保存 | 複数回連続で保存 | version が順番にインクリメント |
| 返り値 | 保存後 | 新しい version が設定された Memory が返る |

### find_history_by_scope_and_type

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | データがない | 空リスト |
| 1件 | 1件の履歴 | 1件のリスト |
| 複数件 | 5件の履歴、limit=3 | 3件のリスト（version 降順） |
| 順序 | 複数件の履歴 | 新しい version が先頭 |

### get_latest_version

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | データがない | 0 |
| 1件 | version=1 のみ | 1 |
| 複数件 | version=1,2,3 | 3 |

### find_by_scope_and_type（変更後）

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | データがない | None |
| 1件 | version=1 のみ | version=1 の Memory |
| 複数件 | version=1,2,3 | version=3 の Memory（最新） |

---

## 完了基準

- [ ] MemoryRepository Protocol に新メソッドが追加されている
- [ ] SQLiteMemoryRepository に新メソッドが実装されている
- [ ] find_by_scope_and_type が最新バージョンを返すように変更されている
- [ ] delete_by_scope_and_type が全バージョンを削除するように変更されている
- [ ] 全テストケースが通過する
