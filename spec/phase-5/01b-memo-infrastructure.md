# 01b: Memo インフラ層 - 詳細設計書

## 概要

SQLiteMemoRepository と MemoModel を実装する。

---

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/persistence/memo_repository.py` | SQLiteMemoRepository |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/persistence/models.py` | MemoModel 追加 |
| `src/myao2/infrastructure/persistence/__init__.py` | SQLiteMemoRepository エクスポート追加 |

## テストファイル

| ファイル | 説明 |
|---------|------|
| `tests/infrastructure/persistence/test_memo_repository.py` | SQLiteMemoRepository のテスト |

---

## MemoModel

SQLModel を使用したテーブル定義。

```python
from sqlalchemy import JSON

class MemoModel(SQLModel, table=True):
    """メモテーブル"""
    __tablename__ = "memos"

    id: str = Field(primary_key=True)  # UUID を文字列として保存
    content: str
    priority: int = Field(index=True)
    tags: list[str] = Field(default_factory=list, sa_type=JSON)  # SQLite JSON型
    detail: str | None = Field(default=None)
    created_at: datetime
    updated_at: datetime = Field(index=True)
```

### インデックス

- `priority`: 優先度検索用
- `updated_at`: 更新日時ソート用

### タグの保存

SQLite の JSON 型（`sa_type=JSON`）を使用:
- Python の `list[str]` をそのまま保存
- SQLite3 の `json_each()` 関数でタグ検索

---

## SQLiteMemoRepository

### コンストラクタ

```python
class SQLiteMemoRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
```

### save

```python
async def save(self, memo: Memo) -> None:
    """メモを保存（upsert）"""
    async with self._session_factory() as session:
        model = MemoModel(
            id=str(memo.id),
            content=memo.content,
            priority=memo.priority,
            tags=memo.tags,
            detail=memo.detail,
            created_at=memo.created_at,
            updated_at=memo.updated_at,
        )
        await session.merge(model)
        await session.commit()
```

### find_by_id

```python
async def find_by_id(self, memo_id: UUID) -> Memo | None:
    """ID でメモを検索"""
    async with self._session_factory() as session:
        result = await session.get(MemoModel, str(memo_id))
        if result is None:
            return None
        return self._to_entity(result)
```

### find_all

```python
async def find_all(
    self,
    offset: int = 0,
    limit: int = 10,
) -> list[Memo]:
    """全メモを取得（優先度降順 → 更新日時降順）"""
    async with self._session_factory() as session:
        stmt = (
            select(MemoModel)
            .order_by(MemoModel.priority.desc(), MemoModel.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
```

### find_by_priority_gte

```python
async def find_by_priority_gte(
    self,
    min_priority: int,
    limit: int = 20,
) -> list[Memo]:
    """指定優先度以上のメモを取得"""
    async with self._session_factory() as session:
        stmt = (
            select(MemoModel)
            .where(MemoModel.priority >= min_priority)
            .order_by(MemoModel.priority.desc(), MemoModel.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
```

### find_recent

```python
async def find_recent(self, limit: int = 5) -> list[Memo]:
    """直近のメモを取得（更新日時降順）"""
    async with self._session_factory() as session:
        stmt = (
            select(MemoModel)
            .order_by(MemoModel.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
```

### find_by_tag

SQLite の `json_each()` 関数を使用してタグを検索。

```python
async def find_by_tag(
    self,
    tag: str,
    offset: int = 0,
    limit: int = 10,
) -> list[Memo]:
    """タグでメモを検索"""
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
        return [self._row_to_entity(row) for row in rows]
```

### get_all_tags_with_stats

```python
async def get_all_tags_with_stats(self) -> list[TagStats]:
    """全タグの統計情報を取得"""
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
                latest_updated_at=datetime.fromisoformat(row["latest_updated_at"]),
            )
            for row in rows
        ]
```

### delete

```python
async def delete(self, memo_id: UUID) -> bool:
    """メモを削除"""
    async with self._session_factory() as session:
        stmt = delete(MemoModel).where(MemoModel.id == str(memo_id))
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
```

### count

```python
async def count(self, tag: str | None = None) -> int:
    """メモの件数を取得"""
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
```

### ヘルパーメソッド

```python
@staticmethod
def _parse_json_field(value: Any) -> list[str]:
    """JSON フィールドをパース"""
    if isinstance(value, str):
        return json.loads(value)
    return value

@staticmethod
def _parse_datetime_field(value: Any) -> datetime:
    """datetime フィールドをパース"""
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value
```

### _to_entity / _row_to_entity

```python
def _to_entity(self, model: MemoModel) -> Memo:
    """MemoModel を Memo エンティティに変換"""
    return Memo(
        id=UUID(model.id),
        content=model.content,
        priority=model.priority,
        tags=model.tags,
        detail=model.detail,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )

def _row_to_entity(self, row: Mapping[str, Any]) -> Memo:
    """SQL結果行を Memo エンティティに変換"""
    return Memo(
        id=UUID(row["id"]),
        content=row["content"],
        priority=row["priority"],
        tags=self._parse_json_field(row["tags"]),
        detail=row["detail"],
        created_at=self._parse_datetime_field(row["created_at"]),
        updated_at=self._parse_datetime_field(row["updated_at"]),
    )
```

---

## テスト項目

### TestSQLiteMemoRepository

- save: 新規保存
- save: 既存更新（upsert）
- find_by_id: 存在する場合
- find_by_id: 存在しない場合
- find_all: 空の場合
- find_all: 複数件の場合（ソート確認）
- find_all: offset/limit の動作
- find_by_priority_gte: 指定優先度以上のみ取得
- find_by_priority_gte: limit の動作
- find_recent: 更新日時降順の確認
- find_by_tag: タグ検索
- find_by_tag: 該当なしの場合
- find_by_tag: offset/limit の動作
- get_all_tags_with_stats: タグ統計取得
- get_all_tags_with_stats: タグなしの場合
- delete: 存在するメモの削除
- delete: 存在しないメモの削除
- count: 全件カウント
- count: タグ指定カウント
