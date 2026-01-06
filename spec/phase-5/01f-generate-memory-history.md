# 01f: 記憶生成ユースケースの履歴対応

## 目的

GenerateMemoryUseCase を履歴対応に修正し、短期記憶の更新トリガーと長期記憶への統合を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/use_cases/generate_memory.py` | 履歴生成・長期記憶統合（修正） |
| `tests/application/use_cases/test_generate_memory.py` | テスト追加（修正） |

---

## 更新トリガー

### 条件（OR条件）

以下の **いずれか** を満たした場合に、新しい短期記憶バージョンを作成：

| トリガー | 条件 | 設定項目 |
|---------|------|---------|
| 会話終了 | 最新メッセージから `conversation_idle_seconds` 秒経過 | デフォルト: 7200（2時間） |
| コンテキスト圧迫 | 前回更新以降のメッセージ数が `message_threshold` を超過 | デフォルト: 50 |

### 判定ロジック

```python
def _should_update_short_term_memory(
    self,
    latest_message_ts: str | None,
    existing_memory: Memory | None,
    new_message_count: int,
    config: ShortTermHistoryConfig,
) -> bool:
    """短期記憶を更新すべきか判定

    Args:
        latest_message_ts: 最新メッセージのタイムスタンプ
        existing_memory: 現在の最新短期記憶
        new_message_count: 前回更新以降の新規メッセージ数
        config: 短期記憶履歴設定

    Returns:
        更新すべき場合 True
    """
    if not config.enabled:
        return True  # 履歴機能が無効の場合は常に上書き

    # 既存の短期記憶がない場合は更新
    if existing_memory is None:
        return True

    # 条件1: 会話終了（idle 時間経過）
    if latest_message_ts:
        latest_dt = datetime.fromtimestamp(float(latest_message_ts), tz=timezone.utc)
        idle_seconds = (datetime.now(timezone.utc) - latest_dt).total_seconds()
        if idle_seconds >= config.conversation_idle_seconds:
            return True

    # 条件2: メッセージ数閾値超過
    if new_message_count >= config.message_threshold:
        return True

    return False
```

---

## 短期記憶の更新フロー

### generate_channel_memories の変更

```python
async def generate_channel_memories(
    self,
    channels: list[Channel],
    config: MemoryConfig,
) -> None:
    """チャンネルの記憶を生成する"""
    history_config = config.short_term_history or ShortTermHistoryConfig()

    for channel in channels:
        # 1. メッセージを取得
        messages = await self._message_repository.find_by_channel(
            channel.id,
            since=timedelta(hours=config.short_term_window_hours),
        )

        if not messages:
            continue

        # 2. 現在の最新短期記憶を取得
        existing_short_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.SHORT_TERM
        )

        # 3. 新規メッセージ数を計算
        new_message_count = self._count_new_messages(
            messages, existing_short_term
        )

        # 4. 更新すべきか判定
        latest_message_ts = messages[-1].ts if messages else None
        should_update = self._should_update_short_term_memory(
            latest_message_ts,
            existing_short_term,
            new_message_count,
            history_config,
        )

        if not should_update:
            continue

        # 5. 短期記憶を生成
        context = self._build_context_for_summarization(channel, messages)
        short_term_content = await self._summarizer.summarize(
            context, MemoryScope.CHANNEL, MemoryType.SHORT_TERM
        )

        # 6. 新しいバージョンとして保存
        new_short_term = create_memory(
            scope=MemoryScope.CHANNEL,
            scope_id=channel.id,
            memory_type=MemoryType.SHORT_TERM,
            content=short_term_content,
            source_message_count=len(messages),
            source_latest_message_ts=latest_message_ts,
        )

        if history_config.enabled:
            # 履歴として保存
            saved_memory = await self._memory_repository.save_as_new_version(new_short_term)
        else:
            # 従来通り上書き
            await self._memory_repository.save(new_short_term)
            saved_memory = new_short_term

        # 7. 長期記憶を更新（短期記憶保存直後）
        await self._update_channel_long_term_memory(
            channel, saved_memory, config
        )

        # 8. ワークスペース長期記憶を更新
        await self._update_workspace_long_term_memory(config)
