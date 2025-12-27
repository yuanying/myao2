# Phase 1: 基盤構築 - 実装手順書

## 目標

プロジェクトの基盤を構築し、最小限のSlack連携とLLM応答を実現する。

## 成果物

メンションに応答できるシンプルなボット

- `uv run python -m myao2` で起動
- Slackでボットをメンションすると、LLMが生成した応答を返信

---

## 前提条件

### 開発環境

- Python 3.12+
- uv（パッケージマネージャー）

### Slackアプリ設定

1. Slack App を作成（https://api.slack.com/apps）
2. Socket Mode を有効化
3. 必要なスコープを設定:
   - `app_mentions:read` - メンションの読み取り
   - `chat:write` - メッセージの送信
   - `channels:history` - チャンネル履歴の読み取り
4. App-Level Token を取得（`connections:write` スコープ）
5. Bot Token を取得

### 環境変数

- `SLACK_BOT_TOKEN` - Bot User OAuth Token
- `SLACK_APP_TOKEN` - App-Level Token（Socket Mode用）

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | プロジェクトセットアップ | [01-project-setup.md](./01-project-setup.md) | - |
| 02 | 設定ファイル基盤 | [02-config-foundation.md](./02-config-foundation.md) | 01 |
| 03 | クリーンアーキテクチャ基本構造 | [03-clean-architecture.md](./03-clean-architecture.md) | 02 |
| 04 | Slack連携 | [04-slack-integration.md](./04-slack-integration.md) | 03 |
| 05 | LLM応答 | [05-llm-response.md](./05-llm-response.md) | 03 |

---

## 実装順序

```
[01] プロジェクトセットアップ
        ↓
[02] 設定ファイル基盤
        ↓
[03] クリーンアーキテクチャ基本構造
        ↓
    ┌───┴───┐
    ↓       ↓
[04]     [05]
Slack    LLM
連携     応答
    └───┬───┘
        ↓
    統合・動作確認
```

---

## タスク概要

### 01: プロジェクトセットアップ

開発環境を整備し、プロジェクトの骨格を作成する。

- pyproject.toml の作成
- ディレクトリ構造の作成
- ruff, ty の設定
- エントリポイントの作成

### 02: 設定ファイル基盤

config.yaml の読み込みと環境変数展開を実装する。

- YAML ファイルの読み込み
- `${VAR_NAME}` 形式の環境変数展開
- 設定値のバリデーション
- 型安全な設定アクセス

### 03: クリーンアーキテクチャ基本構造

各層の基本インターフェースとエンティティを定義する。

- Domain層: Message, User, Channel エンティティ
- Application層: ReplyToMentionUseCase
- Infrastructure層: 各Protocolの実装スタブ
- Presentation層: イベントハンドラ基本構造

### 04: Slack連携

Slack Bolt を使ったメッセージ受信・送信を実装する。

- Socket Mode によるイベント受信
- メッセージ送信機能
- メンション検出

### 05: LLM応答

LiteLLM を使った応答生成を実装する。

- LiteLLM ラッパー
- ペルソナ設定の適用
- 応答生成

---

## Phase 1 完了の検証方法

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

1. 環境変数を設定

```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
```

2. アプリケーションを起動

```bash
uv run python -m myao2
```

3. Slackでボットをメンション

```
@myao2 こんにちは
```

4. ボットが応答を返すことを確認

---

## ディレクトリ構造（Phase 1 完了時）

```
src/myao2/
├── __init__.py
├── __main__.py              # エントリポイント
├── config/
│   ├── __init__.py
│   ├── loader.py            # 設定読み込み
│   └── models.py            # 設定データクラス
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── user.py
│   │   └── channel.py
│   └── services/
│       ├── __init__.py
│       └── protocols.py     # MessagingService等
├── application/
│   ├── __init__.py
│   └── use_cases/
│       ├── __init__.py
│       └── reply_to_mention.py
├── infrastructure/
│   ├── __init__.py
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── client.py        # Boltアプリ
│   │   └── messaging.py     # MessagingService実装
│   └── llm/
│       ├── __init__.py
│       ├── client.py        # LiteLLMラッパー
│       └── response_generator.py
└── presentation/
    ├── __init__.py
    └── slack_handlers.py    # イベントハンドラ

tests/
├── __init__.py
├── conftest.py
├── config/
│   └── test_loader.py
├── domain/
│   └── entities/
│       └── test_message.py
├── application/
│   └── use_cases/
│       └── test_reply_to_mention.py
└── infrastructure/
    ├── slack/
    │   └── test_messaging.py
    └── llm/
        └── test_client.py
```
