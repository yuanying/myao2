# Phase 3: 自律的応答 - 実装手順書

## 目標

人間のように適切なタイミングで自律的に応答するボットを実現する。

## 成果物

誰も反応しないメッセージに自律的に反応するボット

- 定期的なチャンネル監視（check_interval_seconds ごと）
- LLM による応答判定（応答すべきか否かを判断）
- 最低待機時間（min_wait_seconds）の考慮
- 応答対象のスレッド/チャンネル会話のコンテキスト構築
- 補助コンテキストとしての関連チャンネルメッセージ

---

## 前提条件

### Phase 2.5 完了

Phase 2.5 で以下が実装済みであること：

- asyncio ベースの非同期アーキテクチャ
- AsyncApp, AsyncSocketModeHandler
- 非同期 LLM 呼び出し（acompletion）
- 非同期データベースアクセス
- メンション応答機能

### 追加の Slack スコープ

Phase 2 で設定済み：

- `channels:history` - チャンネル履歴の読み取り
- `groups:history` - プライベートチャンネル履歴
- `channels:read` - チャンネル一覧の取得
- `users.conversations` - ボットが参加しているチャンネルの取得

### 追加の依存ライブラリ

なし（既存の依存関係で対応可能）

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | ResponseConfig モデル追加 | [01-response-config.md](./01-response-config.md) | - |
| 02 | チャンネル監視サービス | [02-channel-monitor.md](./02-channel-monitor.md) | 01 |
| 03 | 応答判定サービス | [03-response-judgment.md](./03-response-judgment.md) | 01 |
| 04 | 拡張 Context（補助コンテキスト） | [04-extended-context.md](./04-extended-context.md) | - |
| 05 | 自律応答ユースケース | [05-autonomous-response-usecase.md](./05-autonomous-response-usecase.md) | 02, 03, 04 |
| 06 | 定期チェックループ | [06-periodic-check-loop.md](./06-periodic-check-loop.md) | 05 |
| 07 | エントリポイント統合 | [07-entrypoint-integration.md](./07-entrypoint-integration.md) | 06 |
| 08 | 統合テスト・動作確認 | [08-integration-test.md](./08-integration-test.md) | 07 |

---

## 実装順序（DAG図）

```
[01] ResponseConfig ─────────────────┐
          │                          │
          ├──> [02] チャンネル監視     │
          │                          │
          └──> [03] 応答判定         │
                     │               │
[04] 拡張 Context ───┼───────────────┘
                     ↓
              [05] 自律応答ユースケース
                     │
                     ↓
              [06] 定期チェックループ
                     │
                     ↓
              [07] エントリポイント統合
                     │
                     ↓
              [08] 統合テスト
```

タスク 01, 04 は独立して実装可能。
タスク 02, 03 は 01 に依存するが、相互に独立。

---

## タスク概要

### 01: ResponseConfig モデル追加

config.yaml の `response` セクションを Config に反映する。

- ResponseConfig データクラスの定義
- check_interval_seconds, min_wait_seconds, enabled フィールド
- Config への統合
- loader.py での response セクション読み込み

### 02: チャンネル監視サービス

ボットが参加しているチャンネルを監視し、未応答メッセージを検出する。

- ChannelMonitor Protocol の定義（Domain 層）
- SlackChannelMonitor 実装（Infrastructure 層）
- 監視対象チャンネルの取得
- チャンネルごとの最新メッセージ取得

### 03: 応答判定サービス

LLM を使って応答すべきかを判定する。

- ResponseJudgment Protocol の定義（Domain 層）
- JudgmentResult 値オブジェクト
- LLMResponseJudgment 実装（Infrastructure 層）
- 応答判定用プロンプトの設計
- config.yaml の llm.judgment 設定の使用

### 04: 拡張 Context（補助コンテキスト）

応答対象以外のチャンネルメッセージを補助コンテキストとして提供する。

- Context への auxiliary_context フィールド追加
- build_system_prompt での補助コンテキスト統合

### 05: 自律応答ユースケース

チャンネル状態を受け取り、応答判定と応答生成を実行する。

- AutonomousResponseUseCase の定義
- 処理フロー設計
- min_wait_seconds の考慮
- ReplyToMentionUseCase との責務分離

### 06: 定期チェックループ

asyncio タスクとして定期的にチャンネルをチェックする。

- PeriodicChecker サービスの定義
- asyncio.sleep による間隔制御
- グレースフルシャットダウン

### 07: エントリポイント統合

main() で定期チェックループと Socket Mode を並行実行する。

- asyncio.gather() による並行実行
- 依存オブジェクトの初期化と注入

### 08: 統合テスト・動作確認

全コンポーネントの統合動作を確認する。

- 統合テストの設計
- 手動検証手順
- 動作確認チェックリスト

---

## 主な変更点

| コンポーネント | 変更前 | 変更後 |
|--------------|--------|--------|
| config.yaml | response セクション未使用 | check_interval_seconds, min_wait_seconds を使用 |
| Config | response フィールドなし | ResponseConfig を追加 |
| Context | conversation_history のみ | auxiliary_context（補助コンテキスト）追加 |
| エントリポイント | Socket Mode のみ | Socket Mode + 定期チェックループの並行実行 |
| LLM config | default のみ使用 | judgment 設定も使用 |

---

## 影響を受けるファイル

