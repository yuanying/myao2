# 04: コンテキスト付き応答生成

## 目的

Context ドメインモデルを使用した応答生成を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/protocols.py` | ResponseGenerator 変更（修正） |
| `src/myao2/infrastructure/llm/response_generator.py` | Context 対応（修正） |
| `tests/infrastructure/llm/test_response_generator.py` | テスト修正（修正） |

---

## 依存関係

- タスク 03a（Context ドメインモデル）の完了が前提

---

## インターフェース設計

### `src/myao2/domain/services/protocols.py`（修正）

#### ResponseGenerator Protocol 変更

```
class ResponseGenerator(Protocol):
    """応答生成抽象

    LLM やその他のメカニズムを使って応答を生成する。
    """

    def generate(
        self,
        user_message: Message,
        context: Context,
    ) -> str:
        """応答を生成する

        Args:
            user_message: ユーザーからのメッセージ
            context: 会話コンテキスト（履歴、ペルソナ情報を含む）

        Returns:
            生成された応答テキスト
        """
        ...
```

### `src/myao2/infrastructure/llm/response_generator.py`（修正）

#### LiteLLMResponseGenerator 修正

```
class LiteLLMResponseGenerator:
    """LiteLLM を使った ResponseGenerator 実装

    Context を使用してコンテキスト付き応答を生成する。
    """

    def __init__(self, client: LLMClient) -> None:
        """初期化

        Args:
            client: LLMClient インスタンス
        """

    def generate(
        self,
        user_message: Message,
        context: Context,
    ) -> str:
        """応答を生成する

        Context から LLM 形式のメッセージリストを構築し、
        LLM に渡して応答を生成する。

        Args:
            user_message: ユーザーからのメッセージ
            context: 会話コンテキスト

        Returns:
            生成された応答テキスト

        Raises:
            LLMError: 応答生成に失敗した場合
        """
```

---

## 実装の詳細

### generate メソッド

```python
def generate(
    self,
    user_message: Message,
    context: Context,
) -> str:
    # Context からメッセージリストを構築
    messages = context.build_messages_for_llm(user_message)

    # LLM に渡して応答を取得
    return self._client.complete(messages)
```

---

## テストケース

### test_response_generator.py（修正）

#### 基本動作

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | 有効な Context | 応答が返る |
| 履歴なし | 空の conversation_history | 正常に動作 |
| 履歴あり | 3件の履歴 | Context が正しく使用される |

#### Context 連携

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| メッセージ構築 | Context.build_messages_for_llm | 正しく呼ばれる |
| client 呼び出し | 構築されたメッセージ | client.complete に渡される |

---

## テストフィクスチャ

### モック LLMClient

```python
@pytest.fixture
def mock_client():
    """モック LLMClient"""
    client = Mock(spec=LLMClient)
    client.complete.return_value = "Generated response"
    return client


@pytest.fixture
def generator(mock_client):
    """テスト用ジェネレータ"""
    return LiteLLMResponseGenerator(mock_client)


@pytest.fixture
def persona_config() -> PersonaConfig:
    """テスト用ペルソナ設定"""
    return PersonaConfig(
        name="myao",
        system_prompt="あなたは友達のように振る舞うチャットボットです。",
    )


@pytest.fixture
def sample_context(persona_config) -> Context:
    """テスト用コンテキスト"""
    return Context(
        persona=persona_config,
        conversation_history=[],
    )
```

---

## 設計上の考慮事項

### シンプルな責務分離

- ResponseGenerator はメッセージ構築を Context に委譲
- Context がメッセージ形式の変換を担当
- ResponseGenerator は LLM 呼び出しのみに集中

### 拡張性

- Phase 3 以降で Context に長期・短期記憶が追加されても
- ResponseGenerator の変更は不要
- Context.build_messages_for_llm の実装のみ変更

### 型安全性

- Message と Context の型を使用することで型チェックが効く
- 文字列ベースの引数よりも安全

---

## 完了基準

- [x] ResponseGenerator Protocol が新しいインターフェースに変更されている
- [x] LiteLLMResponseGenerator が Context を受け取る
- [x] Context.build_messages_for_llm が正しく使用される
- [x] 全テストケースが通過する
