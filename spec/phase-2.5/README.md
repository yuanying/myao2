# Phase 2.5: 非同期化 - 実装手順書

## 目標

Phase 3「自律的応答」の実現に向けて、アプリケーション全体を asyncio ベースの非同期アーキテクチャに移行する。

## 成果物

非同期で動作するメンション応答ボット

- asyncio イベントループ上で全コンポーネントが動作
- Slack Socket Mode の非同期接続
- LLM API の非同期呼び出し
- Phase 3 の並行処理（Slackイベント + 定期チェック）の基盤

---

## 背景

Phase 3 では以下の並行処理が必要になる：

- Slack イベントの受信・処理（Socket Mode）
- 定期的な応答判定ループ（例: 30秒ごと）
- LLM API 呼び出し（I/O バウンド）
- データベースアクセス（I/O バウンド）

現在の同期実装では、`runner.start()` がメインスレッドをブロックするため、これらを効率的に並行実行できない。

---

## 前提条件

### Phase 2 完了

Phase 2 で以下が実装済みであること：

- SQLite 永続化基盤（DatabaseManager, MessageModel）
- MessageRepository（SQLiteMessageRepository）
- Slack 履歴取得（ConversationHistoryService）
- Context ドメインモデル
- コンテキスト付き応答生成
- ユースケース統合

### 既存の依存ライブラリ

以下は既に asyncio をサポート：

- `slack-bolt>=1.18.0` - AsyncApp, AsyncSocketModeHandler
- `litellm>=1.0.0` - acompletion()
- `sqlmodel>=0.0.22` - AsyncSession（SQLAlchemy async 統合）
- `pytest-asyncio>=0.23.0` - 非同期テスト

### 追加の依存ライブラリ

```toml
# pyproject.toml
dependencies = [
    # ... 既存の依存関係
    "aiosqlite>=0.20.0",  # SQLite 非同期ドライバ
]
```

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | Protocol 非同期化 | [01-async-protocols.md](./01-async-protocols.md) | - |
| 02 | LLM クライアント非同期化 | [02-async-llm.md](./02-async-llm.md) | 01 |
| 03 | Slack クライアント非同期化 | [03-async-slack.md](./03-async-slack.md) | 01 |
| 04 | リポジトリ非同期化 | [04-async-repository.md](./04-async-repository.md) | 01 |
| 05 | ユースケース非同期化 | [05-async-usecase.md](./05-async-usecase.md) | 02, 03, 04 |
| 06 | プレゼンテーション層非同期化 | [06-async-presentation.md](./06-async-presentation.md) | 03, 05 |
| 07 | エントリポイント非同期化 | [07-async-entrypoint.md](./07-async-entrypoint.md) | 06 |
| 08 | 統合テスト・動作確認 | [08-integration-test.md](./08-integration-test.md) | 07 |

---

## 実装順序

```
[01] Protocol 非同期化
    ├── [02] LLM クライアント非同期化
    ├── [03] Slack クライアント非同期化
    └── [04] リポジトリ非同期化
            │
            ▼
      [05] ユースケース非同期化
            │
            ▼
      [06] プレゼンテーション層非同期化
            │
            ▼
      [07] エントリポイント非同期化
            │
            ▼
      [08] 統合テスト・動作確認
```

タスク 02, 03, 04 は並行して実装可能。

---

## タスク概要

### 01: Protocol 非同期化

全 Protocol を `async def` に変更する。

- `MessagingService.send_message()` → `async def send_message()`
- `ResponseGenerator.generate()` → `async def generate()`
- `MessageRepository` の全メソッドを `async def` に変更
- `ConversationHistoryService` の全メソッドを `async def` に変更

### 02: LLM クライアント非同期化

LiteLLM の非同期 API を使用する。

- `litellm.completion()` → `litellm.acompletion()`
- `LLMClient.complete()` → `async def complete()`
- `LiteLLMResponseGenerator.generate()` → `async def generate()`

### 03: Slack クライアント非同期化

Slack Bolt の非同期モードに移行する。

- `App` → `AsyncApp`
- `SocketModeHandler` → `AsyncSocketModeHandler`
- `WebClient` → `AsyncWebClient`
- `SlackMessagingService` の全メソッドを `async def` に変更
- `SlackEventAdapter.to_message()` → `async def to_message()`

### 04: リポジトリ非同期化

SQLModel の AsyncSession + aiosqlite を使用する。

- `DatabaseManager` を非同期化（`create_async_engine`, `async_sessionmaker`）
- `SQLiteMessageRepository` を `AsyncSession` 対応に変更
- 接続文字列を `sqlite+aiosqlite:///path` 形式に変更

### 05: ユースケース非同期化

全ユースケースを非同期化する。

- `ReplyToMentionUseCase.execute()` → `async def execute()`
- 内部呼び出しに `await` を追加

### 06: プレゼンテーション層非同期化

イベントハンドラを非同期化する。

- `def handle_app_mention()` → `async def handle_app_mention()`
- `AsyncApp` への対応

### 07: エントリポイント非同期化

main 関数を非同期化する。

- `def main()` → `async def main()`
- `asyncio.run(main())` を追加
- `KeyboardInterrupt` → `asyncio.CancelledError` 対応

### 08: 統合テスト・動作確認

全体の動作確認とテスト更新。

- `uv run pytest` で全テスト通過
- `uv run ty check` で型チェック通過
- `uv run ruff check .` で Linter 通過
- 実機でメンション応答動作確認

