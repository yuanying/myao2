# 10: 統合テスト・動作確認

## 目的

全コンポーネントの統合動作を確認し、Phase 4 の完了を検証する。

---

## 検証対象

| コンポーネント | 検証内容 |
|--------------|---------|
| MemoryConfig | 設定ファイルの読み込み |
| Memory エンティティ | 生成・バリデーション |
| MemoryRepository | CRUD 操作 |
| Context | 記憶フィールドの設定 |
| MemorySummarizer | 記憶の生成 |
| GenerateMemoryUseCase | 記憶生成処理 |
| BackgroundMemoryGenerator | 定期実行 |
| ResponseGenerator | 記憶の system prompt 組み込み |
| エントリポイント | 全体の起動・停止 |

---

## 自動テスト

### テスト実行

```bash
# 全テストの実行
uv run pytest

# 特定のテストのみ実行
uv run pytest tests/domain/entities/test_memory.py
uv run pytest tests/infrastructure/persistence/test_memory_repository.py
uv run pytest tests/infrastructure/llm/test_memory_summarizer.py
uv run pytest tests/application/use_cases/test_generate_memory.py
uv run pytest tests/application/services/test_background_memory.py

# カバレッジ付き
uv run pytest --cov=myao2 --cov-report=html
```

### Linter・型チェック

```bash
# Linter
uv run ruff check .
uv run ruff format .

# 型チェック
uv run ty check
```

---

## 統合テストシナリオ

### シナリオ 1: 記憶生成フロー

```python
@pytest.mark.asyncio
async def test_memory_generation_flow():
    """記憶生成フローの統合テスト"""
    # Setup
    db_manager = DatabaseManager(":memory:")
    await db_manager.initialize()

    message_repo = SQLiteMessageRepository(db_manager.get_session)
    channel_repo = SQLiteChannelRepository(db_manager.get_session)
    memory_repo = SQLiteMemoryRepository(db_manager.get_session)

    # テストデータを投入
    channel = Channel(id="C123", name="general")
    await channel_repo.save(channel)

    messages = [
        Message(
            id="msg1",
            channel=channel,
            user=User(id="U1", name="user1", is_bot=False),
            text="Hello world",
            timestamp=datetime.now() - timedelta(hours=2),
            thread_ts=None,
            mentions=[],
        ),
        # ... 追加のメッセージ
    ]
    for msg in messages:
        await message_repo.save(msg)

    # MemorySummarizer のモック
    mock_summarizer = MockMemorySummarizer()

    # UseCase 実行
    use_case = GenerateMemoryUseCase(
        memory_repository=memory_repo,
        message_repository=message_repo,
        channel_repository=channel_repo,
        memory_summarizer=mock_summarizer,
        config=MemoryConfig(database_path=":memory:"),
    )

    await use_case.execute()

    # 検証
    workspace_memory = await memory_repo.find_by_scope_and_type(
        MemoryScope.WORKSPACE,
        GenerateMemoryUseCase.WORKSPACE_SCOPE_ID,
        MemoryType.LONG_TERM,
    )
    assert workspace_memory is not None

    channel_memory = await memory_repo.find_by_scope_and_type(
        MemoryScope.CHANNEL,
        "C123",
        MemoryType.LONG_TERM,
    )
    assert channel_memory is not None
```

### シナリオ 2: 記憶を含む応答生成

```python
@pytest.mark.asyncio
async def test_response_with_memory():
    """記憶を含む応答生成の統合テスト"""
    # 記憶をリポジトリに保存
    memory = create_memory(
        scope=MemoryScope.CHANNEL,
        scope_id="C123",
        memory_type=MemoryType.LONG_TERM,
        content="このチャンネルでは主に技術的な話題について議論しています。",
        source_message_count=100,
    )
    await memory_repo.save(memory)

    # Context を構築
    context = Context(
        persona=PersonaConfig(name="Bot", system_prompt="You are a helpful bot."),
        conversation_history=[...],
        channel_long_term_memory=memory.content,
    )

    # 応答生成
    response_generator = LiteLLMResponseGenerator(
        client=mock_llm_client,
        config=LLMConfig(...),
    )

    response = await response_generator.generate(message, context)

    # 検証: system prompt に記憶が含まれていることを確認
    # (モックを使用して検証)
```

