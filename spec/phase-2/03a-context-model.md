# 03a: Context ドメインモデル

## 目的

会話コンテキストを表現するドメインモデル `Context` を定義する。
Context は過去の会話履歴、および将来実装される長期・短期記憶を保持し、
それらの情報からシステムプロンプトを生成する責務を持つ。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/context.py` | Context エンティティ |
| `src/myao2/domain/entities/__init__.py` | エクスポート追加（修正） |
| `tests/domain/entities/test_context.py` | Context のテスト |

---

## 依存関係

- タスク 01（SQLite永続化基盤）の Message エンティティを使用

---

## インターフェース設計

### `src/myao2/domain/entities/context.py`

#### Context エンティティ

```
@dataclass(frozen=True)
class Context:
    """会話コンテキスト

    会話履歴と将来の長期・短期記憶を保持し、
    LLM に渡すためのシステムプロンプトを生成する。
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    # Phase 3 以降で追加予定
    # long_term_memory: str | None = None
    # short_term_memory: str | None = None

    def build_system_prompt(self) -> str:
        """システムプロンプトを構築する

        ペルソナのベースプロンプトに、必要に応じて
        記憶情報を追加したプロンプトを生成する。

        Returns:
            システムプロンプト文字列
        """

    def build_messages_for_llm(
        self,
        user_message: Message,
    ) -> list[dict[str, str]]:
        """LLM に渡すメッセージリストを構築する

        Args:
            user_message: 現在のユーザーメッセージ

        Returns:
            OpenAI 形式のメッセージリスト
            [{"role": "system", "content": ...}, ...]
        """
```

---

## 実装の詳細

### build_system_prompt メソッド

Phase 2 では単純にペルソナのシステムプロンプトをそのまま返す。
Phase 3 以降で長期・短期記憶を追加するための拡張ポイントとなる。

```python
def build_system_prompt(self) -> str:
    # Phase 2: シンプルにペルソナのプロンプトを返す
    return self.persona.system_prompt

    # Phase 3 以降の拡張イメージ:
    # parts = [self.persona.system_prompt]
    # if self.long_term_memory:
    #     parts.append(f"\n\n## 長期記憶\n{self.long_term_memory}")
    # if self.short_term_memory:
    #     parts.append(f"\n\n## 短期記憶\n{self.short_term_memory}")
    # return "\n".join(parts)
```

### build_messages_for_llm メソッド

会話履歴と現在のメッセージを LLM 形式に変換する。

```python
def build_messages_for_llm(
    self,
    user_message: Message,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": self.build_system_prompt()}]

    # 会話履歴を追加（古い順で渡される前提）
    for msg in self.conversation_history:
        role = "assistant" if msg.user.is_bot else "user"
        messages.append({
            "role": role,
            "content": msg.text,
        })

    # 現在のユーザーメッセージを追加
    messages.append({
        "role": "user",
        "content": user_message.text,
    })

    return messages
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

会話履歴がない場合：

```python
messages = [
    {"role": "system", "content": "あなたは友達のように振る舞うチャットボットです。"},
    {"role": "user", "content": "@myao こんにちは"},
]
```

---

## テストケース

### test_context.py

#### build_system_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 基本動作 | persona あり | persona.system_prompt が返る |

#### build_messages_for_llm

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 履歴なし | conversation_history=[] | system + user のみ |
| 履歴1件 | 1件の履歴 | system + 履歴 + user |
| 履歴複数 | 3件の履歴 | 古い順で追加される |
| ロール判定 | ユーザーとボット混在 | 正しく role が設定される |
| 順序確認 | system → 履歴 → user | 正しい順序 |

---

## テストフィクスチャ

### テスト用データ

```python
@pytest.fixture
def persona_config() -> PersonaConfig:
    """テスト用ペルソナ設定"""
    return PersonaConfig(
        name="myao",
        system_prompt="あなたは友達のように振る舞うチャットボットです。",
    )


@pytest.fixture
def sample_user() -> User:
    """テスト用ユーザー"""
    return User(id="U123", name="testuser", is_bot=False)


@pytest.fixture
def sample_bot() -> User:
    """テスト用ボット"""
    return User(id="B123", name="myao", is_bot=True)


def create_test_message(
    text: str,
    user: User,
    channel_id: str = "C123",
) -> Message:
    """テスト用メッセージを生成"""
    return Message(
        id="1234567890.123456",
        channel=Channel(id=channel_id, name="general"),
        user=user,
        text=text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=None,
        mentions=[],
    )
```

---

## 設計上の考慮事項

### 単一責任の原則

- Context はコンテキスト情報の保持と、それを基にした LLM 形式への変換のみを担当
- 履歴の取得（Slack API 呼び出し、DB 検索）は別のサービスの責務

### 不変性

- Context は `frozen=True` の dataclass
- 状態変更が必要な場合は新しいインスタンスを生成

### 拡張性

- Phase 3 以降の長期・短期記憶追加を想定した設計
- `build_system_prompt` で記憶情報をプロンプトに統合予定

### ドメイン層の独立性

- Context は Slack に依存しない純粋なドメインモデル
- PersonaConfig、Message など既存のドメインオブジェクトのみに依存

---

## 完了基準

- [x] Context エンティティが定義されている
- [x] build_system_prompt でペルソナのプロンプトが返される
- [x] build_messages_for_llm で正しい形式のメッセージリストが生成される
- [x] 会話履歴が古い順で含まれる
- [x] ボットメッセージは role="assistant" で設定される
- [x] 全テストケースが通過する