---

## 主な変更点

| コンポーネント | 変更前 | 変更後 |
|--------------|--------|--------|
| エントリポイント | `def main()` | `async def main()` + `asyncio.run()` |
| Slack App | `App` | `AsyncApp` |
| Socket Mode | `SocketModeHandler.start()` | `AsyncSocketModeHandler.start_async()` |
| WebClient | `WebClient` | `AsyncWebClient` |
| LLM 呼び出し | `litellm.completion()` | `litellm.acompletion()` |
| DB エンジン | `create_engine()` | `create_async_engine()` + aiosqlite |
| DB セッション | `Session` | `AsyncSession` + `async_sessionmaker` |
| イベントハンドラ | `def handle_*()` | `async def handle_*()` |

---

## 影響を受けるファイル

### Domain 層

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/services/protocols.py` | Protocol を async に変更 |
| `src/myao2/domain/repositories/message_repository.py` | Protocol を async に変更 |

### Infrastructure 層

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/client.py` | acompletion() 使用 |
| `src/myao2/infrastructure/llm/response_generator.py` | async def generate() |
| `src/myao2/infrastructure/slack/client.py` | AsyncApp, AsyncSocketModeHandler |
| `src/myao2/infrastructure/slack/messaging.py` | AsyncWebClient |
| `src/myao2/infrastructure/slack/event_adapter.py` | async def to_message() |
| `src/myao2/infrastructure/slack/history.py` | async def fetch_*() |
| `src/myao2/infrastructure/persistence/database.py` | create_async_engine, async_sessionmaker |
| `src/myao2/infrastructure/persistence/message_repository.py` | AsyncSession 対応 |

### Application 層

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/application/use_cases/reply_to_mention.py` | async def execute() |

### Presentation 層

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/presentation/slack_handlers.py` | async def handle_*() |

### エントリポイント

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/__main__.py` | asyncio.run(main()) |

### テスト

| ファイル | 変更内容 |
|---------|---------|
| `tests/infrastructure/llm/test_client.py` | pytest-asyncio 対応 |
| `tests/infrastructure/llm/test_response_generator.py` | pytest-asyncio 対応 |
| `tests/infrastructure/slack/test_messaging.py` | pytest-asyncio 対応 |
| `tests/infrastructure/slack/test_event_adapter.py` | pytest-asyncio 対応 |
| `tests/infrastructure/slack/test_history.py` | pytest-asyncio 対応 |
| `tests/infrastructure/persistence/test_message_repository.py` | pytest-asyncio 対応 |
| `tests/application/use_cases/test_reply_to_mention.py` | pytest-asyncio 対応 |

---

## テスト戦略

### 非同期テストの基本パターン

```python
import pytest

class TestAsyncComponent:
    @pytest.fixture
    def component(self) -> AsyncComponent:
        return AsyncComponent()

    @pytest.mark.asyncio
    async def test_async_method(self, component: AsyncComponent) -> None:
        result = await component.async_method()
        assert result == expected
```

### モッククラスの非同期対応

**変更前:**
```python
class MockMessagingService:
    def send_message(self, channel_id: str, text: str, thread_ts: str | None = None) -> None:
        self.sent_messages.append(...)
```

**変更後:**
```python
class MockMessagingService:
    async def send_message(self, channel_id: str, text: str, thread_ts: str | None = None) -> None:
        self.sent_messages.append(...)
```

### pyproject.toml の設定

既存の設定で対応済み：

```toml
[tool.uv]
dev-dependencies = [
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## リスクと対策

### リスク1: aiosqlite の特性

**注意点:** aiosqlite は実際には非ブロッキング I/O ではなく、バックグラウンドスレッドを使用している。ただし asyncio インターフェースを提供するため、他の非同期処理との統合が容易。

**対策:** 性能が問題になる場合は将来的に PostgreSQL + asyncpg への移行を検討。

### リスク2: AsyncSession の dispose

**注意点:** `create_async_engine` 使用後は `await engine.dispose()` を呼び出す必要がある。省略するとイベントループ終了時にエラーが発生する可能性がある。

**対策:** エントリポイントで適切にクリーンアップ処理を実装。

### リスク3: テストの大幅な書き換え

**対策:** `asyncio_mode = "auto"` により、テストメソッドを `async def` に変更するだけで多くのテストが動作。

### リスク4: 既存コードとの互換性

**対策:** Protocol を先に変更し、実装を段階的に移行。型チェックで不整合を早期発見。

---

## Phase 2.5 完了の検証方法

### 自動テスト

```bash
# 全テストの実行
uv run pytest

# Linter
uv run ruff check .

# 型チェック
uv run ty check
```

### 手動検証

1. アプリケーションを起動

```bash
uv run python -m myao2
```

2. Socket Mode で非同期接続が確立されることを確認

3. メンションに応答できることを確認

```
あなた: @myao2 こんにちは
myao2: [非同期で生成された応答]
```

---

## 完了基準

- [x] エントリポイントが `async def main()` + `asyncio.run()` で動作
- [x] Slack Socket Mode が非同期モードで接続
- [x] メンション時に非同期で応答生成・送信
- [x] `uv run pytest` が全テスト通過
- [x] `uv run ty check` が通過
- [x] `uv run ruff check .` が通過
- [ ] 実機でメンション応答動作確認
