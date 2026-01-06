# 01e: Context の履歴対応

## 目的

Context と ChannelMemory に短期記憶の履歴フィールドを追加する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/channel_messages.py` | ChannelMemory に履歴フィールド追加（修正） |
| `src/myao2/application/use_cases/helpers.py` | 履歴取得ロジック追加（修正） |
| `tests/domain/entities/test_context.py` | 履歴フィールドテスト追加（修正） |

---

## インターフェース設計

### ChannelMemory の変更

`src/myao2/domain/entities/channel_messages.py`:

```python
@dataclass(frozen=True)
class ChannelMemory:
    """チャンネルの記憶

    Attributes:
        channel_id: チャンネル ID
        channel_name: チャンネル名
        long_term_memory: 長期記憶（全期間の時系列要約）
        short_term_memory: 短期記憶（最新のもの、後方互換のため維持）
        short_term_memory_history: 短期記憶履歴（古い順）
    """

    channel_id: str
    channel_name: str
    long_term_memory: str | None = None
    short_term_memory: str | None = None
    short_term_memory_history: list[str] = field(default_factory=list)  # 追加
```

### short_term_memory と short_term_memory_history の関係

- `short_term_memory`: 最新の短期記憶（後方互換のため維持）
- `short_term_memory_history`: 直近 N 件の短期記憶履歴（古い順）

履歴がある場合、`short_term_memory` は `short_term_memory_history[-1]`（最後の要素）と同じ内容になる。

```python
# 例: 5件の履歴がある場合
channel_memory = ChannelMemory(
    channel_id="C123",
    channel_name="general",
    long_term_memory="...",
    short_term_memory="最新の短期記憶",  # = history[-1]
    short_term_memory_history=[
        "1番目の短期記憶",
        "2番目の短期記憶",
        "3番目の短期記憶",
        "4番目の短期記憶",
        "最新の短期記憶",
    ],
)
```

---

## build_context_with_memory の変更

`src/myao2/application/use_cases/helpers.py`:

```python
async def build_context_with_memory(
    persona: PersonaConfig,
    conversation_history: ChannelMessages,
    memory_repository: MemoryRepository,
    memory_config: MemoryConfig,
    channels: list[Channel],
    target_thread_ts: str | None = None,
) -> Context:
    """記憶を含む Context を構築する"""

    # ワークスペース長期記憶を取得
    workspace_long_term = await memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
    )

    # 各チャンネルの記憶を取得
    channel_memories: dict[str, ChannelMemory] = {}
    for channel in channels:
        # 長期記憶
        long_term = await memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
        )

        # 短期記憶履歴（新しい順で取得）
        history_limit = (
            memory_config.short_term_history.max_history_count
            if memory_config.short_term_history and memory_config.short_term_history.enabled
            else 1
        )
        history = await memory_repository.find_history_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.SHORT_TERM, limit=history_limit
        )

        # 古い順に並べ替え（version 昇順）
        history_sorted = sorted(history, key=lambda m: m.version)
        history_contents = [m.content for m in history_sorted]

        # 最新の短期記憶（後方互換）
        latest_short_term = history_contents[-1] if history_contents else None

        channel_memories[channel.id] = ChannelMemory(
            channel_id=channel.id,
            channel_name=channel.name,
            long_term_memory=long_term.content if long_term else None,
            short_term_memory=latest_short_term,
            short_term_memory_history=history_contents,
        )

    # スレッド記憶を取得（変更なし）
    thread_memories: dict[str, str] = {}
    # ...

    return Context(
        persona=persona,
        conversation_history=conversation_history,
        workspace_long_term_memory=workspace_long_term.content if workspace_long_term else None,
        channel_memories=channel_memories,
        thread_memories=thread_memories,
        target_thread_ts=target_thread_ts,
    )
```

---

## 履歴の取得ロジック

### 履歴数の決定

```python
# 設定から履歴数を取得
if memory_config.short_term_history and memory_config.short_term_history.enabled:
    history_limit = memory_config.short_term_history.max_history_count  # デフォルト: 5
else:
    history_limit = 1  # 履歴機能が無効の場合は最新のみ
```

### 並び替え

リポジトリは `version` 降順（新しい順）で返すため、表示用に昇順（古い順）に並べ替える：

```python
# リポジトリから取得（version 降順）
history = await memory_repository.find_history_by_scope_and_type(...)
# [v5, v4, v3, v2, v1]

# 古い順に並べ替え
history_sorted = sorted(history, key=lambda m: m.version)
# [v1, v2, v3, v4, v5]

# 内容だけ抽出
history_contents = [m.content for m in history_sorted]
```

---

## テストケース

### ChannelMemory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト値 | history 未指定 | 空リスト |
| 履歴あり | 5件の履歴 | 5件のリスト |
| 後方互換 | short_term_memory のみ指定 | 従来通り動作 |

### build_context_with_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | チャンネルに短期記憶なし | history は空リスト |
| 履歴 1 件 | 1 件の短期記憶 | history に 1 件、short_term_memory も設定 |
| 履歴 5 件 | 5 件の短期記憶 | history に 5 件（古い順）、short_term_memory は最新 |
| 履歴 10 件、limit 5 | 10 件中 5 件取得 | history に 5 件（最新 5 件を古い順で） |
| 機能無効 | enabled=false | history に 1 件のみ |

### 並び替え

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 順序確認 | v3, v1, v5, v2, v4 の順で保存 | [v1, v2, v3, v4, v5] の順で返る |

---

## 完了基準

- [ ] ChannelMemory に short_term_memory_history フィールドが追加されている
- [ ] build_context_with_memory で履歴を取得できる
- [ ] 履歴は古い順（version 昇順）で格納される
- [ ] short_term_memory は最新の短期記憶（後方互換）
- [ ] 履歴機能が無効の場合は最新の 1 件のみ取得
- [ ] 全テストケースが通過する
