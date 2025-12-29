# 04: Context への記憶フィールド追加

## 目的

Context エンティティに記憶フィールドを追加し、LLM への記憶提供を可能にする。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/context.py` | 記憶フィールド追加（修正） |
| `tests/domain/entities/test_context.py` | 記憶フィールドテスト追加（修正） |

---

## 依存関係

- タスク 02（Memory エンティティ）に依存（概念のみ、直接参照なし）

---

## インターフェース設計

### Context（変更後）

```python
from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history, other channel messages, and memories for LLM.
    This is a pure data class - system prompt construction is the
    responsibility of the module that receives the context.
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    other_channel_messages: dict[str, list[Message]] = field(default_factory=dict)

    # 記憶フィールド（Phase 4 追加）
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None
    channel_long_term_memory: str | None = None
    channel_short_term_memory: str | None = None
    thread_memory: str | None = None
```

---

## フィールド説明

| フィールド | 型 | 説明 |
|-----------|-----|------|
| workspace_long_term_memory | str \| None | ワークスペースの長期記憶（全期間の時系列要約） |
| workspace_short_term_memory | str \| None | ワークスペースの短期記憶（直近の要約） |
| channel_long_term_memory | str \| None | チャンネルの長期記憶（全期間の時系列要約） |
| channel_short_term_memory | str \| None | チャンネルの短期記憶（直近の要約） |
| thread_memory | str \| None | スレッドの記憶（スレッドの要約） |

---

## 使用パターン

### 記憶なしの Context 生成

```python
context = Context(
    persona=persona_config,
    conversation_history=messages,
)
```

### 記憶ありの Context 生成

```python
context = Context(
    persona=persona_config,
    conversation_history=messages,
    workspace_long_term_memory="ワークスペースの歴史...",
    workspace_short_term_memory="直近のワークスペースでの出来事...",
    channel_long_term_memory="チャンネルの歴史...",
    channel_short_term_memory="直近のチャンネルでの出来事...",
    thread_memory="スレッドの要約...",
)
```

### 記憶の有無を確認

```python
def has_any_memory(context: Context) -> bool:
    """Context に何らかの記憶が含まれているかを確認"""
    return any([
        context.workspace_long_term_memory,
        context.workspace_short_term_memory,
        context.channel_long_term_memory,
        context.channel_short_term_memory,
        context.thread_memory,
    ])
```

---

## 設計上の考慮事項

### イミュータブル

- `frozen=True` を維持
- 記憶の追加は新しい Context インスタンスを生成

### デフォルト値

- 全記憶フィールドは `None` がデフォルト
- 記憶システムが無効な場合や、記憶が未生成の場合に対応

### 記憶の粒度

- 記憶は文字列（LLM が生成したテキスト）
- 構造化データではなく、人間が読めるテキスト形式
- LLM が理解しやすい形式を想定

---

## テストケース

### Context 生成

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 記憶なし | 記憶フィールド未指定 | 全記憶フィールドが None |
| 記憶あり | 全記憶フィールド指定 | 全記憶フィールドが設定される |
| 部分記憶 | 一部の記憶フィールドのみ | 指定分のみ設定、残りは None |

### イミュータブル

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| フィールド変更 | 記憶フィールドの変更を試みる | 変更不可（FrozenInstanceError） |

### 後方互換性

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 既存コード | persona と conversation_history のみ指定 | エラーなく動作 |

---

## 完了基準

- [ ] Context に 5 つの記憶フィールドが追加されている
- [ ] 全記憶フィールドのデフォルト値が None である
- [ ] イミュータブル性が維持されている
- [ ] 既存のテストが引き続き通過する
- [ ] 新しいテストケースが通過する
