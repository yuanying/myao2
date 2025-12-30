# CLAUDE.md

## プロジェクト概要

myao2 - Slack上で友達のように振る舞うチャットボット

## 技術スタック

- **言語**: Python 3.12+
- **パッケージ管理**: uv
- **LLM**: LiteLLM
- **Linter**: ruff
- **型チェック**: ty
- **永続化**: SQLite
- **ORM**: SQLModel

## 開発コマンド

```bash
# 依存関係のインストール
uv sync

# Linter実行
uv run ruff check .
uv run ruff format .

# 型チェック
uv run ty check

# テスト実行
uv run pytest

# アプリケーション起動
uv run python -m myao2
```

## アーキテクチャ

クリーンアーキテクチャ / DDD / Dependency Injection を採用

```
src/myao2/
├── domain/              # ドメイン層
│   ├── entities/        # エンティティ
│   ├── repositories/    # リポジトリインターフェース（Protocol）
│   └── services/        # ドメインサービスインターフェース（Protocol）
├── application/         # アプリケーション層
│   ├── use_cases/       # ユースケース
│   └── services/        # アプリケーションサービス
├── infrastructure/      # インフラ層（リポジトリ実装、外部サービス）
│   ├── slack/           # Slack連携
│   ├── llm/             # LLM連携
│   └── persistence/     # SQLite永続化
├── presentation/        # プレゼンテーション層（Slackイベントハンドラ）
└── config/              # 設定管理
```

### レイヤー間の依存関係

- domain は他のレイヤーに依存しない
- application は domain にのみ依存
- infrastructure は domain, application に依存
- presentation は application に依存

## 設計ドキュメント

フェーズごとの詳細設計書が `spec/` ディレクトリに配置されている:

- `spec/phase-1/` - 基盤構築
- `spec/phase-2/` - コンテキスト管理
- `spec/phase-2.5/` - 非同期化
- `spec/phase-3/` - 自律的応答
- `spec/phase-4/` - 記憶システム

各フェーズの README.md に全体概要、個別の `.md` ファイルにタスクごとの詳細設計がある。

## コーディング規約

### 型ヒント
- すべての関数に型ヒントを付ける
- `Any` の使用は最小限に

### docstring
- 公開APIにはdocstringを記載
- Google styleを使用

### テスト
- TDDで開発を進める
- テストファイルは `tests/` ディレクトリに配置
- ファイル名は `test_*.py` 形式

### インポート
- 標準ライブラリ、サードパーティ、ローカルの順で記載
- ruffによる自動ソート

## 設定ファイル

- `config.yaml` - アプリケーション設定
- `config.yaml.example` - 設定テンプレート
- `.env` - 環境変数（機密情報）

**重要**: 設定項目を追加・変更した場合は、必ず `config.yaml.example` も同期して更新すること。

環境変数は `${VAR_NAME}` 形式で config.yaml から参照可能

## 重要な注意事項

- ドメイン層はSlackに依存しない設計とする（将来のマルチプラットフォーム対応のため）
- LLM設定はLiteLLMのcompletion関数に渡すdict形式で定義
- LLMへの入力は `system_prompt` のみを使用し、会話履歴・記憶・コンテキスト情報は全て system_prompt 内に組み込む
- 機密情報（トークン等）は必ず環境変数経由で注入
