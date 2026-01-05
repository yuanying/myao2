# 01d: ワークスペース短期記憶廃止

## 目的

ワークスペースの短期記憶を廃止し、チャンネルの短期記憶履歴で代替する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memory.py` | 有効な組み合わせから削除（修正） |
| `src/myao2/domain/entities/context.py` | workspace_short_term_memory 削除（修正） |
| `src/myao2/application/use_cases/generate_memory.py` | WS 短期記憶生成削除（修正） |
| `src/myao2/application/use_cases/helpers.py` | WS 短期記憶取得削除（修正） |
| `tests/domain/entities/test_memory.py` | テスト修正 |
| `tests/domain/entities/test_context.py` | テスト修正 |

---

## 変更内容

### 1. 有効な組み合わせから削除

`src/myao2/domain/entities/memory.py`:

```python
# 変更前
VALID_MEMORY_COMBINATIONS: set[tuple[MemoryScope, MemoryType]] = {
    (MemoryScope.WORKSPACE, MemoryType.LONG_TERM),
    (MemoryScope.WORKSPACE, MemoryType.SHORT_TERM),  # 削除
    (MemoryScope.CHANNEL, MemoryType.LONG_TERM),
    (MemoryScope.CHANNEL, MemoryType.SHORT_TERM),
    (MemoryScope.THREAD, MemoryType.SHORT_TERM),
}

# 変更後
VALID_MEMORY_COMBINATIONS: set[tuple[MemoryScope, MemoryType]] = {
    (MemoryScope.WORKSPACE, MemoryType.LONG_TERM),
    (MemoryScope.CHANNEL, MemoryType.LONG_TERM),
    (MemoryScope.CHANNEL, MemoryType.SHORT_TERM),
    (MemoryScope.THREAD, MemoryType.SHORT_TERM),
}
```

### 2. Context から削除

`src/myao2/domain/entities/context.py`:

```python
# 変更前
@dataclass(frozen=True)
class Context:
    persona: PersonaConfig
    conversation_history: ChannelMessages
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None  # 削除
    channel_memories: dict[str, ChannelMemory] = field(default_factory=dict)
    thread_memories: dict[str, str] = field(default_factory=dict)
    target_thread_ts: str | None = None

# 変更後
@dataclass(frozen=True)
class Context:
    persona: PersonaConfig
    conversation_history: ChannelMessages
    workspace_long_term_memory: str | None = None
    channel_memories: dict[str, ChannelMemory] = field(default_factory=dict)
    thread_memories: dict[str, str] = field(default_factory=dict)
    target_thread_ts: str | None = None
```

### 3. 記憶生成ユースケースから削除

`src/myao2/application/use_cases/generate_memory.py`:

```python
# generate_workspace_memory メソッドから短期記憶生成を削除

# 変更前
async def generate_workspace_memory(self, ...) -> None:
    # 短期記憶生成
    short_term = await self._summarizer.summarize(
        context, MemoryScope.WORKSPACE, MemoryType.SHORT_TERM
    )
    await self._memory_repository.save(short_term)

    # 長期記憶生成
    long_term = await self._summarizer.summarize(
        context, MemoryScope.WORKSPACE, MemoryType.LONG_TERM, existing
    )
    await self._memory_repository.save(long_term)

# 変更後
async def generate_workspace_memory(self, ...) -> None:
    # 長期記憶生成のみ
    long_term = await self._summarizer.summarize(
        context, MemoryScope.WORKSPACE, MemoryType.LONG_TERM, existing
    )
    await self._memory_repository.save(long_term)
```

### 4. Context 構築から削除

`src/myao2/application/use_cases/helpers.py`:

```python
# build_context_with_memory から WS 短期記憶の取得を削除

# 変更前
workspace_short_term = await memory_repository.find_by_scope_and_type(
    MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.SHORT_TERM
)

context = Context(
    ...
    workspace_short_term_memory=workspace_short_term.content if workspace_short_term else None,
    ...
)

# 変更後
context = Context(
    ...
    # workspace_short_term_memory は削除
    ...
)
```

---

## 既存データの扱い

### 方針

既存のワークスペース短期記憶データは **削除せず残す**。

理由:
1. ロールバックが必要になった場合に備える
2. データ削除は破壊的な操作であり、慎重に行うべき
3. 参照しなければ実害はない

### 将来的なクリーンアップ

必要に応じて、管理スクリプトで以下のコマンドを実行：

```sql
DELETE FROM memories
WHERE scope = 'workspace' AND memory_type = 'short_term';
```

---

## 影響範囲

### 影響を受けるコンポーネント

| コンポーネント | 影響 |
|--------------|------|
| Memory エンティティ | (WORKSPACE, SHORT_TERM) が無効になる |
| Context エンティティ | workspace_short_term_memory フィールド削除 |
| GenerateMemoryUseCase | WS 短期記憶生成を削除 |
| build_context_with_memory | WS 短期記憶取得を削除 |
| テンプレート | WS 短期記憶表示を削除（01g で対応） |

### 影響を受けないコンポーネント

| コンポーネント | 理由 |
|--------------|------|
| MemoryRepository | 汎用的な実装のため変更不要 |
| MemorySummarizer | 呼び出し側が変更されるため変更不要 |
| BackgroundMemoryGenerator | GenerateMemoryUseCase の変更で自動的に反映 |

---

## テストケース

### is_valid_memory_combination

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| WORKSPACE + LONG_TERM | 有効な組み合わせ | True |
| WORKSPACE + SHORT_TERM | 無効な組み合わせ | False（変更） |
| CHANNEL + SHORT_TERM | 有効な組み合わせ | True |

### Memory エンティティ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| WORKSPACE + SHORT_TERM | 無効な組み合わせで生成 | ValueError（変更） |

### Context エンティティ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| フィールド確認 | workspace_short_term_memory | 存在しない |

---

## 完了基準

- [ ] VALID_MEMORY_COMBINATIONS から (WORKSPACE, SHORT_TERM) が削除されている
- [ ] Context から workspace_short_term_memory が削除されている
- [ ] GenerateMemoryUseCase から WS 短期記憶生成が削除されている
- [ ] build_context_with_memory から WS 短期記憶取得が削除されている
- [ ] 既存データは残したまま参照しない状態になっている
- [ ] 全テストケースが通過する
