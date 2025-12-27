# Phase 2: コンテキスト管理 - 実装手順書

## 目標

会話履歴を考慮した応答を実現する。

## 成果物

会話の流れを理解して応答できるボット

- スレッド/チャンネルの会話履歴を踏まえた応答
- SQLite による会話履歴の永続化
- 過去のやり取りを覚えた自然な会話

---

## 前提条件

### Phase 1 完了

Phase 1 で以下が実装済みであること：

- クリーンアーキテクチャの基本構造
- Slack 連携（Socket Mode、メンション検出）
- LLM 応答（LiteLLM）
- エンティティ: User, Channel, Message
- Protocol: MessagingService, ResponseGenerator
- ユースケース: ReplyToMentionUseCase

### 追加のSlackスコープ

Phase 1 に加えて以下のスコープが必要：

- `channels:history` - チャンネル履歴の読み取り（Phase 1 で設定済み）
- `groups:history` - プライベートチャンネル履歴（必要に応じて）

### 依存ライブラリ追加

```toml
# pyproject.toml
dependencies = [
    # ... 既存の依存関係
    "sqlmodel>=0.0.24",  # 追加
]
```

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | SQLite永続化基盤 | [01-sqlite-persistence.md](./01-sqlite-persistence.md) | - |
| 02 | メッセージリポジトリ実装 | [02-message-repository.md](./02-message-repository.md) | 01 |
| 03 | Slack履歴取得 | [03-slack-history.md](./03-slack-history.md) | - |
| 04 | コンテキスト付き応答生成 | [04-context-response.md](./04-context-response.md) | - |
| 05 | ユースケース統合 | [05-usecase-integration.md](./05-usecase-integration.md) | 02, 03, 04 |

---

## 実装順序

```
[01] SQLite永続化基盤    [03] Slack履歴取得    [04] コンテキスト付き応答
        ↓                     │                      │
[02] メッセージ              │                      │
    リポジトリ実装            │                      │
        └──────────────┬──────┴──────────────────────┘
                       ↓
            [05] ユースケース統合
                       ↓
                  動作確認
```

タスク 01, 03, 04 は並行して実装可能。

---

## タスク概要

### 01: SQLite永続化基盤

SQLModel を使ったデータベース基盤を構築する。

- MessageModel テーブル定義
- DatabaseManager（エンジン生成、テーブル作成）
- MessageRepository Protocol 定義
- MemoryConfig 追加

### 02: メッセージリポジトリ実装

MessageRepository の SQLite 実装を作成する。

- SQLiteMessageRepository 実装
- CRUD 操作（save, find_by_channel, find_by_thread, find_by_id）
- エンティティとモデルの相互変換

### 03: Slack履歴取得

Slack API を使ってチャンネル/スレッドの履歴を取得する。

- ConversationHistoryService Protocol 定義
- SlackConversationHistoryService 実装
- conversations.history / conversations.replies の呼び出し

### 04: コンテキスト付き応答生成

会話履歴を考慮した応答生成を実装する。

- ResponseGenerator Protocol の拡張（conversation_history 追加）
- LiteLLMResponseGenerator の修正
- 後方互換性の維持

### 05: ユースケース統合

全コンポーネントを統合し、コンテキスト管理機能を完成させる。

- ReplyToMentionUseCase の修正
- エントリポイント（__main__.py）の更新
- 受信/応答メッセージの永続化

---

## Phase 2 完了の検証方法

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

2. チャンネルで複数回やり取り

```
あなた: @myao2 こんにちは
myao2: こんにちは！何かお手伝いできることはありますか？

あなた: @myao2 今日の天気はどうかな
myao2: [過去の会話を踏まえた応答]
```

3. スレッドでのやり取りでも同様に確認

4. データベースにデータが保存されていることを確認

```bash
sqlite3 ./data/memory.db "SELECT * FROM messages LIMIT 5;"
```

---

## ディレクトリ構造（Phase 2 完了時）

```
src/myao2/
├── __init__.py
├── __main__.py              # エントリポイント（修正）
├── config/
│   ├── __init__.py
│   ├── loader.py
│   └── models.py            # MemoryConfig 追加
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── user.py
│   │   └── channel.py
│   ├── repositories/        # 新規
│   │   ├── __init__.py
│   │   └── message_repository.py
│   └── services/
│       ├── __init__.py
│       └── protocols.py     # ConversationHistoryService 追加
├── application/
│   ├── __init__.py
│   └── use_cases/
│       ├── __init__.py
│       └── reply_to_mention.py  # 修正
├── infrastructure/
│   ├── __init__.py
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── messaging.py
│   │   ├── event_adapter.py
│   │   └── history.py       # 新規
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   └── response_generator.py  # 修正
│   └── persistence/         # 新規
│       ├── __init__.py
│       ├── database.py
│       ├── models.py
│       └── message_repository.py
└── presentation/
    ├── __init__.py
    └── slack_handlers.py

tests/
├── __init__.py
├── conftest.py
├── config/
│   └── test_loader.py
├── domain/
│   ├── entities/
│   │   └── test_message.py
│   └── repositories/        # 新規
│       └── test_message_repository.py
├── application/
│   └── use_cases/
│       └── test_reply_to_mention.py  # 修正
└── infrastructure/
    ├── slack/
    │   ├── test_messaging.py
    │   ├── test_event_adapter.py
    │   └── test_history.py  # 新規
    ├── llm/
    │   ├── test_client.py
    │   └── test_response_generator.py  # 修正
    └── persistence/         # 新規
        ├── test_database.py
        └── test_message_repository.py
```

---

## 設計上の考慮事項

### プラットフォーム非依存

- Domain層の Repository Protocol は Slack に依存しない
- ConversationHistoryService も抽象化
- 将来 Discord 等に対応する際も Domain/Application 層は変更不要

### 後方互換性

- ResponseGenerator の conversation_history はオプショナル
- 履歴なしでも従来通り動作

### パフォーマンス

- 履歴取得は limit で件数を制限（デフォルト: 20件）
- SQLite のインデックスを適切に設定
- Phase 2 ではキャッシュは実装しない（シンプルさ優先）

### エラーハンドリング

- データベースエラーは適切な例外に変換
- Slack API エラーはログに記録
- LLM エラーは既存の例外クラスを使用
