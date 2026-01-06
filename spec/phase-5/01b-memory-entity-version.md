# 01b: Memory エンティティのバージョン対応

## 目的

Memory エンティティに `version` フィールドを追加し、短期記憶の履歴管理を可能にする。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memory.py` | version フィールド追加（修正） |
| `src/myao2/infrastructure/persistence/models.py` | version カラム追加（修正） |
| `tests/domain/entities/test_memory.py` | version テスト追加（修正） |

---

## インターフェース設計

### Memory エンティティの変更

```python
@dataclass(frozen=True)
class Memory:
    """記憶エンティティ

    記憶は (scope, scope_id, memory_type, version) の組み合わせで一意に識別される。
    version は短期記憶の履歴管理に使用される。
    長期記憶は常に version=1 で上書きされる。

    Attributes:
        scope: 記憶のスコープ（WORKSPACE / CHANNEL / THREAD）
        scope_id: スコープ固有の ID
        memory_type: 記憶の種類（LONG_TERM / SHORT_TERM）
        content: 記憶の内容（LLM 生成テキスト）
        created_at: 作成日時
        updated_at: 更新日時
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts
        version: バージョン番号（1から開始）
    """

    scope: MemoryScope
    scope_id: str
    memory_type: MemoryType
    content: str
    created_at: datetime
    updated_at: datetime
    source_message_count: int
    source_latest_message_ts: str | None = None
    version: int = 1  # 追加
```

### create_memory ファクトリメソッドの変更

```python
def create_memory(
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    content: str,
    source_message_count: int,
    source_latest_message_ts: str | None = None,
    version: int = 1,  # 追加
) -> Memory:
    """Memory エンティティを生成する

    Args:
        scope: 記憶のスコープ
        scope_id: スコープ固有の ID
        memory_type: 記憶の種類
        content: 記憶の内容
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts
        version: バージョン番号（デフォルト: 1）

    Returns:
        Memory エンティティ
    """
    now = datetime.now(timezone.utc)
    return Memory(
        scope=scope,
        scope_id=scope_id,
        memory_type=memory_type,
        content=content,
        created_at=now,
        updated_at=now,
        source_message_count=source_message_count,
        source_latest_message_ts=source_latest_message_ts,
        version=version,
    )
```

---

## MemoryModel の変更

### models.py

```python
class MemoryModel(SQLModel, table=True):
    """記憶モデル"""

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
    version: int = Field(default=1)  # 追加

    # 一意制約の変更: version を含める
    __table_args__ = (
        UniqueConstraint(
            "scope", "scope_id", "memory_type", "version",
            name="uq_scope_type_version"
        ),
    )
```

---

## マイグレーション

### 既存データの扱い

既存の短期記憶データは `version=1` として扱う。

SQLite の場合、以下のスキーマ変更が必要：

```sql
-- 1. version カラムを追加（デフォルト値 1）
ALTER TABLE memories ADD COLUMN version INTEGER DEFAULT 1;

-- 2. 既存データを version=1 に更新
UPDATE memories SET version = 1 WHERE version IS NULL;

-- 3. 旧一意制約を削除（SQLite では直接削除できないため、テーブル再作成が必要）
-- 4. 新一意制約を追加
```

### 自動マイグレーション

SQLModel の `create_all` を使用すると、新しいカラムは追加されるが、一意制約の変更は手動で行う必要がある。

実装では、起動時に以下のチェックを行う：

1. `version` カラムが存在しない場合は追加
2. 既存データの `version` が NULL の場合は 1 に更新

---

## version の使い方

| スコープ | memory_type | version の挙動 |
|---------|-------------|---------------|
| WORKSPACE | LONG_TERM | 常に 1（上書き） |
| CHANNEL | LONG_TERM | 常に 1（上書き） |
| CHANNEL | SHORT_TERM | インクリメント（履歴化） |
| THREAD | SHORT_TERM | 常に 1（上書き） |

### 長期記憶

長期記憶は履歴化せず、常に `version=1` で上書きする。

### チャンネル短期記憶

チャンネルの短期記憶は履歴化する。新しい短期記憶を保存する際は、現在の最大 version + 1 で保存する。

### スレッド短期記憶

スレッドの短期記憶は履歴化せず、常に `version=1` で上書きする。

---

## テストケース

### Memory エンティティ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト version | version 未指定で生成 | version=1 |
| カスタム version | version=5 で生成 | version=5 |
| 不変性 | version の変更を試みる | 変更不可 |

### create_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト version | version 未指定 | version=1 の Memory |
| カスタム version | version=3 を指定 | version=3 の Memory |

### MemoryModel

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 一意性 | 同じ (scope, scope_id, memory_type, version) | 重複エラー |
| 異なる version | version のみ異なる | 両方保存可能 |

---

## 完了基準

- [ ] Memory エンティティに version フィールドが追加されている
- [ ] create_memory で version を指定できる
- [ ] MemoryModel に version カラムが追加されている
- [ ] 一意制約が (scope, scope_id, memory_type, version) に変更されている
- [ ] 全テストケースが通過する
