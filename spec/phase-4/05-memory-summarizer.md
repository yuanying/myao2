# 05: MemorySummarizer（LLM を使った記憶生成）

## 目的

コンテキストから記憶を生成するサービスを実装する。
LLM を使用してスコープに応じた内容を要約し、長期記憶・短期記憶を生成する。

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
- タスク 04a（Context、ChannelMessages）に依存

---

## インターフェース設計

### MemorySummarizer Protocol

```python
from typing import Protocol

from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType


class MemorySummarizer(Protocol):
    """記憶要約サービス

    コンテキストから記憶を生成する。
    スコープに応じて要約対象が異なる：
    - THREAD: target_thread_ts のスレッドメッセージを要約
    - CHANNEL: conversation_history の全メッセージを要約
    - WORKSPACE: channel_memories を統合して要約
    """

    async def summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        """コンテキストから記憶を生成する

        Args:
            context: 会話コンテキスト（メッセージと記憶を含む）
            scope: 記憶のスコープ（要約対象を決定）
            memory_type: 記憶の種類
            existing_memory: 既存の記憶（インクリメンタル更新用、長期記憶の場合のみ使用）

        Returns:
            生成された記憶テキスト
            要約対象がない場合は空文字列または existing_memory を返す
        """
        ...
```

---

## スコープ別の動作

### THREAD スコープ

- `context.target_thread_ts` に対応するスレッドメッセージを要約
- `context.conversation_history.get_thread(target_thread_ts)` でメッセージを取得
- `target_thread_ts` が None の場合は空文字列を返す
- 補助情報としてチャンネルの記憶とワークスペースの記憶を含める

### CHANNEL スコープ

memory_type に応じて要約対象が異なる：

- **短期記憶（SHORT_TERM）**:
  - `context.conversation_history` の全メッセージ（トップレベル＋全スレッド）を要約
  - `context.conversation_history.get_all_messages()` でメッセージを取得
  - メッセージが空の場合は空文字列を返す

- **長期記憶（LONG_TERM）**:
  - チャンネルの短期記憶を既存の長期記憶にマージ
  - `context.channel_memories[channel_id].short_term_memory` を入力として使用
  - 短期記憶が空の場合は既存記憶を返す

- 補助情報としてワークスペースの記憶を含める

### WORKSPACE スコープ

memory_type に応じて要約対象が異なる：

- **短期記憶（SHORT_TERM）**:
  - 各チャンネルの**短期記憶のみ**を統合
  - `context.channel_memories` の各チャンネルの `short_term_memory` を入力として使用

- **長期記憶（LONG_TERM）**:
  - 各チャンネルの**長期記憶のみ**を統合し、既存のワークスペース長期記憶にマージ
  - `context.channel_memories` の各チャンネルの `long_term_memory` を入力として使用

- チャンネル記憶がない場合は空文字列または既存記憶を返す
- 補助情報はなし（最上位スコープのため）

---

## LLMMemorySummarizer 実装

### クラス設計

```python
from myao2.config.models import MemoryConfig
from myao2.domain.entities.context import Context
from myao2.domain.entities.memory import MemoryScope, MemoryType
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
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        content = self._get_content_for_scope(context, scope, memory_type)
        if not content:
            return existing_memory or ""

        prompt = self._build_prompt(content, scope, memory_type, existing_memory, context)
        max_tokens = self._get_max_tokens(memory_type)

        response = await self._client.complete(
            system_prompt=self._get_system_prompt(scope, memory_type),
            user_message=prompt,
            max_tokens=max_tokens,
        )

        return response.strip()

    def _get_content_for_scope(
        self, context: Context, scope: MemoryScope, memory_type: MemoryType
    ) -> str:
        """スコープと memory_type に応じた要約対象を取得"""
        ...

    def _build_prompt(self, content: str, scope: MemoryScope, ...) -> str:
        """プロンプトを構築"""
        ...
```

---

## プロンプト設計

