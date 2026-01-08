# 03: Web Fetch ツール - 詳細設計書

**Status**: Done

## 概要

外部 Web ページをスクレイピングするための strands-agents ツールを実装する。
指定された Web API エンドポイントを使用して URL の内容を Markdown 形式で取得する。

---

## 決定事項サマリー

| 項目 | 決定内容 | 備考 |
|------|---------|------|
| 使用タイミング | 応答生成時のみ | response_generator に統合 |
| 認証 | なし | |
| パターン | memo_tools.py と同様の Factory パターン | |
| 設定構造 | `tools.web_fetch` セクションとして配置 | |
| エラー処理 | シンプルなメッセージ返却 | 「ページを取得できませんでした」等 |
| タイムアウト | 設定可能（デフォルト60秒） | `timeout_seconds` |
| ガイドライン | プロンプトに含めない | docstring のみで判断 |
| URL検証 | 基本的な検証のみ | http/https で始まるかチェック |
| コンテンツ制限 | 設定可能（デフォルト20000文字） | `max_content_length` |
| ログ | INFOレベルで記録 | URL と成功/失敗を記録 |
| docstring | 簡潔な説明 | |
| tools セクション省略時 | デフォルト設定を使用 | 全ツール有効 |
| HTTPクライアント | 都度作成 | シンプルで安全 |
| enabled=false時 | ツールを登録しない | LLM がツールを認識しない |

---

## 設定構造

```yaml
# config.yaml
tools:
  web_fetch:
    enabled: true
    api_endpoint: ${WEB_FETCH_API_ENDPOINT}
    timeout_seconds: 60
    max_content_length: 20000
```

---

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/strands/web_fetch_tools.py` | web_fetch ツール |
| `tests/infrastructure/llm/strands/test_web_fetch_tools.py` | テスト |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `spec/phase-5/README.md` | 機能一覧に 03 を追加 |
| `src/myao2/config/models.py` | `WebFetchConfig`, `ToolsConfig` dataclass 追加 |
| `src/myao2/config/loader.py` | `ToolsConfig` 読み込み追加 |
| `config.yaml.example` | `tools.web_fetch` セクション追加（既存の `external` セクションを置換）|
| `src/myao2/infrastructure/llm/strands/__init__.py` | web_fetch_tools エクスポート追加 |
| `src/myao2/infrastructure/llm/strands/response_generator.py` | WebFetchToolsFactory 統合 |
| `src/myao2/__main__.py` | WebFetchToolsFactory 初期化 |

---

## 実装方針

### ToolContext によるリポジトリアクセス

strands-agents の `@tool(context=True)` を使用し、`ToolContext.invocation_state` から設定にアクセスする。

```python
from strands import tool
from strands.types.tools import ToolContext

WEB_FETCH_CONFIG_KEY = "web_fetch_config"

def get_web_fetch_config(tool_context: ToolContext) -> WebFetchConfig:
    """ToolContext から WebFetchConfig を取得"""
    config = tool_context.invocation_state.get(WEB_FETCH_CONFIG_KEY)
    if config is None:
        raise RuntimeError("WebFetchConfig not found in invocation_state")
    return config
```

### WebFetchToolsFactory

設定の注入と invocation_state の構築を担当。

```python
class WebFetchToolsFactory:
    """Web Fetch ツールのファクトリ"""

    def __init__(self, config: WebFetchConfig) -> None:
        self._config = config

    def get_invocation_state(self) -> dict:
        """invocation_state を取得"""
        return {WEB_FETCH_CONFIG_KEY: self._config}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得"""
        return WEB_FETCH_TOOLS
```

---

## ツール仕様

### web_fetch

```python
@tool(context=True)
async def web_fetch(url: str, tool_context: ToolContext) -> str:
    """Webページの内容を取得する。

    Args:
        url: 取得するWebページのURL

    Returns:
        ページ内容（Markdown形式）またはエラーメッセージ
    """
```

**処理フロー:**
1. URL 検証（http/https で始まるか）
2. API リクエスト送信
3. レスポンス処理（success チェック）
4. コンテンツ長制限の適用
5. 結果返却

**API リクエスト:**
```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{config.api_endpoint}/md",
        json={"url": url, "f": "llm", "q": None, "c": "0"},
        timeout=config.timeout_seconds,
    )
```

**API レスポンス:**
```json
{
  "url": "https://example.com",
  "filter": "llm",
  "query": null,
  "cache": "0",
  "markdown": "CONTENTS",
  "success": true
}
```

---

## エラーハンドリング

| エラー種別 | 返却メッセージ |
|-----------|---------------|
| 不正なURL | 「無効なURLです。http:// または https:// で始まるURLを指定してください」 |
| タイムアウト | 「ページの取得がタイムアウトしました」 |
| HTTPエラー | 「ページを取得できませんでした」 |
| API失敗（success=false） | 「ページを取得できませんでした」 |

---

## テスト項目

### TestWebFetch

- 正常な取得
- コンテンツ長制限の適用
- 不正なURL（http/https以外）
- タイムアウト
- HTTPエラー
- API失敗（success=false）

### TestWebFetchToolsFactory

- invocation_state の構築
- tools プロパティ

### TestWebFetchConfig

- デフォルト値
- カスタム値

---

## 手動検証

1. アプリケーション起動
2. Slack でボットに URL を含むメッセージを送信（例: 「https://example.com の内容を教えて」）
3. ボットが web_fetch ツールを使用してページ内容を取得することを確認
4. ログで INFO レベルの記録を確認
