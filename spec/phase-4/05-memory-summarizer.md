# 05: MemorySummarizer（LLM を使った記憶生成）

## 目的

メッセージリストから記憶を生成するサービスを実装する。
LLM を使用して会話履歴を要約し、長期記憶・短期記憶を生成する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/memory_summarizer.py` | MemorySummarizer Protocol（新規） |
| `src/myao2/domain/services/__init__.py` | MemorySummarizer エクスポート（修正） |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | LLMMemorySummarizer 実装（新規） |
| `src/myao2/infrastructure/llm/__init__.py` | LLMMemorySummarizer エクスポート（修正） |
| `tests/infrastructure/llm/test_memory_summarizer.py` | テスト（新規） |

---

## 依存関係

- タスク 01（MemoryConfig）に依存
- タスク 02（Memory エンティティ）に依存

---

## インターフェース設計

### MemorySummarizer Protocol

```python
from typing import Protocol

from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.domain.entities.message import Message


class MemorySummarizer(Protocol):
    """記憶要約サービス

    メッセージリストから記憶を生成する。
    """

    async def summarize(
        self,
        messages: list[Message],
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        """メッセージリストから記憶を生成する

        Args:
            messages: 要約対象のメッセージリスト
            scope: 記憶のスコープ
            memory_type: 記憶の種類
            existing_memory: 既存の記憶（インクリメンタル更新用、長期記憶の場合のみ使用）

        Returns:
            生成された記憶テキスト
        """
        ...
```

---

## LLMMemorySummarizer 実装

### クラス設計

```python
from myao2.config.models import MemoryConfig
from myao2.domain.entities.memory import MemoryScope, MemoryType
from myao2.domain.entities.message import Message
from myao2.domain.services.memory_summarizer import MemorySummarizer
from myao2.infrastructure.llm.client import LLMClient


class LLMMemorySummarizer(MemorySummarizer):
    """LLM を使用した記憶要約サービス"""

    def __init__(
        self,
        client: LLMClient,
        config: MemoryConfig,
    ) -> None:
        self._client = client
        self._config = config

    async def summarize(
        self,
        messages: list[Message],
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        if not messages:
            return existing_memory or ""

        prompt = self._build_prompt(messages, scope, memory_type, existing_memory)
        max_tokens = self._get_max_tokens(memory_type)

        response = await self._client.complete(
            system_prompt=self._get_system_prompt(scope, memory_type),
            user_message=prompt,
            max_tokens=max_tokens,
        )

        return response.strip()

    def _build_prompt(
        self,
        messages: list[Message],
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None,
    ) -> str:
        """プロンプトを構築"""
        ...

    def _get_system_prompt(
        self,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> str:
        """システムプロンプトを取得"""
        ...

    def _get_max_tokens(self, memory_type: MemoryType) -> int:
        """最大トークン数を取得"""
        if memory_type == MemoryType.LONG_TERM:
            return self._config.long_term_summary_max_tokens
        return self._config.short_term_summary_max_tokens
```

---

## プロンプト設計

### 長期記憶用システムプロンプト

```
あなたは会話の長期的な傾向を時系列で要約するアシスタントです。

以下の点に注意して要約してください：
- 時系列順に出来事を整理する
- 重要なトピックや決定事項を記録する
- 参加者の傾向や関係性を把握する
- 繰り返し話題になるテーマを特定する
- 具体的な日時や期間を含める（可能な場合）

要約は箇条書きで、簡潔かつ具体的に記述してください。
```

### 長期記憶用プロンプト（新規生成）

```
以下の{scope_name}の会話履歴から、長期的な傾向を時系列で要約してください。

会話履歴:
{formatted_messages}
```

### 長期記憶用プロンプト（インクリメンタル更新）

```
以下の{scope_name}の会話履歴を、既存の要約に追加・更新してください。

既存の要約:
{existing_memory}

新しい会話履歴:
{formatted_messages}

既存の要約を維持しつつ、新しい情報を時系列順に追加してください。
古い情報は必要に応じて要約・統合しても構いません。
```

### 短期記憶用システムプロンプト

```
あなたは会話の直近の状況を要約するアシスタントです。

以下の点に注意して要約してください：
- 現在進行中の話題を把握する
- 直近の質問や問題を記録する
- 参加者の現在の関心事を特定する
- 未解決の事項を明確にする

要約は箇条書きで、簡潔かつ具体的に記述してください。
```

### 短期記憶用プロンプト

```
以下の{scope_name}の直近の会話から、現在の状況を要約してください。

会話履歴:
{formatted_messages}
```

### scope_name のマッピング

| MemoryScope | scope_name |
|-------------|------------|
| WORKSPACE | ワークスペース |
| CHANNEL | チャンネル |
| THREAD | スレッド |

---

## メッセージフォーマット

```python
def _format_messages(self, messages: list[Message]) -> str:
    """メッセージリストをフォーマット"""
    lines = []
    for msg in messages:
        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
        user = msg.user.name
        text = msg.text
        lines.append(f"[{timestamp}] {user}: {text}")
    return "\n".join(lines)
```

---

## 設計上の考慮事項

### トークン制限

- 長期記憶と短期記憶で異なる最大トークン数を設定可能
- MemoryConfig から取得

### インクリメンタル更新

- 長期記憶は既存の記憶を考慮した更新が可能
- 新しいメッセージのみを追加して要約を更新
- 古い情報の圧縮・統合を LLM に任せる

### エラーハンドリング

- LLM 呼び出し失敗時は例外を送出
- 呼び出し元（UseCase）でエラーハンドリング

### 空メッセージ対応

- メッセージが空の場合は既存の記憶をそのまま返す
- 既存の記憶もない場合は空文字列を返す

---

## テストケース

### summarize

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 長期記憶生成 | メッセージリストから新規生成 | 時系列の要約が生成される |
| 長期記憶更新 | 既存記憶 + 新メッセージ | 既存記憶が更新される |
| 短期記憶生成 | 直近のメッセージから生成 | 現在の状況が要約される |
| 空メッセージ | メッセージが空 | 既存記憶または空文字列 |
| スコープ別 | 各スコープで生成 | スコープに応じたプロンプトが使用される |

### _build_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 長期記憶・新規 | existing_memory なし | 新規生成用プロンプト |
| 長期記憶・更新 | existing_memory あり | 更新用プロンプト |
| 短期記憶 | 任意 | 短期記憶用プロンプト |

### _format_messages

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常 | 複数メッセージ | タイムスタンプ付きでフォーマット |
| 空リスト | メッセージなし | 空文字列 |

---

## 完了基準

- [ ] MemorySummarizer Protocol が定義されている
- [ ] LLMMemorySummarizer が実装されている
- [ ] 長期記憶用プロンプトが設計されている
- [ ] 短期記憶用プロンプトが設計されている
- [ ] インクリメンタル更新がサポートされている
- [ ] 空メッセージへの対応が実装されている
- [ ] `__init__.py` でエクスポートされている
- [ ] 全テストケースが通過する
