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
├── domain/          # ドメイン層（エンティティ、値オブジェクト、リポジトリIF）
├── application/     # アプリケーション層（ユースケース）
├── infrastructure/  # インフラ層（リポジトリ実装、外部サービス）
│   ├── slack/       # Slack連携
│   ├── llm/         # LLM連携
│   └── persistence/ # SQLite永続化
├── presentation/    # プレゼンテーション層（Slackイベントハンドラ）
└── config/          # 設定管理
```

### レイヤー間の依存関係

- domain は他のレイヤーに依存しない
- application は domain にのみ依存
- infrastructure は domain, application に依存
- presentation は application に依存

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
- `.env` - 環境変数（機密情報）

環境変数は `${VAR_NAME}` 形式で config.yaml から参照可能

## 重要な注意事項

- ドメイン層はSlackに依存しない設計とする（将来のマルチプラットフォーム対応のため）
- LLM設定はLiteLLMのcompletion関数に渡すdict形式で定義
- 機密情報（トークン等）は必ず環境変数経由で注入