```

---

## 長期記憶への統合

### チャンネル長期記憶の更新

```python
async def _update_channel_long_term_memory(
    self,
    channel: Channel,
    new_short_term: Memory,
    config: MemoryConfig,
) -> None:
    """チャンネル長期記憶を更新する

    新しい短期記憶を既存の長期記憶に統合する。
    """
    # 既存の長期記憶を取得
    existing_long_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
    )

    # Context を構築（既存長期記憶 + 新短期記憶）
    context = self._build_context_for_long_term_update(
        channel,
        existing_long_term,
        new_short_term,
    )

    # 長期記憶を生成
    long_term_content = await self._summarizer.summarize(
        context,
        MemoryScope.CHANNEL,
        MemoryType.LONG_TERM,
        existing_memory=existing_long_term.content if existing_long_term else None,
    )

    # 保存（常に上書き）
    long_term = create_memory(
        scope=MemoryScope.CHANNEL,
        scope_id=channel.id,
        memory_type=MemoryType.LONG_TERM,
        content=long_term_content,
        source_message_count=new_short_term.source_message_count,
        source_latest_message_ts=new_short_term.source_latest_message_ts,
    )
    await self._memory_repository.save(long_term)
```

### ワークスペース長期記憶の更新

```python
async def _update_workspace_long_term_memory(
    self,
    config: MemoryConfig,
) -> None:
    """ワークスペース長期記憶を更新する

    全チャンネルの長期記憶を統合する。
    """
    # 既存のワークスペース長期記憶を取得
    existing_ws_long_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
    )

    # 全チャンネルの長期記憶を取得
    channels = await self._channel_repository.find_active_channels()
    channel_long_terms = []
    for channel in channels:
        long_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel.id, MemoryType.LONG_TERM
        )
        if long_term:
            channel_long_terms.append((channel, long_term))

    # Context を構築
    context = self._build_context_for_workspace_long_term_update(
        existing_ws_long_term,
        channel_long_terms,
    )

    # ワークスペース長期記憶を生成
    ws_long_term_content = await self._summarizer.summarize(
        context,
        MemoryScope.WORKSPACE,
        MemoryType.LONG_TERM,
        existing_memory=existing_ws_long_term.content if existing_ws_long_term else None,
    )

    # 保存（常に上書き）
    ws_long_term = create_memory(
        scope=MemoryScope.WORKSPACE,
        scope_id=WORKSPACE_SCOPE_ID,
        memory_type=MemoryType.LONG_TERM,
        content=ws_long_term_content,
        source_message_count=sum(lt.source_message_count for _, lt in channel_long_terms),
        source_latest_message_ts=max(
            (lt.source_latest_message_ts for _, lt in channel_long_terms if lt.source_latest_message_ts),
            default=None,
        ),
    )
    await self._memory_repository.save(ws_long_term)
```

---

## 処理フロー図

```
generate_channel_memories() 開始
      │
      ↓
各チャンネルについてループ
      │
      ├─→ メッセージ取得
      │
      ├─→ 現在の短期記憶取得
      │
      ├─→ 更新すべきか判定
      │    │
      │    ├─ No → 次のチャンネルへ
      │    │
      │    └─ Yes ↓
      │
      ├─→ 短期記憶を生成（LLM）
      │
      ├─→ 新バージョンとして保存
      │
      ├─→ チャンネル長期記憶を更新（LLM）
      │
      └─→ ワークスペース長期記憶を更新（LLM）

ループ終了
```

---

## テストケース

### _should_update_short_term_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴機能無効 | enabled=false | True（常に更新） |
| 既存記憶なし | existing_memory=None | True |
| idle 時間経過 | 2時間以上経過 | True |
| メッセージ数超過 | 50件以上 | True |
| 両条件未満 | 1時間経過、30件 | False |
| idle + メッセージ | 2時間経過 AND 60件 | True |

### generate_channel_memories

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 更新条件満たさず | idle 未到達、メッセージ少 | 短期記憶更新されない |
| idle トリガー | 2時間以上経過 | 短期記憶が新バージョンで保存 |
| メッセージトリガー | 50件以上 | 短期記憶が新バージョンで保存 |
| 長期記憶統合 | 短期記憶保存後 | 長期記憶が更新される |
| WS長期記憶更新 | チャンネル長期記憶更新後 | WS長期記憶が更新される |

### 履歴機能無効時

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 上書き保存 | enabled=false | save() で上書き（save_as_new_version ではない） |

---

## 完了基準

- [ ] _should_update_short_term_memory が OR 条件で判定している
- [ ] 短期記憶が save_as_new_version で履歴として保存される
- [ ] 短期記憶保存直後にチャンネル長期記憶が更新される
- [ ] チャンネル長期記憶更新後にワークスペース長期記憶が更新される
- [ ] 履歴機能無効時は従来通り上書き保存される
- [ ] 全テストケースが通過する
