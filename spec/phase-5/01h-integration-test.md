# 01h: 統合テスト

## 目的

短期記憶履歴システムの全体的な動作を確認する統合テストを作成する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `tests/integration/test_memory_history.py` | 統合テスト（新規） |

---

## テストシナリオ

### 1. 短期記憶の履歴保存

#### シナリオ: 初回の短期記憶生成

```python
async def test_first_short_term_memory_saved_as_version_1():
    """初回の短期記憶は version=1 で保存される"""
    # Given: チャンネルにメッセージがある
    # When: GenerateMemoryUseCase を実行
    # Then: 短期記憶が version=1 で保存される
```

#### シナリオ: 2回目以降の短期記憶生成

```python
async def test_subsequent_short_term_memory_increments_version():
    """2回目以降の短期記憶は version がインクリメントされる"""
    # Given: version=1 の短期記憶が存在
    # And: 更新条件を満たしている（idle 時間経過）
    # When: GenerateMemoryUseCase を実行
    # Then: 短期記憶が version=2 で保存される
    # And: version=1 の短期記憶も残っている
```

### 2. 更新トリガー

#### シナリオ: idle 時間による更新

```python
async def test_update_triggered_by_idle_time():
    """conversation_idle_seconds 経過で更新される"""
    # Given: 既存の短期記憶がある
    # And: 最新メッセージから 2 時間以上経過
    # When: GenerateMemoryUseCase を実行
    # Then: 新しい短期記憶が保存される
```

#### シナリオ: メッセージ数による更新

```python
async def test_update_triggered_by_message_count():
    """message_threshold 超過で更新される"""
    # Given: 既存の短期記憶がある
    # And: 前回更新以降のメッセージが 50 件以上
    # When: GenerateMemoryUseCase を実行
    # Then: 新しい短期記憶が保存される
```

#### シナリオ: 条件未満で更新されない

```python
async def test_no_update_when_conditions_not_met():
    """条件を満たさない場合は更新されない"""
    # Given: 既存の短期記憶がある
    # And: idle 時間未到達（1 時間）
    # And: メッセージ数未満（30 件）
    # When: GenerateMemoryUseCase を実行
    # Then: 短期記憶は更新されない
```

### 3. 長期記憶への統合

#### シナリオ: 短期記憶保存後の長期記憶更新

```python
async def test_long_term_memory_updated_after_short_term_save():
    """短期記憶保存直後に長期記憶が更新される"""
    # Given: 既存のチャンネル長期記憶がある
    # When: 短期記憶が新バージョンとして保存される
    # Then: チャンネル長期記憶が更新される
    # And: ワークスペース長期記憶が更新される
```

### 4. Context 構築

#### シナリオ: 履歴の取得と並び替え

```python
async def test_context_contains_history_in_chronological_order():
    """Context に履歴が古い順で含まれる"""
    # Given: version=1,2,3,4,5 の短期記憶が存在
    # When: build_context_with_memory を実行
    # Then: short_term_memory_history に 5 件が古い順で格納
    # And: short_term_memory は最新（version=5）の内容
```

#### シナリオ: 履歴数の制限

```python
async def test_context_limits_history_count():
    """max_history_count で履歴数が制限される"""
    # Given: version=1〜10 の短期記憶が存在
    # And: max_history_count=5
    # When: build_context_with_memory を実行
    # Then: short_term_memory_history に最新 5 件のみ（version=6〜10）
```

### 5. ワークスペース短期記憶の廃止

#### シナリオ: WS 短期記憶が参照されない

```python
async def test_workspace_short_term_memory_not_referenced():
    """ワークスペース短期記憶が Context に含まれない"""
    # Given: DB にワークスペース短期記憶が存在
    # When: build_context_with_memory を実行
    # Then: workspace_short_term_memory フィールドが存在しない
```

#### シナリオ: WS 短期記憶が生成されない

```python
async def test_workspace_short_term_memory_not_generated():
    """ワークスペース短期記憶が生成されない"""
    # When: GenerateMemoryUseCase を実行
    # Then: ワークスペース短期記憶は生成されない
    # And: ワークスペース長期記憶のみ生成される
```

