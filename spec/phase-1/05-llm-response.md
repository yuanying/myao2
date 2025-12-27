# 05: LLM応答

## 目的

LiteLLM を使った応答生成を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/client.py` | LiteLLM ラッパー |
| `src/myao2/infrastructure/llm/response_generator.py` | ResponseGenerator 実装 |
| `tests/infrastructure/llm/test_client.py` | LLMクライアントのテスト |
| `tests/infrastructure/llm/test_response_generator.py` | 応答生成のテスト |

---

## LiteLLM の使用

### 基本的な使い方

LiteLLM は OpenAI API 互換のインターフェースで複数のLLMプロバイダーを抽象化する。

```python
from litellm import completion

response = completion(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ],
    temperature=0.7,
    max_tokens=1000
)
```

### 設定の適用

`config.yaml` の `llm.default` セクションがそのまま `completion()` に渡される。

---

## インターフェース設計

### `src/myao2/infrastructure/llm/client.py`

#### LLMClient

```
class LLMClient:
    """LiteLLM ラッパー"""

    def __init__(self, config: LLMConfig) -> None:
        """
        Args:
            config: LLM設定（model, temperature, max_tokens等）
        """
        ...

    def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any
    ) -> str:
        """チャット補完を実行する

        Args:
            messages: OpenAI形式のメッセージリスト
                [{"role": "system", "content": "..."}, ...]
            **kwargs: 追加パラメータ（設定を上書き）

        Returns:
            生成されたテキスト

        Raises:
            LLMError: API呼び出しエラー
        """
        ...
```

#### 例外クラス

```
class LLMError(Exception):
    """LLM関連のエラー"""

class LLMRateLimitError(LLMError):
    """レート制限エラー"""

class LLMAuthenticationError(LLMError):
    """認証エラー"""
```

### `src/myao2/infrastructure/llm/response_generator.py`

#### LiteLLMResponseGenerator

```
class LiteLLMResponseGenerator:
    """LiteLLMを使った ResponseGenerator 実装"""

    def __init__(self, client: LLMClient) -> None:
        """
        Args:
            client: LLMClient インスタンス
        """
        ...

    def generate(
        self,
        user_message: str,
        system_prompt: str
    ) -> str:
        """応答を生成する

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト（ペルソナ設定等）

        Returns:
            生成された応答テキスト

        Raises:
            LLMError: 応答生成に失敗
        """
        ...
```

---

## メッセージ形式

### 基本的な構造

```python
messages = [
    {
        "role": "system",
        "content": persona.system_prompt
    },
    {
        "role": "user",
        "content": user_message
    }
]
```

### Phase 1 での制限

- 会話履歴は含めない（単発の応答）
- コンテキストは Phase 2 以降で追加

---

## テストケース

### test_client.py

#### LLMClient

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常な補完 | 有効なメッセージ | 応答テキストが返る |
| 設定の適用 | temperature=0.5 | パラメータが反映される |
| kwargsによる上書き | max_tokens=500 | 設定が上書きされる |
| 認証エラー | 無効なAPIキー | LLMAuthenticationError |
| レート制限 | 429エラー | LLMRateLimitError |

### test_response_generator.py

#### LiteLLMResponseGenerator

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 基本的な生成 | user_message + system_prompt | 応答が生成される |
| システムプロンプトの適用 | ペルソナ設定 | プロンプトがmessagesに含まれる |
| 空のメッセージ | user_message="" | 応答が生成される（または適切なエラー） |
| LLMエラーの伝播 | client がエラー | LLMError が伝播 |

---

## テストでのモック

### LiteLLMのモック

```python
@pytest.fixture
def mock_completion(mocker):
    return mocker.patch("litellm.completion")

def test_complete_success(mock_completion, llm_client):
    mock_completion.return_value = MockResponse(
        choices=[MockChoice(message=MockMessage(content="Hello!"))]
    )

    result = llm_client.complete([{"role": "user", "content": "Hi"}])

    assert result == "Hello!"
```

### 統合テスト用の設定

- 環境変数 `TEST_WITH_REAL_LLM=true` で実際のAPIを使用
- デフォルトはモックを使用（API課金なし）

---

## 設計上の考慮事項

### エラーハンドリング

- LiteLLM の例外をキャッチしてドメイン例外に変換
- レート制限時のリトライは Phase 1 では実装しない

### ログ記録

- APIリクエスト/レスポンスをデバッグログに記録
- 本番環境ではプロンプト内容を記録しない（プライバシー考慮）

### 環境変数

- LLM APIキーは環境変数で設定（`OPENAI_API_KEY` 等）
- LiteLLM が自動的に読み取る

---

## 完了基準

- [ ] LLMClient が LiteLLM を正しく呼び出せる
- [ ] 設定ファイルのパラメータが適用される
- [ ] LiteLLMResponseGenerator が応答を生成できる
- [ ] システムプロンプト（ペルソナ）が適用される
- [ ] エラーが適切な例外クラスで伝播する
- [ ] 全テストケースが通過する（モック使用）
