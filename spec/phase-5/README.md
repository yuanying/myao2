# Phase 5: 短期記憶履歴システム

## 目標

チャンネルの短期記憶に履歴機能を追加し、より充実したコンテキスト情報を LLM に提供する。

## 成果物

直近の短期記憶履歴を参照でき、長期記憶と連携した一貫性のある記憶システム

- チャンネル短期記憶の履歴管理（バージョン管理）
- 短期記憶から長期記憶への自動統合
- ワークスペース短期記憶の廃止
- プロンプトへの履歴表示機能

---

## 主要な変更点

| コンポーネント | 変更前 | 変更後 |
|--------------|--------|--------|
| チャンネル短期記憶 | 上書き（1件のみ） | バージョン管理で履歴保持 |
| ワークスペース短期記憶 | 有効 | 廃止（参照しない） |
| 長期記憶更新 | バックグラウンド定期実行 | 短期記憶保存時に即座更新 |
| プロンプト表示 | 最新の短期記憶のみ | 直近5件の履歴を表示 |
| Memory エンティティ | version なし | version フィールド追加 |

---

## 記憶システムの新構成

### 長期記憶

| スコープ | 説明 | 変更 |
|---------|------|------|
| ワークスペース | ワークスペース全体の出来事を時系列で要約 | 維持 |
| チャンネル | チャンネルごとの出来事を時系列で要約 | 維持 |

### 短期記憶

| スコープ | 説明 | 変更 |
|---------|------|------|
| ワークスペース | ワークスペースの直近の出来事を要約 | **廃止** |
| チャンネル | チャンネルの直近の出来事を要約（履歴あり） | **履歴化** |
| スレッド | スレッドの内容を要約 | 維持（上書き） |

---

## 設定項目

```yaml
memory:
  # 既存項目
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600
  short_term_window_hours: 24
  long_term_summary_max_tokens: 500
  short_term_summary_max_tokens: 300
  # 追加項目
  short_term_history:
    enabled: true
    max_history_count: 5          # プロンプトに含める履歴数
    conversation_idle_seconds: 7200  # 会話終了判定（2時間）
    message_threshold: 50         # メッセージ数閾値
```

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 |
|---|--------|-----------|------|
| 01 | 短期記憶履歴システム（メイン） | [01-short-term-memory-history.md](./01-short-term-memory-history.md) | - |
| 01a | 設定項目の追加 | [01a-config-extension.md](./01a-config-extension.md) | - |
| 01b | Memory エンティティのバージョン対応 | [01b-memory-entity-version.md](./01b-memory-entity-version.md) | 01a |
| 01c | リポジトリの履歴対応 | [01c-memory-repository-history.md](./01c-memory-repository-history.md) | 01b |
| 01d | ワークスペース短期記憶廃止 | [01d-workspace-short-term-deprecation.md](./01d-workspace-short-term-deprecation.md) | 01c |
| 01e | Context の履歴対応 | [01e-context-history.md](./01e-context-history.md) | 01c, 01d |
| 01f | 記憶生成ユースケースの履歴対応 | [01f-generate-memory-history.md](./01f-generate-memory-history.md) | 01e |
| 01g | テンプレート更新 | [01g-template-update.md](./01g-template-update.md) | 01e, 01f |
| 01h | 統合テスト | [01h-integration-test.md](./01h-integration-test.md) | 01g |

---

## 実装順序（DAG図）

```
[01a] 設定項目追加
      │
      ↓
[01b] Memory エンティティ version 追加
      │
      ↓
[01c] リポジトリ履歴対応
      │
      ├──────────────────────────────┐
      ↓                              │
[01d] ワークスペース短期記憶廃止     │
      │                              │
      ↓                              │
[01e] Context 履歴対応 ←─────────────┤
      │                              │
      ↓                              │
[01f] 記憶生成ユースケース履歴対応   │
      │                              │
      ↓                              │
[01g] テンプレート更新 ←─────────────┘
      │
      ↓
[01h] 統合テスト
```

---

## 前提条件

### Phase 4 完了

Phase 4 で以下が実装済みであること：

- Memory エンティティ（scope, scope_id, memory_type で一意）
- MemoryRepository（save, find_by_scope_and_type）
- GenerateMemoryUseCase（記憶生成ユースケース）
- BackgroundMemoryGenerator（バックグラウンド記憶生成）
- Context エンティティ（workspace_short_term_memory, channel_memories）
- Jinja2 テンプレート（response_query.j2, memory_query.j2）

---

## 決定事項

| 項目 | 決定 |
|------|------|
| 更新トリガー | OR条件（2時間静止 OR 50件メッセージ） |
| 長期記憶統合タイミング | 短期記憶保存直後に即座に更新 |
| スレッド履歴化 | しない（上書きのまま） |
| 既存データマイグレーション | version=1 として扱う |
| WS短期記憶既存データ | DBに残すが参照しない |
| 古い履歴削除 | 削除しない（別ツールで対応） |
| 表示順序 | 古い順（時系列：v1→v2→v3→v4→v5） |
| 複数CH構造 | チャンネルごとにグループ化 |
| プロンプト配置 | 長期記憶 → 短期記憶履歴 → 会話履歴 |
| 長期記憶統合方法 | 既存長期記憶 + 新短期記憶をLLMで統合 |
| 長期記憶更新対象 | チャンネル・WS両方（現状維持） |

---

## 影響を受けるファイル

### 新規作成

| ファイル | 説明 |
|---------|------|
| `tests/integration/test_memory_history.py` | 統合テスト（新規） |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/entities/memory.py` | version フィールド追加 |
| `src/myao2/domain/entities/context.py` | workspace_short_term_memory 参照削除 |
| `src/myao2/domain/entities/channel_messages.py` | short_term_memory_history 追加 |
| `src/myao2/domain/repositories/memory_repository.py` | 履歴取得メソッド追加 |
| `src/myao2/infrastructure/persistence/models.py` | version カラム追加 |
| `src/myao2/infrastructure/persistence/memory_repository.py` | 履歴メソッド実装 |
| `src/myao2/config/models.py` | ShortTermHistoryConfig 追加 |
| `src/myao2/config/loader.py` | 新設定項目の読み込み |
| `src/myao2/application/use_cases/generate_memory.py` | 履歴生成ロジック |
| `src/myao2/application/use_cases/helpers.py` | Context 構築変更 |
| `src/myao2/infrastructure/llm/templates/response_query.j2` | 履歴表示 |
| `src/myao2/infrastructure/llm/templates/memory_query.j2` | 履歴表示 |
| `config.yaml.example` | 新設定項目 |

---

## Phase 5 完了の検証方法

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

3. 2時間経過後、または50件超過後に短期記憶が新バージョンとして保存されることを確認

4. データベースで履歴を確認：

```bash
sqlite3 ./data/memory.db "SELECT scope, scope_id, memory_type, version, updated_at FROM memories WHERE memory_type='short_term' ORDER BY scope_id, version;"
```

5. ボットが応答する際、短期記憶履歴を考慮した応答になっていることを確認

6. ログで記憶生成・長期記憶統合が出力されていることを確認
