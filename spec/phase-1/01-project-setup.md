# 01: プロジェクトセットアップ

## 目的

開発環境を整備し、プロジェクトの骨格を作成する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `pyproject.toml` | プロジェクト設定・依存関係 |
| `src/myao2/__init__.py` | パッケージ初期化 |
| `src/myao2/__main__.py` | エントリポイント |
| 各層の `__init__.py` | サブパッケージ初期化 |
| `.github/workflows/ci.yml` | CI ワークフロー（lint + test） |

---

## pyproject.toml

### 依存関係

| パッケージ | 用途 |
|-----------|------|
| `slack-bolt` | Slack Bot フレームワーク |
| `litellm` | LLM API ラッパー |
| `pyyaml` | YAML パーサー |

### 開発依存関係

| パッケージ | 用途 |
|-----------|------|
| `pytest` | テストフレームワーク |
| `pytest-asyncio` | 非同期テストサポート |
| `ruff` | Linter / Formatter |
| `ty` | 型チェッカー |

### tool.ruff 設定

- `line-length`: 88
- `target-version`: "py312"
- `select`: ["E", "F", "I", "W"]（基本的なルール）

---

## ディレクトリ構造

```
myao2/
├── .github/
│   └── workflows/
│       └── ci.yml           # CI ワークフロー
├── pyproject.toml
├── config.yaml.example      # 設定ファイルサンプル
├── src/
│   └── myao2/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config/
│       │   └── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── entities/
│       │   │   └── __init__.py
│       │   └── services/
│       │       └── __init__.py
│       ├── application/
│       │   ├── __init__.py
│       │   └── use_cases/
│       │       └── __init__.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── slack/
│       │   │   └── __init__.py
│       │   └── llm/
│       │       └── __init__.py
│       └── presentation/
│           └── __init__.py
└── tests/
    ├── __init__.py
    └── conftest.py
```

---

## GitHub Actions（CI）

### `.github/workflows/ci.yml`

PR および main ブランチへのプッシュ時に自動実行される CI ワークフロー。

#### トリガー

- `push`: main ブランチ
- `pull_request`: main ブランチへのPR

#### ジョブ構成

| ジョブ | 内容 |
|-------|------|
| `lint` | ruff check, ruff format --check, ty check |
| `test` | pytest 実行 |

#### 使用するアクション

| アクション | 用途 |
|-----------|------|
| `actions/checkout@v4` | リポジトリのチェックアウト |
| `astral-sh/setup-uv@v4` | uv のセットアップ |

#### ワークフロー設計

```
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run ty check

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run pytest
```

---

## インターフェース設計

### `src/myao2/__init__.py`

```
"""myao2 - Slack上で友達のように振る舞うチャットボット"""

__version__ = "0.1.0"
```

### `src/myao2/__main__.py`

```
"""アプリケーションのエントリポイント"""

def main() -> None:
    """アプリケーションを起動する"""
    ...

if __name__ == "__main__":
    main()
```

- Phase 1 完了時には、設定読み込み→Slackアプリ起動の流れを実装
- 初期段階では空の `main()` 関数でOK

---

## テストケース

### 環境構築の検証

| テスト | 期待結果 |
|--------|---------|
| `uv sync` | 依存関係がエラーなくインストールされる |
| `uv run ruff check .` | エラーが0件 |
| `uv run ruff format --check .` | フォーマット差分が0件 |
| `uv run ty check` | 型エラーが0件 |
| `uv run pytest` | テストが実行される（0件でもOK） |

### モジュールインポートの検証

| テスト | 期待結果 |
|--------|---------|
| `python -c "import myao2"` | エラーなくインポートできる |
| `python -c "from myao2 import __version__"` | バージョン文字列が取得できる |

---

## 完了基準

- [ ] `pyproject.toml` が作成され、`uv sync` が成功する
- [ ] すべての `__init__.py` が作成されている
- [ ] `uv run ruff check .` がエラー0件で通過
- [ ] `uv run ty check` がエラー0件で通過
- [ ] `uv run python -c "import myao2"` が成功する
- [ ] GitHub Actions の CI が正常に動作する（lint + test）
