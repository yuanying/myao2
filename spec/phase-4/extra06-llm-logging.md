# extra06: 全LLM呼び出しのログ出力統一

## 目的

全てのLLM呼び出し時にリクエスト内容とレスポンス内容をログ出力するようにする。
`config.logging.debug_llm_messages` フラグで統一的に制御する。

---

## 背景

### 現状

| コンポーネント | ログ出力状況 |
|--------------|------------|
| LLMClient | DEBUG: model名のみ |
| LiteLLMResponseGenerator | debug_llm_messages で全メッセージ出力 |
| LLMResponseJudgment | DEBUG: 結果のみ、リクエスト内容なし |
| LLMMemorySummarizer | ログ出力なし |

### 問題点

1. ログ出力が統一されていない
2. デバッグ時にリクエスト内容が確認できないコンポーネントがある
3. 問題発生時の原因特定が困難

### 解決方針

- LLMClient にログ出力を集約
- `debug_llm_messages` フラグで全LLM呼び出しのログを制御
- 呼び出し元を識別できるラベル付け

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/client.py` | ログ出力強化 |
| `src/myao2/infrastructure/llm/response_generator.py` | ログ出力を LLMClient に委譲 |
| `src/myao2/infrastructure/llm/response_judgment.py` | ログ出力を LLMClient に委譲 |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | ログ出力を LLMClient に委譲 |
| `tests/infrastructure/llm/test_client.py` | ログ出力テスト追加 |

---

## 設計

### LLMClient の complete メソッド拡張

```python
async def complete(
    self,
    messages: list[dict],
    caller: str = "unknown",  # 呼び出し元識別子を追加
    **kwargs,
) -> str:
    """LLM呼び出しを実行

    Args:
        messages: OpenAI形式のメッセージリスト
        caller: 呼び出し元の識別子（例: "response_generator", "response_judgment"）
        **kwargs: LiteLLM追加パラメータ
    """
```

### ログ出力形式

```
# debug_llm_messages=True or DEBUG レベル有効時

INFO - myao2.infrastructure.llm.client - === LLM Request [response_generator] ===
INFO - myao2.infrastructure.llm.client - Model: gpt-4o-mini
INFO - myao2.infrastructure.llm.client - [0] role=system
INFO - myao2.infrastructure.llm.client - content: <システムプロンプト>
INFO - myao2.infrastructure.llm.client - [1] role=user
INFO - myao2.infrastructure.llm.client - content: <ユーザーメッセージ>
INFO - myao2.infrastructure.llm.client - === LLM Response [response_generator] ===
INFO - myao2.infrastructure.llm.client - <応答内容>
```

### 呼び出し元識別子

| コンポーネント | caller 値 |
|--------------|----------|
| LiteLLMResponseGenerator | `"response_generator"` |
| LLMResponseJudgment | `"response_judgment"` |
| LLMMemorySummarizer | `"memory_summarizer"` |

---

## 実装詳細

### LLMClient の変更

```python
class LLMClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._debug_llm_messages = bool(
            config.logging and config.logging.debug_llm_messages
        )

    def _should_log(self) -> bool:
        return self._debug_llm_messages or logger.isEnabledFor(logging.DEBUG)

    def _log_messages(self, messages: list[dict], caller: str) -> None:
        if not self._should_log():
            return
        level = logging.INFO if self._debug_llm_messages else logging.DEBUG
        logger.log(level, f"=== LLM Request [{caller}] ===")
        logger.log(level, f"Model: {self._config.llm.model}")
        for i, msg in enumerate(messages):
            logger.log(level, f"[{i}] role={msg['role']}")
            logger.log(level, f"content: {msg['content']}")

    def _log_response(self, response: str, caller: str) -> None:
        if not self._should_log():
            return
        level = logging.INFO if self._debug_llm_messages else logging.DEBUG
        logger.log(level, f"=== LLM Response [{caller}] ===")
        logger.log(level, response)

    async def complete(
        self,
        messages: list[dict],
        caller: str = "unknown",
        **kwargs,
    ) -> str:
        self._log_messages(messages, caller)
        # ... LLM呼び出し処理 ...
        self._log_response(response, caller)
        return response
```

### 各コンポーネントの変更

```python
# LiteLLMResponseGenerator
response = await self._client.complete(messages, caller="response_generator")

# LLMResponseJudgment
response = await self._client.complete(messages, caller="response_judgment")

# LLMMemorySummarizer
response = await self._client.complete(messages, caller="memory_summarizer")
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| complete | debug_llm_messages=True | INFO レベルでログ出力 |
| complete | debug_llm_messages=False, DEBUG有効 | DEBUG レベルでログ出力 |
| complete | debug_llm_messages=False, DEBUG無効 | ログ出力なし |
| complete | caller 指定 | ログに caller が含まれる |

---

## 設定

```yaml
logging:
  level: INFO
  debug_llm_messages: true  # 全LLM呼び出しのログを出力
```

---

## 完了基準

- [ ] LLMClient にログ出力メソッドが実装されている
- [ ] LLMClient.complete に caller パラメータが追加されている
- [ ] LiteLLMResponseGenerator が caller を指定して呼び出している
- [ ] LLMResponseJudgment が caller を指定して呼び出している
- [ ] LLMMemorySummarizer が caller を指定して呼び出している
- [ ] debug_llm_messages フラグでログ出力を制御できる
- [ ] 全テストが通過する
