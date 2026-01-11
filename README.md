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

## Docker

### イメージのビルド

ローカルでビルドする場合:

```bash
docker build -t myao2:latest .
```

### ローカルでの実行

```bash
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/data:/app/data \
  -e SLACK_BOT_TOKEN=xoxb-xxx \
  -e SLACK_APP_TOKEN=xapp-xxx \
  -e OPENAI_API_KEY=sk-xxx \
  myao2:latest
```

## Kubernetes デプロイ

### 前提条件

- Kubernetes クラスタへのアクセス
- kubectl のインストールと設定

### Secret の作成

必須の環境変数を含む Secret を作成します（キー名がそのまま環境変数名になります）:

```bash
kubectl create namespace myao2
kubectl -n myao2 create secret generic myao2-secrets \
  --from-literal=SLACK_BOT_TOKEN=xoxb-xxx \
  --from-literal=SLACK_APP_TOKEN=xapp-xxx \
  --from-literal=OPENAI_API_KEY=sk-xxx
```

オプショナルな環境変数を追加する場合:

```bash
kubectl -n myao2 patch secret myao2-secrets --patch '{"stringData": {
  "TAVILY_API_KEY": "tvly-xxx",
  "ANTHROPIC_API_KEY": "sk-ant-xxx",
  "AZURE_API_KEY": "xxx",
  "AZURE_API_BASE": "https://your-resource.openai.azure.com/",
  "AZURE_API_VERSION": "2023-05-15"
}}'
```

**環境変数一覧:**

| 環境変数 (= Secret Key) | 必須 | 説明 |
|-------------------------|------|------|
| `SLACK_BOT_TOKEN` | Yes | Slack Bot Token |
| `SLACK_APP_TOKEN` | Yes | Slack App Token |
| `OPENAI_API_KEY` | Yes | OpenAI API Key |
| `TAVILY_API_KEY` | No | Tavily Web検索 API Key |
| `WEB_FETCH_API_ENDPOINT` | No | Web取得 API エンドポイント |
| `ANTHROPIC_API_KEY` | No | Anthropic API Key |
| `AZURE_API_KEY` | No | Azure OpenAI API Key |
| `AZURE_API_BASE` | No | Azure OpenAI エンドポイント |
| `AZURE_API_VERSION` | No | Azure OpenAI APIバージョン |

### デプロイ

このリポジトリのマニフェストを直接参照してデプロイできます:

```bash
kubectl kustomize https://github.com/yuanying/myao2//manifests/overlays/production?ref=main | kubectl apply -f -
```

### ConfigMap のカスタマイズ

独自の config.yaml を使用する場合は、kustomization.yaml を作成して上書きします:

```yaml
# my-deployment/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - https://github.com/yuanying/myao2//manifests/overlays/production?ref=main

configMapGenerator:
  - name: myao2-config
    behavior: replace
    files:
      - config.yaml
```

```bash
# デプロイ
kubectl kustomize my-deployment | kubectl apply -f -
```

### ログ確認

```bash
kubectl -n myao2 logs -f deployment/myao2
```

## ライセンス

MIT