### シナリオ 3: バックグラウンド記憶生成

```python
@pytest.mark.asyncio
async def test_background_memory_generation():
    """バックグラウンド記憶生成の統合テスト"""
    config = MemoryConfig(
        database_path=":memory:",
        long_term_update_interval_seconds=1,  # テスト用に短く設定
    )

    mock_use_case = MockGenerateMemoryUseCase()
    generator = BackgroundMemoryGenerator(
        generate_memory_use_case=mock_use_case,
        config=config,
    )

    # バックグラウンドで起動
    task = asyncio.create_task(generator.start())

    # 少し待機
    await asyncio.sleep(2.5)

    # 停止
    await generator.stop()
    await task

    # 検証: execute() が複数回呼ばれたこと
    assert mock_use_case.execute_count >= 2
```

---

## 手動検証手順

### 1. 環境準備

```bash
# 依存関係のインストール
uv sync

# 設定ファイルの確認
cat config.yaml
```

config.yaml に記憶設定が含まれていることを確認：

```yaml
memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600
  short_term_window_hours: 24
```

### 2. アプリケーション起動

```bash
uv run python -m myao2
```

ログを確認：

```
INFO:myao2:Starting myao2...
INFO:myao2.application.services.background_memory:Starting background memory generator
INFO:myao2.application.services.periodic_checker:Starting periodic checker
```

### 3. メッセージ投稿

Slack でチャンネルにメッセージを投稿する。

### 4. 記憶生成の確認

`long_term_update_interval_seconds` 経過後、ログを確認：

```
INFO:myao2.application.services.background_memory:Running memory generation
INFO:myao2.application.use_cases.generate_memory:Generating workspace memory
INFO:myao2.application.use_cases.generate_memory:Generated workspace/default/long_term memory
...
INFO:myao2.application.services.background_memory:Memory generation completed
```

### 5. データベースの確認

```bash
sqlite3 ./data/memory.db "SELECT scope, scope_id, memory_type, substr(content, 1, 100) FROM memories;"
```

期待される出力：

```
workspace|default|long_term|ワークスペース全体の歴史...
workspace|default|short_term|直近のワークスペースでの出来事...
channel|C1234567890|long_term|このチャンネルの歴史...
channel|C1234567890|short_term|直近のチャンネルでの出来事...
```

### 6. 記憶を含む応答の確認

ボットにメンションして応答を確認。

応答が記憶を考慮した内容になっていることを確認：
- 過去の会話の内容を参照している
- チャンネルの傾向を理解している

### 7. シャットダウンの確認

Ctrl+C でアプリケーションを停止。

ログを確認：

```
INFO:myao2:Shutting down...
INFO:myao2.application.services.background_memory:Stopping background memory generator
INFO:myao2.application.services.periodic_checker:Stopping periodic checker
INFO:myao2.application.services.background_memory:Background memory generator stopped
INFO:myao2.application.services.periodic_checker:Periodic checker stopped
```

---

## 動作確認チェックリスト

### 設定

- [ ] config.yaml に memory セクションが記載されている
- [ ] 新しい設定項目がデフォルト値で動作する

### 記憶生成

- [ ] アプリケーション起動後、記憶生成が開始される
- [ ] ワークスペースの長期・短期記憶が生成される
- [ ] チャンネルの長期・短期記憶が生成される
- [ ] スレッドの記憶が生成される
- [ ] 記憶がデータベースに保存される

### 記憶の更新

- [ ] 新しいメッセージが追加されると記憶が更新される
- [ ] インクリメンタル更新が正しく動作する

### 応答生成

- [ ] 記憶が system prompt に含まれる
- [ ] 記憶を考慮した応答が生成される
- [ ] 記憶がない場合も正常に動作する

### エラーハンドリング

- [ ] 記憶生成エラーでもサービスが継続する
- [ ] 記憶取得エラーでも応答生成が継続する

### パフォーマンス

- [ ] 記憶生成がタイムアウトしない
- [ ] 応答生成の遅延が許容範囲内

---

## 完了基準

- [ ] 全自動テストが通過する
- [ ] Linter エラーがない
- [ ] 型チェックエラーがない
- [ ] 手動検証チェックリストが全て完了
- [ ] ドキュメント（この設計書）が更新されている
