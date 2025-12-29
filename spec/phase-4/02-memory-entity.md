# 02: Memory エンティティ定義

## 目的

長期記憶と短期記憶を表現するドメインエンティティを定義する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memory.py` | Memory, MemoryScope, MemoryType エンティティ（新規） |
| `src/myao2/domain/entities/__init__.py` | Memory エクスポート追加（修正） |
| `tests/domain/entities/test_memory.py` | Memory テスト（新規） |

---

## インターフェース設計

### MemoryScope 列挙型

```python
from enum import Enum

class MemoryScope(Enum):
    """記憶のスコープ"""

    WORKSPACE = "workspace"
    CHANNEL = "channel"
    THREAD = "thread"
```

### MemoryType 列挙型

```python
class MemoryType(Enum):
    """記憶の種類"""

    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
```

### 有効な組み合わせ

| スコープ | 長期記憶 | 短期記憶 |
|---------|:------:|:------:|
| WORKSPACE | ○ | ○ |
| CHANNEL | ○ | ○ |
| THREAD | - | ○ |

```python
# 有効な組み合わせの定義
VALID_MEMORY_COMBINATIONS: set[tuple[MemoryScope, MemoryType]] = {
    (MemoryScope.WORKSPACE, MemoryType.LONG_TERM),
    (MemoryScope.WORKSPACE, MemoryType.SHORT_TERM),
    (MemoryScope.CHANNEL, MemoryType.LONG_TERM),
    (MemoryScope.CHANNEL, MemoryType.SHORT_TERM),
    (MemoryScope.THREAD, MemoryType.SHORT_TERM),
}


def is_valid_memory_combination(scope: MemoryScope, memory_type: MemoryType) -> bool:
    """記憶のスコープとタイプの組み合わせが有効かを判定"""
    return (scope, memory_type) in VALID_MEMORY_COMBINATIONS
```

### Memory エンティティ

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Memory:
    """記憶エンティティ

    記憶は (scope, scope_id, memory_type) の組み合わせで一意に識別される。
    例えば、チャンネル "C123" の長期記憶は1つだけ存在する。

    Attributes:
        scope: 記憶のスコープ（WORKSPACE / CHANNEL / THREAD）
        scope_id: スコープ固有の ID
            - WORKSPACE: workspace_id（通常は固定値 "default"）
            - CHANNEL: channel_id
            - THREAD: "{channel_id}:{thread_ts}"
        memory_type: 記憶の種類（LONG_TERM / SHORT_TERM）
        content: 記憶の内容（LLM 生成テキスト）
        created_at: 作成日時
        updated_at: 更新日時
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts
    """

    scope: MemoryScope
    scope_id: str
    memory_type: MemoryType
    content: str
    created_at: datetime
    updated_at: datetime
    source_message_count: int
    source_latest_message_ts: str | None = None

    def __post_init__(self) -> None:
        """バリデーション"""
        if not is_valid_memory_combination(self.scope, self.memory_type):
            raise ValueError(
                f"Invalid memory combination: scope={self.scope}, "
                f"memory_type={self.memory_type}"
            )
```

### ファクトリメソッド

```python
def create_memory(
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    content: str,
    source_message_count: int,
    source_latest_message_ts: str | None = None,
) -> Memory:
    """Memory エンティティを生成する

    Args:
        scope: 記憶のスコープ
        scope_id: スコープ固有の ID
        memory_type: 記憶の種類
        content: 記憶の内容
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts

    Returns:
        Memory エンティティ

    Raises:
        ValueError: 無効なスコープとタイプの組み合わせの場合
    """
    now = datetime.now()
    return Memory(
        scope=scope,
        scope_id=scope_id,
        memory_type=memory_type,
        content=content,
        created_at=now,
        updated_at=now,
        source_message_count=source_message_count,
        source_latest_message_ts=source_latest_message_ts,
    )
```

---

## scope_id の命名規則

| スコープ | scope_id 形式 | 例 |
|---------|--------------|-----|
| WORKSPACE | 固定値 | `"default"` |
| CHANNEL | channel_id | `"C1234567890"` |
| THREAD | `{channel_id}:{thread_ts}` | `"C1234567890:1234567890.123456"` |

### ヘルパー関数

```python
def make_thread_scope_id(channel_id: str, thread_ts: str) -> str:
    """スレッドの scope_id を生成する"""
    return f"{channel_id}:{thread_ts}"


def parse_thread_scope_id(scope_id: str) -> tuple[str, str]:
    """スレッドの scope_id をパースする

    Returns:
        (channel_id, thread_ts) のタプル

    Raises:
        ValueError: 無効な形式の場合
    """
    parts = scope_id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid thread scope_id format: {scope_id}")
    return parts[0], parts[1]
```

---

## 設計上の考慮事項

### イミュータブル

- `frozen=True` により不変オブジェクト
- 更新時は新しいインスタンスを生成

### バリデーション

- `__post_init__` で有効な組み合わせを検証
- 無効な組み合わせは `ValueError` を送出

### 一意性

- 記憶は `(scope, scope_id, memory_type)` の組み合わせで一意に識別
- 例: `(CHANNEL, "C123", LONG_TERM)` は1つの記憶を指す
- 別途 UUID 等の ID は不要

---

## テストケース

### MemoryScope

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 値の確認 | 各スコープの値 | WORKSPACE="workspace", CHANNEL="channel", THREAD="thread" |

### MemoryType

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 値の確認 | 各タイプの値 | LONG_TERM="long_term", SHORT_TERM="short_term" |

### is_valid_memory_combination

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| WORKSPACE + LONG_TERM | 有効な組み合わせ | True |
| WORKSPACE + SHORT_TERM | 有効な組み合わせ | True |
| CHANNEL + LONG_TERM | 有効な組み合わせ | True |
| CHANNEL + SHORT_TERM | 有効な組み合わせ | True |
| THREAD + SHORT_TERM | 有効な組み合わせ | True |
| THREAD + LONG_TERM | 無効な組み合わせ | False |

### Memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | 有効な組み合わせ | Memory が生成される |
| 無効な組み合わせ | THREAD + LONG_TERM | ValueError が発生 |
| イミュータブル | フィールド変更を試みる | 変更不可 |
| 比較 | 同じ内容の Memory | 等価と判定される |

### create_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | 必須パラメータのみ | Memory が生成される |
| 日時設定 | 生成直後 | created_at と updated_at が設定される |
| 無効な組み合わせ | THREAD + LONG_TERM | ValueError が発生 |

### make_thread_scope_id / parse_thread_scope_id

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | channel_id, thread_ts | 正しい形式の scope_id |
| 正常パース | 有効な scope_id | (channel_id, thread_ts) |
| パースエラー | 無効な形式 | ValueError |

---

## 完了基準

- [ ] MemoryScope 列挙型が定義されている
- [ ] MemoryType 列挙型が定義されている
- [ ] is_valid_memory_combination 関数が定義されている
- [ ] Memory エンティティがイミュータブルに定義されている
- [ ] Memory の `__post_init__` でバリデーションが行われる
- [ ] create_memory ファクトリ関数が定義されている
- [ ] make_thread_scope_id / parse_thread_scope_id が定義されている
- [ ] `__init__.py` でエクスポートされている
- [ ] 全テストケースが通過する