### 6. スレッド短期記憶（履歴化しない）

#### シナリオ: スレッド短期記憶は上書き

```python
async def test_thread_short_term_memory_overwrites():
    """スレッド短期記憶は履歴化せず上書きされる"""
    # Given: スレッドの短期記憶が存在（version=1）
    # When: スレッドの短期記憶を再生成
    # Then: version=1 のまま上書きされる
    # And: version=2 は作成されない
```

### 7. 履歴機能無効時

#### シナリオ: enabled=false で上書き

```python
async def test_history_disabled_overwrites():
    """履歴機能無効時は従来通り上書き"""
    # Given: short_term_history.enabled=false
    # And: 既存の短期記憶（version=1）
    # When: GenerateMemoryUseCase を実行
    # Then: version=1 が上書きされる
    # And: version=2 は作成されない
```

---

## テスト設計

### フィクスチャ

```python
@pytest.fixture
def memory_config_with_history():
    """履歴機能有効の設定"""
    return MemoryConfig(
        database_path=":memory:",
        short_term_history=ShortTermHistoryConfig(
            enabled=True,
            max_history_count=5,
            conversation_idle_seconds=7200,
            message_threshold=50,
        ),
    )

@pytest.fixture
def memory_config_without_history():
    """履歴機能無効の設定"""
    return MemoryConfig(
        database_path=":memory:",
        short_term_history=ShortTermHistoryConfig(
            enabled=False,
        ),
    )

@pytest.fixture
async def memory_repository(engine):
    """テスト用リポジトリ"""
    return SQLiteMemoryRepository(engine)

@pytest.fixture
def mock_summarizer():
    """モック MemorySummarizer"""
    summarizer = AsyncMock(spec=MemorySummarizer)
    summarizer.summarize.return_value = "Generated memory content"
    return summarizer
```

### モック戦略

| コンポーネント | モック方法 |
|--------------|-----------|
| MemorySummarizer | AsyncMock で LLM 呼び出しをモック |
| MessageRepository | インメモリ実装または AsyncMock |
| ChannelRepository | インメモリ実装または AsyncMock |
| MemoryRepository | 実際の SQLite 実装（:memory:） |

---

## 手動検証手順

### 1. 環境準備

```bash
# 依存関係のインストール
uv sync

# テスト用設定ファイルの準備
cp config.yaml.example config.yaml
# short_term_history セクションを追加
```

### 2. アプリケーション起動

```bash
uv run python -m myao2
```

### 3. 検証手順

1. **短期記憶の生成確認**
   - チャンネルにメッセージを投稿
   - 2 時間待機するか、50 件以上のメッセージを投稿
   - DB で短期記憶を確認

   ```bash
   sqlite3 ./data/memory.db "SELECT scope_id, version, updated_at FROM memories WHERE scope='channel' AND memory_type='short_term';"
   ```

2. **履歴の確認**
   - 追加でメッセージを投稿し、再度更新条件を満たす
   - DB で version=2 が追加されていることを確認

3. **長期記憶の確認**
   - 短期記憶更新後に長期記憶が更新されていることを確認

   ```bash
   sqlite3 ./data/memory.db "SELECT scope_id, updated_at FROM memories WHERE scope='channel' AND memory_type='long_term';"
   ```

4. **プロンプトの確認**
   - ボットにメンションして応答を確認
   - ログで履歴が含まれていることを確認

---

## 完了基準

- [ ] 全統合テストが通過する
- [ ] 短期記憶が履歴として保存される
- [ ] 更新トリガー（idle / メッセージ数）が正しく動作する
- [ ] 長期記憶が短期記憶保存後に更新される
- [ ] Context に履歴が正しい順序で含まれる
- [ ] ワークスペース短期記憶が参照・生成されない
- [ ] スレッド短期記憶が上書きされる
- [ ] 履歴機能無効時に従来通り動作する
- [ ] 手動検証で期待通りの動作を確認
