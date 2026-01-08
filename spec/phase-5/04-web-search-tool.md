# 04: Web Search ツール - 詳細設計書

**Status**: Done

## 概要

Tavily API を使用したウェブ検索機能を strands-agents ツールとして実装する。

---

## 決定事項サマリー

| 項目 | 決定内容 | 備考 |
|------|---------|------|
| 使用タイミング | 応答生成時のみ | response_generator に統合 |
| クライアント | AsyncTavilyClient | 非同期でイベントループをブロックしない |
| パターン | web_fetch_tools.py と同様の Factory パターン | |
| 設定構造 | `tools.web_search` セクションとして配置 | |
| search_depth | basic（デフォルト） | 設定可能 |
| max_results | 5件（デフォルト） | 設定可能 |
| include_answer | 有効 | Tavily が要約を生成 |
| content制限 | 設定可能（デフォルト500文字） | `max_content_length` |
| raw_content | 使用しない | content のみ使用 |
| TavilyClient | 都度作成 | シンプルで安全 |
| エラー処理 | シンプルなメッセージ | 「検索できませんでした」等 |
| ログ | INFOレベル | クエリと成功/失敗を記録 |
| docstring | 簡潔な説明 | |
| APIキー未設定時 | 起動時に警告ログ | ツールは登録しない |
| 設定省略時 | ツール無効 | 明示的な有効化が必要 |

---

## 設定構造

```yaml
# config.yaml
tools:
  web_search:
    enabled: true
    api_key: ${TAVILY_API_KEY}
    search_depth: basic        # basic or advanced
    max_results: 5             # 検索結果の最大件数
    max_content_length: 500    # 各結果のcontent最大文字数（0で無制限）
```

---

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/strands/web_search_tools.py` | web_search ツール |
| `tests/infrastructure/llm/strands/test_web_search_tools.py` | テスト |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `spec/phase-5/README.md` | 機能一覧に 04 を追加 |
| `src/myao2/config/models.py` | `WebSearchConfig` dataclass 追加 |
| `src/myao2/config/loader.py` | `web_search` 読み込み追加 |
| `config.yaml.example` | `tools.web_search` セクション追加 |
| `src/myao2/infrastructure/llm/strands/__init__.py` | web_search_tools エクスポート追加 |
| `src/myao2/infrastructure/llm/strands/response_generator.py` | WebSearchToolsFactory 統合 |
| `src/myao2/__main__.py` | WebSearchToolsFactory 初期化 |

---

## 実装方針

### ToolContext によるリポジトリアクセス

strands-agents の `@tool(context=True)` を使用し、`ToolContext.invocation_state` から設定にアクセスする。

```python
from strands import tool
from strands.types.tools import ToolContext

WEB_SEARCH_CONFIG_KEY = "web_search_config"

def get_web_search_config(tool_context: ToolContext) -> WebSearchConfig:
    """ToolContext から WebSearchConfig を取得"""
    config = tool_context.invocation_state.get(WEB_SEARCH_CONFIG_KEY)
    if config is None:
        raise RuntimeError("WebSearchConfig not found in invocation_state")
    return config
```

### WebSearchToolsFactory

設定の注入と invocation_state の構築を担当。

```python
class WebSearchToolsFactory:
    """Web Search ツールのファクトリ"""

    def __init__(self, config: WebSearchConfig) -> None:
        self._config = config

    def get_invocation_state(self) -> dict:
        """invocation_state を取得"""
        return {WEB_SEARCH_CONFIG_KEY: self._config}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得"""
        return WEB_SEARCH_TOOLS
```

---

## ツール仕様

### web_search

```python
@tool(context=True)
async def web_search(query: str, tool_context: ToolContext) -> str:
    """ウェブ検索を実行する。

    Args:
        query: 検索クエリ
        tool_context: ツールコンテキスト

    Returns:
        検索結果（タイトル、URL、要約を含む）またはエラーメッセージ
    """
```

**処理フロー:**
1. クエリバリデーション（空文字チェック）
2. AsyncTavilyClient でウェブ検索実行
3. レスポンス処理（answer, results の整形）
4. コンテンツ長制限の適用（各結果の content）
5. 結果返却（Markdown形式）

**AsyncTavilyClient 呼び出し:**
```python
from tavily import AsyncTavilyClient

client = AsyncTavilyClient(api_key=config.api_key)
response = await client.search(
    query=query,
    search_depth=config.search_depth,
    max_results=config.max_results,
    include_answer=True,
)
```

**レスポンス構造:**
```json
{
  "query": "Python async programming",
  "answer": "Pythonの非同期プログラミングは...",
  "results": [
    {
      "title": "Python asyncio documentation",
      "url": "https://docs.python.org/3/library/asyncio.html",
      "content": "Pythonの公式asyncioドキュメント...",
      "score": 0.95
    }
  ]
}
```

**返却フォーマット:**
```markdown
## 検索結果: "Python async programming"

### 回答
Pythonの非同期プログラミングは...

### 結果
1. **Python asyncio documentation**
   URL: https://docs.python.org/3/library/asyncio.html
   Pythonの公式asyncioドキュメント...

2. **Real Python - Async IO in Python**
   URL: https://realpython.com/async-io-python/
   非同期プログラミングの詳細な解説...
```

---

## エラーハンドリング

| エラー種別 | 返却メッセージ |
|-----------|---------------|
| 空のクエリ | 「検索クエリを入力してください」 |
| APIエラー | 「検索できませんでした」 |
| 結果なし | 「検索結果が見つかりませんでした」 |

---

## テスト項目

### TestWebSearch

- 正常な検索
- 回答を含む検索結果
- コンテンツ長制限の適用
- 空のクエリ
- APIエラー
- 結果なし

### TestWebSearchToolsFactory

- invocation_state の構築
- tools プロパティ

### TestWebSearchConfig

- デフォルト値
- カスタム値

---

## 手動検証

1. アプリケーション起動
2. Slack でボットに検索を依頼（例: 「Pythonの非同期プログラミングについて検索して」）
3. ボットが web_search ツールを使用して検索結果を取得することを確認
4. ログで INFO レベルの記録を確認
