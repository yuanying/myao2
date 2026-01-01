# Phase 4: 記憶システム - 実装手順書

## 目標

長期的な記憶を持つボットを実現する。

## 成果物

過去の会話を覚えていて、それに応じた反応ができるボット

- 長期記憶: ワークスペース、チャンネルの全期間の出来事を時系列で要約
- 短期記憶: ワークスペース、チャンネルの短期間の要約、およびスレッドの要約
- バックグラウンドでの定期的な記憶生成
- 応答生成時の記憶活用

---

## 記憶システムの構成

### 長期記憶（全期間の時系列で出来事を要約）

| スコープ | 説明 |
|---------|------|
| ワークスペース | ワークスペース全体の出来事を時系列で要約 |
| チャンネル | チャンネルごとの出来事を時系列で要約 |

### 短期記憶

| スコープ | 説明 |
|---------|------|
| ワークスペース | ワークスペースの直近の出来事を要約 |
| チャンネル | チャンネルの直近の出来事を要約 |
| スレッド | スレッドの内容を要約 |

---

## 前提条件

### Phase 3 完了

Phase 3 で以下が実装済みであること：

- 自律応答システム（AutonomousResponseUseCase）
- 定期チェックループ（PeriodicChecker）
- Context エンティティ（conversation_history, other_channel_messages）
- LLMClient による非同期 LLM 呼び出し
- DBConversationHistoryService による履歴取得
- JudgmentCache による応答判定キャッシュ

### 既存の設定

config.yaml の `memory` セクション：

```yaml
memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600  # 1時間ごと
```

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | MemoryConfig 拡張 | [01-memory-config.md](./01-memory-config.md) | - |
| 02 | Memory エンティティ定義 | [02-memory-entity.md](./02-memory-entity.md) | - |
| 03 | MemoryRepository プロトコルと SQLite 実装 | [03-memory-repository.md](./03-memory-repository.md) | 02 |
| 04 | Context への記憶フィールド追加 | [04-context-memory-fields.md](./04-context-memory-fields.md) | 02 |
| 05 | MemorySummarizer（LLM を使った記憶生成） | [05-memory-summarizer.md](./05-memory-summarizer.md) | 01, 02 |
| 06 | GenerateMemoryUseCase（記憶生成ユースケース） | [06-generate-memory-usecase.md](./06-generate-memory-usecase.md) | 03, 05 |
| 07 | バックグラウンド記憶生成サービス | [07-background-memory-service.md](./07-background-memory-service.md) | 06 |
| 08 | ResponseGenerator への記憶組み込み | [08-response-generator-memory.md](./08-response-generator-memory.md) | 04, 06 |
| 09 | エントリポイント統合 | [09-entrypoint-integration.md](./09-entrypoint-integration.md) | 07, 08 |
| 10 | 統合テスト・動作確認 | [10-integration-test.md](./10-integration-test.md) | 09 |

---

## 実装順序（DAG図）

```
[01] MemoryConfig ────────────────────┐
                                      │
[02] Memory エンティティ ──────────────┼───┐
          │                           │   │
          ├──> [03] MemoryRepository  │   │
          │                           │   │
          └──> [04] Context 拡張 ─────│───┼───────┐
                                      │   │       │
                    ┌─────────────────┘   │       │
                    │                     │       │
                    ↓                     │       │
              [05] MemorySummarizer ──────┘       │
                    │                             │
                    ↓                             │
              [06] GenerateMemoryUseCase          │
                    │                             │
                    ↓                             ↓
              [07] バックグラウンド記憶生成   [08] ResponseGenerator 記憶組み込み
                    │                             │
                    └──────────────┬──────────────┘
                                   ↓
                         [09] エントリポイント統合
                                   │
                                   ↓
                         [10] 統合テスト
```

タスク 01, 02 は独立して実装可能。
タスク 03, 04, 05 は 02 に依存するが、相互に独立。

---

## タスク概要

### 01: MemoryConfig 拡張

現在の MemoryConfig を拡張し、記憶生成に必要な設定を追加する。

- `short_term_window_hours`: 短期記憶の時間窓（時間）
- `long_term_summary_max_tokens`: 長期記憶の最大トークン数
- `short_term_summary_max_tokens`: 短期記憶の最大トークン数
- `memory_generation_llm`: 記憶生成に使用する LLM 設定名

### 02: Memory エンティティ定義

長期記憶と短期記憶を表現するドメインエンティティを定義する。