### 新規作成

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/channel_monitor.py` | ChannelMonitor Protocol |
| `src/myao2/domain/services/response_judgment.py` | ResponseJudgment Protocol |
| `src/myao2/domain/entities/judgment_result.py` | JudgmentResult 値オブジェクト |
| `src/myao2/infrastructure/slack/channel_monitor.py` | SlackChannelMonitor 実装 |
| `src/myao2/infrastructure/llm/response_judgment.py` | LLMResponseJudgment 実装 |
| `src/myao2/application/use_cases/autonomous_response.py` | 自律応答ユースケース |
| `src/myao2/application/services/periodic_checker.py` | 定期チェックサービス |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | ResponseConfig 追加 |
| `src/myao2/config/loader.py` | response セクション読み込み |
| `src/myao2/domain/entities/context.py` | auxiliary_context 追加 |
| `src/myao2/domain/entities/__init__.py` | エクスポート追加 |
| `src/myao2/domain/services/__init__.py` | Protocol エクスポート追加 |
| `src/myao2/__main__.py` | 定期チェックループ起動 |

### テスト

| ファイル | 説明 |
|---------|------|
| `tests/config/test_models.py` | ResponseConfig テスト追加 |
| `tests/domain/entities/test_context.py` | auxiliary_context テスト追加 |
| `tests/domain/entities/test_judgment_result.py` | 新規 |
| `tests/infrastructure/slack/test_channel_monitor.py` | 新規 |
| `tests/infrastructure/llm/test_response_judgment.py` | 新規 |
| `tests/application/use_cases/test_autonomous_response.py` | 新規 |
| `tests/application/services/test_periodic_checker.py` | 新規 |

---

## テスト戦略

### TDD アプローチ

各タスクは以下の手順で実装する：

1. Protocol / データ構造の型シグネチャを定義
2. テストケースを作成（失敗するテスト）
3. 実装コードを書いてテストを通す
4. リファクタリング

### テストの分類

- **単体テスト**: 各コンポーネントの独立した動作確認
- **統合テスト**: コンポーネント間の連携確認
- **モック活用**: LLM / Slack API は Protocol 経由でモック可能

---

## Phase 3 完了の検証方法

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

2. チャンネルでメッセージを投稿し、誰も反応しない状態を作る

3. min_wait_seconds（デフォルト 5分）経過後、ボットが自律的に応答することを確認

4. 応答判定ログを確認し、判定理由が出力されていることを確認

5. 複数人が活発に会話している場合、ボットが割り込まないことを確認

---

## ディレクトリ構造（Phase 3 完了時）

```
src/myao2/
├── __init__.py
├── __main__.py              # 定期チェックループ起動（修正）
├── config/
│   ├── __init__.py
│   ├── loader.py            # response セクション読み込み（修正）
│   └── models.py            # ResponseConfig 追加（修正）
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py      # エクスポート追加（修正）
│   │   ├── message.py
│   │   ├── user.py
│   │   ├── channel.py
│   │   ├── context.py       # auxiliary_context 追加（修正）
│   │   └── judgment_result.py  # 新規
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── message_repository.py
│   └── services/
│       ├── __init__.py      # Protocol エクスポート追加（修正）
│       ├── protocols.py
│       ├── channel_monitor.py   # 新規
│       └── response_judgment.py # 新規
├── application/
│   ├── __init__.py
│   ├── use_cases/
│   │   ├── __init__.py
│   │   ├── reply_to_mention.py
│   │   └── autonomous_response.py  # 新規
│   └── services/            # 新規
│       ├── __init__.py
│       └── periodic_checker.py
├── infrastructure/
│   ├── __init__.py
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── messaging.py
│   │   ├── event_adapter.py
│   │   ├── history.py
│   │   └── channel_monitor.py  # 新規
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   ├── response_generator.py
│   │   └── response_judgment.py  # 新規
│   └── persistence/
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
│   └── test_loader.py       # ResponseConfig テスト追加
├── domain/
│   ├── entities/
│   │   ├── test_message.py
│   │   ├── test_context.py  # auxiliary_context テスト追加
│   │   └── test_judgment_result.py  # 新規
│   └── repositories/
│       └── test_message_repository.py
├── application/
│   ├── use_cases/
│   │   ├── test_reply_to_mention.py
│   │   └── test_autonomous_response.py  # 新規
│   └── services/            # 新規
│       └── test_periodic_checker.py
└── infrastructure/
    ├── slack/
    │   ├── test_messaging.py
    │   ├── test_event_adapter.py
    │   ├── test_history.py
    │   └── test_channel_monitor.py  # 新規
    ├── llm/
    │   ├── test_client.py
    │   ├── test_response_generator.py
    │   └── test_response_judgment.py  # 新規
    └── persistence/
        ├── test_database.py
        └── test_message_repository.py
```

---

## 設計上の考慮事項

### プラットフォーム非依存

- Domain 層の Protocol は Slack に依存しない
- ChannelMonitor, ResponseJudgment も抽象化
- 将来 Discord 等に対応する際も Domain/Application 層は変更不要

### 責務分離

- ChannelMonitor: チャンネル監視のみ
- ResponseJudgment: 応答判定のみ
- AutonomousResponseUseCase: 全体フローの調整
- PeriodicChecker: スケジューリングのみ

### 拡張性

- Phase 4 の記憶システムへの拡張を想定
- Context の auxiliary_context は補助情報として柔軟に拡張可能

### パフォーマンス

- check_interval_seconds でチェック頻度を制御
- 判定用 LLM は軽量モデル（llm.judgment）を使用可能
- 不要な API 呼び出しを避けるため、最終確認時刻を記録

### エラーハンドリング

- チェック失敗時は次回ループまで待機（サービス継続優先）
- Slack API エラーはログに記録
- LLM エラーは既存の例外クラスを使用
