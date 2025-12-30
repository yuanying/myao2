# 04: Context への記憶フィールド追加

> **注意**: この設計書は [04a-channel-messages-and-context.md](./04a-channel-messages-and-context.md) によって置き換えられました。
> 新しい設計では Context の構造が大幅に変更されています。

## 変更履歴

| 日付 | 変更内容 |
|------|---------|
| 初版 | Context に 5 つの記憶フィールドを追加 |
| 改訂 | 04a で ChannelMessages 導入に伴い構造を変更 |

---

## 旧設計（参考）

### Context（旧）

```python
@dataclass(frozen=True)
class Context:
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

## 新設計（04a）

### Context（新）

```python
@dataclass(frozen=True)
class Context:
    persona: PersonaConfig
    conversation_history: ChannelMessages  # 型変更
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None
    channel_memories: dict[str, ChannelMemory] = field(default_factory=dict)  # 新規
    thread_memories: dict[str, str] = field(default_factory=dict)  # 新規
    target_thread_ts: str | None = None  # 新規
```

---

## 変更点のサマリー

### 削除されたフィールド

| フィールド | 理由 |
|-----------|------|
| other_channel_messages | channel_memories に統合 |
| channel_long_term_memory | channel_memories に移動 |
| channel_short_term_memory | channel_memories に移動 |
| thread_memory | thread_memories に変更（単一→複数） |

### 追加されたフィールド

| フィールド | 説明 |
|-----------|------|
| channel_memories | 複数チャンネルの記憶を保持 |
| thread_memories | 複数スレッドの要約を保持 |
| target_thread_ts | 返答対象を明示 |

### 型変更

| フィールド | 変更前 | 変更後 |
|-----------|--------|--------|
| conversation_history | list[Message] | ChannelMessages |

---

## 完了基準

- [x] Context に 5 つの記憶フィールドが追加されている
- [x] 全記憶フィールドのデフォルト値が None である
- [x] イミュータブル性が維持されている
- [x] 既存のテストが引き続き通過する
- [x] 新しいテストケースが通過する

> **注意**: 上記は旧設計の完了基準です。新設計の完了基準は 04a を参照してください。