- `MemoryScope` 列挙型（WORKSPACE / CHANNEL / THREAD）
- `MemoryType` 列挙型（LONG_TERM / SHORT_TERM）
- `Memory` エンティティ（イミュータブル）
- 有効な組み合わせの定義

### 03: MemoryRepository プロトコルと SQLite 実装

記憶の永続化を担当するリポジトリを定義・実装する。

- MemoryRepository Protocol の定義
- SQLiteMemoryRepository の実装
- MemoryModel（SQLModel）の定義

### 04: Context への記憶フィールド追加

Context エンティティに記憶フィールドを追加する。

- `workspace_long_term_memory`: ワークスペースの長期記憶
- `workspace_short_term_memory`: ワークスペースの短期記憶
- `channel_long_term_memory`: チャンネルの長期記憶
- `channel_short_term_memory`: チャンネルの短期記憶
- `thread_memory`: スレッドの短期記憶

### 05: MemorySummarizer（LLM を使った記憶生成）

メッセージリストから記憶を生成するサービスを実装する。

- MemorySummarizer Protocol の定義
- LLMMemorySummarizer の実装
- 長期記憶用プロンプト設計（時系列要約）
- 短期記憶用プロンプト設計

### 06: GenerateMemoryUseCase（記憶生成ユースケース）

チャンネル/スレッドの記憶を生成するユースケースを実装する。

- ワークスペース記憶の生成
- チャンネル記憶の生成
- スレッド記憶の生成
- インクリメンタル更新のサポート

### 07: バックグラウンド記憶生成サービス

定期的に記憶を生成するバックグラウンドサービスを実装する。

- BackgroundMemoryGenerator の実装
- asyncio.Event ベースの停止制御
- エラーハンドリング

### 08: ResponseGenerator への記憶組み込み

LiteLLMResponseGenerator を拡張し、記憶を system prompt に含める。

- system prompt への記憶セクション追加
- 記憶の優先順位と配置

### 09: エントリポイント統合

`__main__.py` を修正し、記憶システムを統合する。

- 記憶関連コンポーネントの初期化
- バックグラウンドタスクへの追加
- AutonomousResponseUseCase への記憶注入

### 10: 統合テスト・動作確認

全コンポーネントの統合動作を確認する。

- 統合テストの設計
- 手動検証手順
- 動作確認チェックリスト

---

## 主な変更点

| コンポーネント | 変更前 | 変更後 |
|--------------|--------|--------|
| MemoryConfig | database_path, interval のみ | 記憶生成設定を追加 |
| Context | 記憶フィールドなし | 5つの記憶フィールド追加 |
| ResponseGenerator | 記憶なし | 記憶を system prompt に含める |
| エントリポイント | 記憶システムなし | BackgroundMemoryGenerator を起動 |
| SQLite モデル | memories テーブルなし | MemoryModel 追加 |

---

## 影響を受けるファイル

