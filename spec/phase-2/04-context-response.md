# 04: コンテキスト付き応答生成

## 目的

会話履歴を考慮した応答生成を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/protocols.py` | ResponseGenerator 拡張（修正） |
| `src/myao2/infrastructure/llm/response_generator.py` | 履歴対応（修正） |
| `tests/infrastructure/llm/test_response_generator.py` | テスト追加（修正） |

---

## インターフェース設計

### `src/myao2/domain/services/protocols.py`（修正）

#### ResponseGenerator Protocol 拡張

```
class ResponseGenerator(Protocol):
    """応答生成抽象

    LLM やその他のメカニズムを使って応答を生成する。
    """

    def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[Message] | None = None,  # 追加
    ) -> str:
        """応答を生成する

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト
            conversation_history: 会話履歴（オプション）

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

    会話履歴を含めた応答生成をサポートする。
    """

    def __init__(self, client: LLMClient) -> None:
        """初期化

        Args:
            client: LLMClient インスタンス
        """

    def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[Message] | None = None,
    ) -> str:
        """応答を生成する

        会話履歴がある場合は、LLM のメッセージリストに含める。

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト
            conversation_history: 会話履歴（オプション）

        Returns:
            生成された応答テキスト

        Raises:
            LLMError: 応答生成に失敗した場合
        """

    def _build_messages(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[Message] | None,
    ) -> list[dict[str, str]]:
        """LLM に渡すメッセージリストを構築する

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト
            conversation_history: 会話履歴

        Returns:
            OpenAI 形式のメッセージリスト
        """
```

---

## 実装の詳細

### メッセージ構築ロジック

```python
def _build_messages(
    self,
    user_message: str,
    system_prompt: str,
    conversation_history: list[Message] | None,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]

    # 会話履歴を追加（古い順で渡される前提）
    if conversation_history:
        for msg in conversation_history:
            # ボットのメッセージは assistant、それ以外は user
            role = "assistant" if msg.user.is_bot else "user"
            messages.append({
                "role": role,
                "content": msg.text,
            })

    # 現在のユーザーメッセージを追加
    messages.append({"role": "user", "content": user_message})

    return messages
```

### generate メソッド

```python
def generate(
    self,
    user_message: str,
    system_prompt: str,
    conversation_history: list[Message] | None = None,
) -> str:
    messages = self._build_messages(
        user_message,
        system_prompt,
        conversation_history,
    )
    return self._client.complete(messages)
```

### LLM メッセージ形式の例

会話履歴がある場合：

```python
messages = [
    {"role": "system", "content": "あなたは友達のように振る舞うチャットボットです。"},
    # 会話履歴（古い順）
    {"role": "user", "content": "こんにちは！"},
    {"role": "assistant", "content": "こんにちは！何かお手伝いできることはありますか？"},
    {"role": "user", "content": "今日の調子はどう？"},
    {"role": "assistant", "content": "元気ですよ！ありがとう。"},
    # 現在のメッセージ
    {"role": "user", "content": "@myao 何か面白い話ある？"},
]
```

会話履歴がない場合（Phase 1 互換）：

```python
messages = [
    {"role": "system", "content": "あなたは友達のように振る舞うチャットボットです。"},
    {"role": "user", "content": "@myao こんにちは"},
]
```

---

## テストケース

### test_response_generator.py（追加）

#### 履歴なし（後方互換性）

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | conversation_history=None | 従来通り動作 |
| 空履歴 | conversation_history=[] | 従来通り動作 |

#### 履歴あり

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 単一履歴 | 1件の履歴 | messages に履歴が含まれる |
| 複数履歴 | 3件の履歴 | 古い順で messages に追加 |

#### ロール判定

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| ユーザーメッセージ | is_bot=False | role="user" |
| ボットメッセージ | is_bot=True | role="assistant" |
| 混在 | ユーザーとボット | 正しく role が設定される |

#### _build_messages

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 順序確認 | system → 履歴 → user | 正しい順序 |
| system 常に先頭 | 履歴あり/なし | system が最初 |
| user 常に末尾 | 履歴あり/なし | 現在のメッセージが最後 |

---

## テストフィクスチャ

### テスト用メッセージ生成

```python
def create_history_message(
    text: str,
    is_bot: bool = False,
    user_name: str = "testuser",
) -> Message:
    """会話履歴用のテストメッセージを生成"""
    return Message(
        id="1234567890.123456",
        channel=Channel(id="C123", name="general"),
        user=User(
            id="U123" if not is_bot else "B123",
            name=user_name if not is_bot else "myao",
            is_bot=is_bot,
        ),
        text=text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=None,
        mentions=[],
    )
```

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
```

---

## 設計上の考慮事項

### 後方互換性

- `conversation_history` はオプショナル引数（デフォルト: None）
- 既存の呼び出しはそのまま動作
- テストも既存のものは変更不要

### ロール判定のシンプルさ

- `is_bot` のみで判定（シンプル）
- 将来的にはユーザー種別（human, bot, system）を追加可能

### メッセージ順序

- 会話履歴は古い順で渡される前提
- 呼び出し元（ユースケース）が順序を保証

### メンションの扱い

- メッセージテキストにはメンション（`<@U123>`）がそのまま含まれる
- LLM がメンションを理解できるよう、Phase 2 では特別な処理はしない
- 将来的にはメンションを名前に変換する処理を追加可能

---

## 完了基準

- [ ] ResponseGenerator Protocol に conversation_history が追加されている
- [ ] LiteLLMResponseGenerator が履歴を扱える
- [ ] 履歴なしでも従来通り動作する（後方互換性）
- [ ] ボットメッセージは role="assistant" で設定される
- [ ] メッセージ順序が正しい（system → 履歴 → user）
- [ ] 全テストケースが通過する
