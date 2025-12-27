# myao2

Slack上で友達のように振る舞うチャットボット

## 概要

myao2は、Slackワークスペースで誰も反応しないメッセージに対して、友達のように自然に反応するチャットボットです。

## 特徴

- **人間のシミュレーション**: 即座に反応するのではなく、適切なタイミングで自然な応答
- **友達のような存在**: ボットではなく、ワークスペースの一員として振る舞う
- **コンテキスト理解**: ワークスペース、チャンネル、スレッド全体のコンテキストを考慮

## 必要条件

- Python 3.12+
- uv (パッケージマネージャー)

## セットアップ

```bash
# 依存関係のインストール
uv sync

# 設定ファイルの準備
cp config.yaml.example config.yaml
cp .env.example .env
# .env と config.yaml を編集して必要な設定を行う
```

## 開発

```bash
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
└── presentation/    # プレゼンテーション層（Slackイベントハンドラ）
```

## ライセンス

MIT