### 新規作成

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memory.py` | Memory, MemoryScope, MemoryType エンティティ |
| `src/myao2/domain/repositories/memory_repository.py` | MemoryRepository Protocol |
| `src/myao2/domain/services/memory_summarizer.py` | MemorySummarizer Protocol |
| `src/myao2/infrastructure/persistence/memory_repository.py` | SQLiteMemoryRepository |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | LLMMemorySummarizer |
| `src/myao2/application/use_cases/generate_memory.py` | GenerateMemoryUseCase |
| `src/myao2/application/services/background_memory.py` | BackgroundMemoryGenerator |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | MemoryConfig 拡張 |
| `src/myao2/config/loader.py` | memory セクション読み込み拡張 |
| `src/myao2/domain/entities/context.py` | 記憶フィールド追加 |
| `src/myao2/domain/entities/__init__.py` | Memory エクスポート追加 |
| `src/myao2/domain/repositories/__init__.py` | MemoryRepository エクスポート |
| `src/myao2/infrastructure/persistence/models.py` | MemoryModel 追加 |
| `src/myao2/infrastructure/persistence/__init__.py` | SQLiteMemoryRepository エクスポート |
| `src/myao2/infrastructure/llm/__init__.py` | LLMMemorySummarizer エクスポート |
| `src/myao2/infrastructure/llm/response_generator.py` | 記憶を system prompt に含める |
| `src/myao2/application/use_cases/autonomous_response.py` | 記憶取得・Context 設定 |
| `src/myao2/application/use_cases/reply_to_mention.py` | 記憶取得・Context 設定 |
| `src/myao2/__main__.py` | 記憶システム初期化・起動 |

### テスト

| ファイル | 説明 |
|---------|------|
| `tests/domain/entities/test_memory.py` | 新規 |
| `tests/domain/repositories/test_memory_repository.py` | 新規 |
| `tests/infrastructure/persistence/test_memory_repository.py` | 新規 |
| `tests/infrastructure/llm/test_memory_summarizer.py` | 新規 |
| `tests/application/use_cases/test_generate_memory.py` | 新規 |
| `tests/application/services/test_background_memory.py` | 新規 |
| `tests/config/test_loader.py` | MemoryConfig テスト追加 |
| `tests/domain/entities/test_context.py` | 記憶フィールドテスト追加 |
| `tests/infrastructure/llm/test_response_generator.py` | 記憶組み込みテスト追加 |

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
- **モック活用**: LLM / リポジトリは Protocol 経由でモック可能

### 重要なテストケース

| コンポーネント | テストケース |
|--------------|------------|
| Memory エンティティ | 不変性、比較、ファクトリメソッド、有効な組み合わせ検証 |
| MemoryRepository | CRUD 操作、スコープ検索、タイプ別検索 |
| MemorySummarizer | 長期記憶生成、短期記憶生成、既存記憶の更新 |
| GenerateMemoryUseCase | ワークスペース記憶生成、チャンネル記憶生成、スレッド記憶生成 |
| BackgroundMemoryGenerator | 起動・停止、間隔制御 |
| ResponseGenerator | 記憶ありの prompt 生成、記憶なしの prompt 生成 |

---

## Phase 4 完了の検証方法

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

2. チャンネルで複数のメッセージを投稿

3. `long_term_update_interval_seconds` 経過後、記憶が生成されることを確認

4. データベースで記憶を確認：

```bash
sqlite3 ./data/memory.db "SELECT * FROM memories;"
```

5. ボットが応答する際、記憶を考慮した応答になっていることを確認

6. ログで記憶生成・記憶使用が出力されていることを確認

---

## ディレクトリ構造（Phase 4 完了時）

```
src/myao2/
├── __init__.py
├── __main__.py                    # 記憶システム起動（修正）
├── config/
│   ├── __init__.py
│   ├── loader.py                  # memory 拡張読み込み（修正）
│   └── models.py                  # MemoryConfig 拡張（修正）
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py            # Memory エクスポート（修正）
│   │   ├── message.py
│   │   ├── user.py
│   │   ├── channel.py
│   │   ├── context.py             # 記憶フィールド追加（修正）
│   │   ├── judgment_result.py
│   │   ├── judgment_cache.py
│   │   └── memory.py              # 新規
│   ├── repositories/
│   │   ├── __init__.py            # MemoryRepository エクスポート（修正）
│   │   ├── message_repository.py
│   │   ├── channel_repository.py
│   │   ├── user_repository.py
│   │   ├── judgment_cache_repository.py
│   │   └── memory_repository.py   # 新規
│   └── services/
│       ├── __init__.py
│       ├── protocols.py
│       ├── channel_monitor.py
│       ├── response_judgment.py
│       ├── channel_sync.py
│       ├── message_formatter.py
│       └── memory_summarizer.py   # 新規
├── application/
│   ├── __init__.py
│   ├── use_cases/
│   │   ├── __init__.py
│   │   ├── reply_to_mention.py    # 記憶取得追加（修正）
│   │   ├── autonomous_response.py # 記憶取得追加（修正）
│   │   └── generate_memory.py     # 新規
│   └── services/
│       ├── __init__.py
│       ├── periodic_checker.py
│       └── background_memory.py   # 新規
├── infrastructure/
│   ├── __init__.py
│   ├── slack/
│   │   └── ...
│   ├── llm/
│   │   ├── __init__.py            # LLMMemorySummarizer エクスポート（修正）
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   ├── response_generator.py  # 記憶組み込み（修正）
│   │   ├── response_judgment.py
│   │   └── memory_summarizer.py   # 新規
│   └── persistence/
│       ├── __init__.py            # SQLiteMemoryRepository エクスポート（修正）
│       ├── database.py
│       ├── models.py              # MemoryModel 追加（修正）
│       ├── message_repository.py
│       ├── channel_repository.py
│       ├── user_repository.py
│       ├── judgment_cache_repository.py
│       └── memory_repository.py   # 新規
└── presentation/
    └── ...

