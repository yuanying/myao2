# 01a: Memo ドメイン層 - 詳細設計書

## 概要

Memo エンティティと MemoRepository Protocol を定義する。

---

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memo.py` | Memo エンティティ、TagStats データクラス |
| `src/myao2/domain/repositories/memo_repository.py` | MemoRepository Protocol |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/entities/__init__.py` | Memo, TagStats, create_memo エクスポート追加 |
| `src/myao2/domain/repositories/__init__.py` | MemoRepository エクスポート追加 |

## テストファイル

| ファイル | 説明 |
|---------|------|
| `tests/domain/entities/test_memo.py` | Memo エンティティのテスト |

---

## Memo エンティティ

### データ構造

```python
@dataclass(frozen=True)
class Memo:
    """メモエンティティ

    Attributes:
        id: メモの一意識別子（UUID）
        content: メモ本文（50文字程度を推奨）
        priority: 優先度（1-5、5が最高）
        tags: タグリスト（最大3タグ）
        detail: 詳細情報（edit_memoで上書き更新）
        created_at: 作成日時
        updated_at: 更新日時
    """
    id: UUID
    content: str
    priority: int  # 1-5
    tags: list[str]  # 最大3タグ
    detail: str | None
    created_at: datetime
    updated_at: datetime
```

### バリデーション

`__post_init__` で以下を検証:

1. `priority` が 1-5 の範囲内であること
2. `content` が空でないこと（空白のみも不可）
3. `tags` が最大3つまでであること

```python
def __post_init__(self) -> None:
    if not 1 <= self.priority <= 5:
        raise ValueError("Priority must be between 1 and 5")
    if not self.content.strip():
        raise ValueError("Content cannot be empty")
    if len(self.tags) > 3:
        raise ValueError("Maximum 3 tags allowed per memo")
```

### プロパティ

```python
@property
def has_detail(self) -> bool:
    """詳細情報があるかどうか"""
    return self.detail is not None and len(self.detail.strip()) > 0
```

---

## TagStats データクラス

タグの統計情報を保持する。

```python
@dataclass(frozen=True)
class TagStats:
    """タグ統計情報

    Attributes:
        tag: タグ名
        count: 使用数
        latest_updated_at: 最新更新日時
    """
    tag: str
    count: int
    latest_updated_at: datetime
```

---

## create_memo ファクトリ関数

```python
def create_memo(
    content: str,
    priority: int,
    tags: list[str] | None = None,
) -> Memo:
    """Memo エンティティを生成する

    Args:
        content: メモの内容
        priority: 優先度（1-5）
        tags: タグリスト（省略時は空リスト）

    Returns:
        Memo エンティティ

    Raises:
        ValueError: バリデーションエラーの場合
    """
    now = datetime.now(timezone.utc)
    return Memo(
        id=uuid4(),
        content=content,
        priority=priority,
        tags=tags or [],
        detail=None,
        created_at=now,
        updated_at=now,
    )
```

---

## MemoRepository Protocol

```python
class MemoRepository(Protocol):
    """メモリポジトリ"""

    async def save(self, memo: Memo) -> None:
        """メモを保存（upsert）

        同じ ID のメモが存在する場合は更新する。

        Args:
            memo: 保存するメモ
        """
        ...

    async def find_by_id(self, memo_id: UUID) -> Memo | None:
        """ID でメモを検索

        Args:
            memo_id: メモの ID

        Returns:
            見つかったメモ、または None
        """
        ...

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
        ...

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
        ...

    async def find_recent(self, limit: int = 5) -> list[Memo]:
        """直近のメモを取得

        更新日時降順でソート。

        Args:
            limit: 取得する最大件数

        Returns:
            メモのリスト
        """
        ...

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
        ...

    async def get_all_tags_with_stats(self) -> list[TagStats]:
        """全タグの統計情報を取得

        使用数降順でソート。

        Returns:
            TagStats のリスト
        """
        ...

    async def delete(self, memo_id: UUID) -> bool:
        """メモを削除

        Args:
            memo_id: 削除するメモの ID

        Returns:
            削除成功の場合 True、メモが存在しない場合 False
        """
        ...

    async def count(self, tag: str | None = None) -> int:
        """メモの件数を取得

        Args:
            tag: 指定した場合、そのタグを持つメモの件数を返す

        Returns:
            メモの件数
        """
        ...
```

---

## テスト項目

### TestMemo

- 有効なパラメータでの作成
- detail付きでの作成
- has_detail プロパティ（None、空文字、空白のみ、値あり）
- 優先度範囲外でのエラー（0, 6）
- 空コンテンツでのエラー
- タグ4つ以上でのエラー
- タグ3つでの正常作成
- 空タグリストでの正常作成
- 不変性（frozen）
- 等価性

### TestCreateMemo

- 必須パラメータのみでの作成
- タグ付きでの作成
- タイムスタンプの設定
- ユニークID生成
- バリデーションエラー

### TestTagStats

- 正常な作成
- 不変性
- 等価性
