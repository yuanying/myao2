# 03: 応答判定サービス

## 目的

LLM を使って、メッセージに応答すべきかどうかを判定するサービスを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/response_judgment.py` | ResponseJudgment Protocol |
| `src/myao2/domain/entities/judgment_result.py` | JudgmentResult 値オブジェクト |
| `src/myao2/infrastructure/llm/response_judgment.py` | LLMResponseJudgment 実装 |
| `tests/domain/entities/test_judgment_result.py` | JudgmentResult テスト |
| `tests/infrastructure/llm/test_response_judgment.py` | LLMResponseJudgment テスト |

---

## 依存関係

- タスク 01（ResponseConfig）
- config.yaml の `llm.judgment` 設定

---

## インターフェース設計

### JudgmentResult 値オブジェクト

```python
@dataclass(frozen=True)
class JudgmentResult:
    """応答判定の結果

    Attributes:
        should_respond: 応答すべきかどうか
        reason: 判定理由（デバッグ/ログ用）
        confidence: 確信度（0.0 - 1.0、オプション）
    """

    should_respond: bool
    reason: str
    confidence: float = 1.0
```

### ResponseJudgment Protocol

```python
class ResponseJudgment(Protocol):
    """応答判定サービス

    会話コンテキストを分析し、ボットが応答すべきかを判定する。
    """

    async def judge(
        self,
        context: Context,
        message: Message,
    ) -> JudgmentResult:
        """応答すべきかを判定する

        Args:
            context: 会話コンテキスト（persona と conversation_history を含む）
            message: 判定対象のメッセージ

        Returns:
            判定結果
        """
        ...
```

---

## 判定基準

### 応答する場合（requirements.md より）

- メッセージが投稿されてからしばらく経過し、誰も返答がなくて困っている/寂しそうな時
- 数人の会話が続いているが、有用なアドバイスができそうな時
- 自分が反応したほうが良いと判断した場合は即座に応答

### 応答しない場合

- 明らかな独り言
- 数人の会話で熱中している場合（割り込むのは適切ではない）

---

## LLM プロンプト設計

### システムプロンプト（概要）

```
あなたは会話への参加判断を行うアシスタントです。
以下の会話を分析し、{persona.name}として応答すべきかを判断してください。

現在時刻: {current_time}

判断基準：
1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

以下の場合は応答しないでください：
- 明らかな独り言
- 活発な会話に無理に割り込む場合

回答形式：
{"should_respond": true/false, "reason": "理由"}
```

### 会話履歴のフォーマット

各メッセージは以下の形式で時刻付きで送信される：

```
会話履歴:
[2024-01-01 12:00:00] user_name: メッセージ内容
[2024-01-01 12:05:00] another_user: 返信内容

判定対象メッセージ:
[2024-01-01 12:30:00] target_user: このメッセージに応答すべきか判定してください
```

これにより LLM が経過時間を判断材料として使用でき、判定対象のメッセージが明確になる。

### レスポンスのパース

- JSON 形式で should_respond と reason を受け取る
- パース失敗時はデフォルトで should_respond=false

---

## LLM 設定

### config.yaml の llm.judgment

```yaml
llm:
  judgment:
    model: "gpt-4o-mini"
    temperature: 0.3
    max_tokens: 200
```

- 軽量なモデルを使用（コスト削減）
- temperature は低めに設定（安定した判定）

---

## テストケース

### JudgmentResult

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 生成 | should_respond=True | 正しく生成される |
| 生成 | should_respond=False | 正しく生成される |
| 不変性 | フィールド変更 | エラー（frozen） |

### LLMResponseJudgment

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 応答すべき | 未応答の質問 | should_respond=True |
| 応答不要 | 活発な会話 | should_respond=False |
| JSONパース成功 | 正しいJSON | 結果が返る |
| JSONパース失敗 | 不正なJSON | should_respond=False |
| LLMエラー | API エラー | should_respond=False |
| 時刻情報 | プロンプトに現在時刻が含まれる | 時刻が含まれる |
| メッセージ時刻 | 各メッセージに時刻が含まれる | 時刻が含まれる |

---

## 設計上の考慮事項

### コスト効率

- 判定用 LLM は軽量モデルを使用
- 不要な判定を避けるため、明らかに応答不要なケースは事前にフィルタ

### 判定の安定性

- temperature を低く設定
- 判定基準を明確にプロンプトに記載

### ログ出力

- 判定結果は reason とともにログ出力
- デバッグや調整に活用

---

## 完了基準

- [x] JudgmentResult が定義されている
- [x] ResponseJudgment Protocol が定義されている
- [x] LLMResponseJudgment が実装されている
- [x] llm.judgment 設定が使用されている
- [x] 判定理由がログ出力される
- [x] 全テストケースが通過する