tests/
├── __init__.py
├── conftest.py
├── config/
│   └── test_loader.py             # MemoryConfig テスト追加
├── domain/
│   ├── entities/
│   │   ├── test_message.py
│   │   ├── test_context.py        # 記憶フィールドテスト追加
│   │   ├── test_judgment_result.py
│   │   └── test_memory.py         # 新規
│   └── repositories/
│       └── ...
├── application/
│   ├── use_cases/
│   │   ├── test_reply_to_mention.py
│   │   ├── test_autonomous_response.py
│   │   └── test_generate_memory.py     # 新規
│   └── services/
│       ├── test_periodic_checker.py
│       └── test_background_memory.py   # 新規
└── infrastructure/
    ├── llm/
    │   ├── test_client.py
    │   ├── test_response_generator.py  # 記憶テスト追加
    │   ├── test_response_judgment.py
    │   └── test_memory_summarizer.py   # 新規
    └── persistence/
        ├── test_database.py
        ├── test_message_repository.py
        └── test_memory_repository.py   # 新規
```

---

## 設計上の考慮事項

### プラットフォーム非依存

- Memory エンティティは Slack に依存しない
- MemorySummarizer Protocol により実装を差し替え可能
- 将来的に異なる要約戦略にも対応可能

### スコープの階層

記憶は以下の階層で管理：

| スコープ | 長期記憶 | 短期記憶 |
|---------|:------:|:------:|
| ワークスペース | ○ | ○ |
| チャンネル | ○ | ○ |
| スレッド | - | ○ |

### インクリメンタル更新

長期記憶は全メッセージを毎回処理するのではなく：

1. 前回更新時の最新メッセージ ts を記録
2. 次回更新時は新しいメッセージのみ取得
3. 既存の長期記憶 + 新しいメッセージで更新

### パフォーマンス

- 記憶生成は `long_term_update_interval_seconds` ごと（デフォルト: 1時間）
- 記憶生成用 LLM は軽量モデルを使用可能（`memory_generation_llm` 設定）
- 短期記憶は `short_term_window_hours` の時間窓内のメッセージのみ処理

### エラーハンドリング

- 記憶生成失敗時は次回まで待機（サービス継続優先）
- 記憶取得失敗時は記憶なしで応答生成を継続
- 各エラーはログに記録

---

## エクストラタスク

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| extra04 | ResponseJudgment#judge インターフェース簡素化 | [extra04-judgment-interface-simplify.md](./extra04-judgment-interface-simplify.md) | - |
| extra05 | 全LLM呼び出しのJinja2テンプレート化 | [extra05-jinja2-templates.md](./extra05-jinja2-templates.md) | - |
| extra06 | 全LLM呼び出しのログ出力統一 | [extra06-llm-logging.md](./extra06-llm-logging.md) | - |
| extra07 | min_wait_seconds への jitter 追加 | [extra07-min-wait-jitter.md](./extra07-min-wait-jitter.md) | - |

### エクストラタスク概要

#### extra04: ResponseJudgment#judge インターフェース簡素化

ResponseJudgment#judge の引数を `context` のみに変更し、判定対象スレッドは
`context.target_thread_ts` から取得するようにする。同時に ChannelMonitor の
`get_unreplied_messages` を `get_unreplied_threads` に変更し、スレッド単位で
未応答を管理する。

#### extra05: 全LLM呼び出しのJinja2テンプレート化

ResponseGenerator 以外の LLM 呼び出し（ResponseJudgment, MemorySummarizer）でも
Jinja2 テンプレートを使用してシステムプロンプトを組み立てるようにする。
これによりプロンプトの管理方法を統一し、変更時の保守性を向上させる。

#### extra06: 全LLM呼び出しのログ出力統一

全ての LLM 呼び出し時にリクエスト内容とレスポンス内容をログ出力するようにする。
`config.logging.debug_llm_messages` フラグで統一的に制御し、
デバッグ時の問題特定を容易にする。

#### extra07: min_wait_seconds への jitter 追加

自律応答の待機時間にランダムなばらつき（jitter）を追加する。
`ResponseConfig.jitter_ratio`（デフォルト: 0.2 = ±20%）で制御し、
より人間らしい応答タイミングを実現する。

---

## 今後の拡張（Phase 5 以降）

- ユーザーごとの記憶（特定ユーザーとの関係性）
- 記憶の重要度スコアリング
- 記憶の自動アーカイブ・削除
- 記憶のベクトル検索（セマンティック検索）
- URL・画像の理解と記憶への反映