### 長期記憶用システムプロンプト（THREAD/CHANNEL）

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

### 短期記憶用システムプロンプト（THREAD/CHANNEL）

```
あなたは会話の直近の状況を要約するアシスタントです。

以下の点に注意して要約してください：
- 現在進行中の話題を把握する
- 直近の質問や問題を記録する
- 参加者の現在の関心事を特定する
- 未解決の事項を明確にする

要約は箇条書きで、簡潔かつ具体的に記述してください。
```

### ワークスペース用システムプロンプト

```
あなたはワークスペース全体の記憶を統合するアシスタントです。

複数チャンネルの記憶を統合し、以下の点に注意して要約してください：
- チャンネル横断的なトピックや傾向を把握する
- 重要なプロジェクトや議論を記録する
- 組織全体の動向や関心事を特定する
- 繰り返し話題になるテーマを特定する

要約は箇条書きで、簡潔かつ具体的に記述してください。
```

### 補助情報の構成

スコープに応じて、上位スコープの記憶を「参考情報」としてプロンプトに含める：

| スコープ | 補助情報 |
|---------|---------|
| THREAD | チャンネルの記憶 + ワークスペースの記憶 |
| CHANNEL | ワークスペースの記憶 |
| WORKSPACE | なし |

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
- 新しいコンテンツのみを追加して要約を更新
- 古い情報の圧縮・統合を LLM に任せる

### エラーハンドリング

- LLM 呼び出し失敗時は例外を送出
- 呼び出し元（UseCase）でエラーハンドリング

### 空コンテンツ対応

- 要約対象がない場合は既存の記憶をそのまま返す
- 既存の記憶もない場合は空文字列を返す

---

## テストケース

### THREAD スコープ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッドメッセージ使用 | target_thread_ts のメッセージを要約 | スレッドメッセージが含まれる |
| 補助情報 | チャンネル記憶を参考情報に含める | チャンネル記憶が含まれる |
| target なし | target_thread_ts が None | 空文字列を返す |
| 既存記憶更新 | existing_memory あり | 既存記憶を含むプロンプト |

### CHANNEL スコープ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 短期記憶（全メッセージ使用） | トップレベル + スレッドメッセージを要約 | 全メッセージが含まれる |
| 長期記憶（短期記憶をマージ） | 短期記憶を長期記憶にマージ | 短期記憶が入力に含まれる |
| 補助情報 | ワークスペース記憶を参考情報に含める | ワークスペース記憶が含まれる |
| 空コンテンツ | 要約対象がない | 既存記憶または空文字列 |

### WORKSPACE スコープ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 短期記憶統合 | 各チャンネルの短期記憶のみを統合 | 短期記憶のみが含まれる |
| 長期記憶統合 | 各チャンネルの長期記憶のみを統合 | 長期記憶のみが含まれる |
| 補助情報なし | 最上位スコープ | 参考情報セクションなし |
| チャンネル記憶なし | channel_memories が空 | 既存記憶または空文字列 |

---

## 完了基準

- [x] MemorySummarizer Protocol が定義されている
- [x] LLMMemorySummarizer が実装されている
- [x] スコープ別の動作が実装されている
  - [x] THREAD: target_thread_ts のメッセージを使用
  - [x] CHANNEL 短期: 全メッセージを使用
  - [x] CHANNEL 長期: 短期記憶を長期記憶にマージ
  - [x] WORKSPACE 短期: チャンネル短期記憶のみを統合
  - [x] WORKSPACE 長期: チャンネル長期記憶のみを統合
- [x] 補助情報が適切に含まれている
- [x] 長期記憶用プロンプトが設計されている
- [x] 短期記憶用プロンプトが設計されている
- [x] ワークスペース用プロンプトが設計されている
- [x] インクリメンタル更新がサポートされている
- [x] 空コンテンツへの対応が実装されている
- [x] `__init__.py` でエクスポートされている
- [x] 全テストケースが通過する
