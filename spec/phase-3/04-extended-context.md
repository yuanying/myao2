# 04: 拡張 Context（補助コンテキスト）

## 目的

応答対象以外のチャンネルメッセージを補助コンテキストとして
Context に含められるよう拡張する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/context.py` | auxiliary_context 追加（修正） |
| `tests/domain/entities/test_context.py` | テスト追加 |

---

## 背景

requirements.md 2.1.2 より：

> **コンテキスト構築の方針:**
> - 応答すべきスレッド、もしくはチャンネルのメッセージ一覧はLLMのmessagesで構築
> - それ以外のチャンネルのスレッドに属していないメッセージは、返答生成時の補助会話として別途コンテキストに含める

---

## インターフェース設計

### Context エンティティの拡張

```python
@dataclass(frozen=True)
class Context:
    """会話コンテキスト

    会話履歴と補助コンテキストを保持し、
    LLM に渡すためのシステムプロンプトを生成する。
    """

    persona: PersonaConfig
    conversation_history: list[Message] = field(default_factory=list)
    auxiliary_context: str | None = None  # 追加
    # Phase 4 以降で追加予定
    # long_term_memory: str | None = None
    # short_term_memory: str | None = None

    def build_system_prompt(self) -> str:
        """システムプロンプトを構築する"""
        ...

    def build_messages_for_llm(
        self,
        user_message: Message,
    ) -> list[dict[str, str]]:
        """LLM に渡すメッセージリストを構築する"""
        ...
```

---

## 補助コンテキストの構築

### 形式

補助コンテキストはシステムプロンプトに追加される文字列。
以下のような形式を想定：

```
## 最近のチャンネルでの会話

#general:
- user1: 今日は暑いですね
- user2: そうですね、30度超えてます

#random:
- user3: 週末どこか行く？
```

### build_system_prompt での統合

```python
def build_system_prompt(self) -> str:
    parts = [self.persona.system_prompt]

    if self.auxiliary_context:
        parts.append(f"\n\n## 参考情報\n{self.auxiliary_context}")

    # Phase 4 以降
    # if self.long_term_memory:
    #     parts.append(f"\n\n## 長期記憶\n{self.long_term_memory}")

    return "\n".join(parts)
```

---

## 補助コンテキストの用途

### 自律応答時

- 応答対象のスレッド/チャンネル以外のメッセージを含める
- ワークスペース全体の雰囲気を把握するため

### メンション応答時

- 必要に応じて他チャンネルの情報を含める（オプション）

---

## テストケース

### auxiliary_context

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| None の場合 | auxiliary_context 未設定 | ペルソナプロンプトのみ |
| 設定あり | auxiliary_context 設定 | プロンプトに追加される |

### build_system_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 補助コンテキストなし | auxiliary_context=None | persona.system_prompt のみ |
| 補助コンテキストあり | 文字列を設定 | 「## 参考情報」セクションが追加 |

---

## 設計上の考慮事項

### 不変性の維持

- Context は frozen dataclass のまま
- 補助コンテキストを追加する場合は新しいインスタンスを生成

### トークン数の管理

- 補助コンテキストが大きすぎると LLM の入力上限を超える可能性
- 必要に応じてサマリー化や件数制限を検討（Phase 4 以降）

### 既存機能への影響

- メンション応答（ReplyToMentionUseCase）は変更不要
- auxiliary_context=None のまま動作する

---

## 完了基準

- [x] Context に auxiliary_context フィールドが追加されている
- [x] build_system_prompt で補助コンテキストが統合される
- [x] auxiliary_context=None の場合は既存動作と同じ
- [x] 既存のテストが引き続き通過する
- [x] 全テストケースが通過する
