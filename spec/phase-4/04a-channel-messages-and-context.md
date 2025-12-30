# 04a: ChannelMessages と Context の構造変更

## 目的

ChannelMessages ドメインエンティティを導入し、Context の構造を変更することで、より豊富なコンテキスト情報を LLM に提供できるようにする。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/channel_messages.py` | ChannelMessages, ChannelMemory エンティティ（新規） |
| `src/myao2/domain/entities/context.py` | Context の構造変更（修正） |
| `src/myao2/domain/entities/__init__.py` | エクスポート追加（修正） |
| `src/myao2/config/models.py` | ResponseConfig への設定追加（修正） |
| `config.yaml.example` | 設定例の更新（修正） |
| `tests/domain/entities/test_channel_messages.py` | ChannelMessages テスト（新規） |
| `tests/domain/entities/test_context.py` | Context テスト更新（修正） |

---

## 依存関係

- タスク 02（Memory エンティティ）に依存（概念のみ）
- タスク 04（Context への記憶フィールド追加）を置き換え

---

## インターフェース設計

### ChannelMemory

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelMemory:
    """チャンネルの記憶を保持するデータクラス

    Attributes:
        channel_id: チャンネル ID
        channel_name: チャンネル名
        long_term_memory: 長期記憶（全期間の時系列要約）
        short_term_memory: 短期記憶（直近の要約）
    """

    channel_id: str
    channel_name: str
    long_term_memory: str | None = None
    short_term_memory: str | None = None
```

### ChannelMessages

```python
from dataclasses import dataclass, field

from myao2.domain.entities.message import Message


@dataclass(frozen=True)
class ChannelMessages:
    """チャンネルのメッセージを構造化して保持するデータクラス

    Attributes:
        channel_id: チャンネル ID
        channel_name: チャンネル名
        top_level_messages: トップレベルメッセージのリスト（スレッドの親メッセージ含む）
        thread_messages: スレッドごとのメッセージマップ（thread_ts -> メッセージリスト）
    """

    channel_id: str
    channel_name: str
    top_level_messages: list[Message] = field(default_factory=list)
    thread_messages: dict[str, list[Message]] = field(default_factory=dict)

    def get_all_messages(self) -> list[Message]:
        """全メッセージを時系列で取得

        Returns:
            トップレベルメッセージとスレッドメッセージを時系列順に結合したリスト
        """
        all_msgs = list(self.top_level_messages)
        for thread_msgs in self.thread_messages.values():
            all_msgs.extend(thread_msgs)
        return sorted(all_msgs, key=lambda m: m.timestamp)

    def get_thread(self, thread_ts: str) -> list[Message]:
        """指定したスレッドのメッセージを取得

        Args:
            thread_ts: スレッドの親メッセージのタイムスタンプ

        Returns:
            スレッド内のメッセージリスト（存在しない場合は空リスト）
        """
        return self.thread_messages.get(thread_ts, [])

    @property
    def thread_count(self) -> int:
        """スレッド数を取得"""
        return len(self.thread_messages)

    @property
    def total_message_count(self) -> int:
        """全メッセージ数を取得"""
        return len(self.top_level_messages) + sum(
            len(msgs) for msgs in self.thread_messages.values()
        )
```

### Context（変更後）

```python
from dataclasses import dataclass, field

from myao2.config.models import PersonaConfig
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages


@dataclass(frozen=True)
class Context:
    """Conversation context.

    Holds conversation history, channel memories, and thread memories for LLM.
    This is a pure data class - system prompt construction is the
    responsibility of the module that receives the context.

    Attributes:
        persona: Persona configuration with name and system prompt.
        conversation_history: Channel messages structure for target channel.
        workspace_long_term_memory: Workspace long-term memory.
        workspace_short_term_memory: Workspace short-term memory.
        channel_memories: Active channel memories (channel_id -> ChannelMemory).
        thread_memories: Recent thread summaries (thread_ts -> memory).
        target_thread_ts: Target thread timestamp (None for top-level).
    """

    persona: PersonaConfig
    conversation_history: ChannelMessages
    workspace_long_term_memory: str | None = None
    workspace_short_term_memory: str | None = None
    channel_memories: dict[str, ChannelMemory] = field(default_factory=dict)
    thread_memories: dict[str, str] = field(default_factory=dict)
    target_thread_ts: str | None = None
```

---

## 設定追加

### ResponseConfig

```python
@dataclass
class ResponseConfig:
    """自律応答設定"""

    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
    message_limit: int = 20
    max_message_age_seconds: int = 43200  # 12 hours
    channel_messages_limit: int = 50  # 新規: 全体のメッセージ制限
    active_channel_days: int = 7  # 新規: アクティブチャンネルの判定日数
    thread_memory_days: int = 7  # 新規: スレッド記憶の保持日数
    judgment_skip: JudgmentSkipConfig | None = None
```

### 設定説明

| フィールド | 型 | デフォルト値 | 説明 |
|-----------|-----|-------------|------|
| channel_messages_limit | int | 50 | ChannelMessages に含める全体のメッセージ数上限 |
| active_channel_days | int | 7 | アクティブなチャンネルとして判定する日数 |
| thread_memory_days | int | 7 | スレッド記憶を保持する日数 |

---

## フィールド説明

### Context フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| persona | PersonaConfig | ペルソナ設定（名前とシステムプロンプト） |
| conversation_history | ChannelMessages | ターゲットチャンネルのメッセージ構造 |
| workspace_long_term_memory | str \| None | ワークスペースの長期記憶 |
| workspace_short_term_memory | str \| None | ワークスペースの短期記憶 |
| channel_memories | dict[str, ChannelMemory] | アクティブなチャンネルの記憶マップ（長期・短期記憶を含む） |
| thread_memories | dict[str, str] | 直近のスレッド要約マップ |
| target_thread_ts | str \| None | 返答対象のスレッド（None ならトップレベル） |

### ChannelMessages フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| channel_id | str | チャンネル ID |
| channel_name | str | チャンネル名 |
| top_level_messages | list[Message] | トップレベルメッセージ（スレッド親含む） |
| thread_messages | dict[str, list[Message]] | スレッドごとのメッセージ |

### ChannelMemory フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| channel_id | str | チャンネル ID |
| channel_name | str | チャンネル名 |
| long_term_memory | str \| None | 長期記憶 |
| short_term_memory | str \| None | 短期記憶 |

---

## 変更点のサマリー

### 削除されるフィールド

| フィールド | 理由 |
|-----------|------|
| other_channel_messages | channel_memories に統合 |
| channel_long_term_memory | channel_memories に移動 |
| channel_short_term_memory | channel_memories に移動 |
| thread_memory | thread_memories に変更（単一→複数） |

### 追加されるフィールド

| フィールド | 説明 |
|-----------|------|
| channel_memories | 複数チャンネルの記憶を保持 |
| thread_memories | 複数スレッドの要約を保持 |
| target_thread_ts | 返答対象を明示 |

### 型変更

| フィールド | 変更前 | 変更後 |
|-----------|--------|--------|
| conversation_history | list[Message] | ChannelMessages |

---

## 使用パターン

### 基本的な Context 生成

```python
# ChannelMessages を構築
channel_messages = ChannelMessages(
    channel_id="C123",
    channel_name="general",
    top_level_messages=[msg1, msg2, msg3],
    thread_messages={
        "1234567890.000000": [thread_msg1, thread_msg2],
    },
)

# Context を生成
context = Context(
    persona=persona_config,
    conversation_history=channel_messages,
)
```

### 記憶を含む Context 生成

```python
# チャンネル記憶を構築
channel_memories = {
    "C123": ChannelMemory(
        channel_id="C123",
        channel_name="general",
        long_term_memory="general チャンネルでは技術的な議論が多い...",
        short_term_memory="最近は新プロジェクトの話題が中心...",
    ),
    "C456": ChannelMemory(
        channel_id="C456",
        channel_name="random",
        long_term_memory="random チャンネルは雑談が多い...",
    ),
}

# スレッド記憶を構築
thread_memories = {
    "1234567890.000000": "このスレッドではバグ修正について議論...",
    "1234567891.000000": "新機能のデザインについて...",
}

# Context を生成
context = Context(
    persona=persona_config,
    conversation_history=channel_messages,
    workspace_long_term_memory="このワークスペースは...",
    workspace_short_term_memory="直近では...",
    channel_memories=channel_memories,
    thread_memories=thread_memories,
    target_thread_ts="1234567890.000000",
)
```

---

## ChannelMessages の構築フロー

```
1. MessageRepository から直近 channel_messages_limit 件のメッセージを取得
   - find_all_in_channel(channel_id, limit=channel_messages_limit)

2. メッセージをトップレベルとスレッドに分類
   - thread_ts が None → top_level_messages
   - thread_ts が設定 → thread_messages[thread_ts] に追加

3. スレッドの親メッセージがトップレベルにない場合は追加
   - thread_messages のキーに対応するメッセージを探す
   - なければトップレベルに追加

4. ChannelMessages インスタンスを生成
```

---

## 設計上の考慮事項

### イミュータブル

- `frozen=True` を維持
- ChannelMessages, ChannelMemory, Context すべてイミュータブル

### デフォルト値

- 記憶フィールドは `None` または空の辞書がデフォルト
- 記憶システムが無効な場合や、記憶が未生成の場合に対応

### 後方互換性

- **破壊的変更**: `conversation_history` の型が変わるため、既存コードの修正が必要
- 移行ガイドを提供
- **暫定処置**: タスク 08 が実装されるまでは、影響を受けるコンポーネントに暫定処置を適用（詳細は後述）

### パフォーマンス

- `channel_messages_limit` で全体のメッセージ数を制限
- `active_channel_days` でアクティブなチャンネルのみを対象に
- `thread_memory_days` でスレッド記憶の対象を限定

---

## テストケース

### ChannelMessages

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 空のインスタンス | channel_id, channel_name のみ指定 | 空のリスト/辞書で生成 |
| トップレベルのみ | top_level_messages のみ指定 | thread_messages は空 |
| スレッドのみ | thread_messages のみ指定 | top_level_messages は空 |
| 混合 | 両方指定 | 両方が設定される |
| get_all_messages | 混合データ | 時系列順で全メッセージ返却 |
| get_thread | 存在するスレッド | メッセージリスト返却 |
| get_thread | 存在しないスレッド | 空リスト返却 |
| thread_count | 複数スレッド | 正しいスレッド数 |
| total_message_count | 混合データ | 正しい合計数 |
| イミュータブル | フィールド変更試行 | FrozenInstanceError |

### ChannelMemory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 必須フィールドのみ | channel_id, channel_name のみ | 記憶フィールドは None |
| 全フィールド | 全て指定 | 全て設定される |
| イミュータブル | フィールド変更試行 | FrozenInstanceError |

### Context

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 必須フィールドのみ | persona, conversation_history のみ | 記憶フィールドはデフォルト |
| 全フィールド | 全て指定 | 全て設定される |
| channel_memories | 複数チャンネル | 正しく保持 |
| thread_memories | 複数スレッド | 正しく保持 |
| target_thread_ts | スレッド指定 | 正しく保持 |
| イミュータブル | フィールド変更試行 | FrozenInstanceError |

---

## 移行ガイド

### 変更前

```python
context = Context(
    persona=persona_config,
    conversation_history=messages,  # list[Message]
    other_channel_messages={"C456": other_messages},
    channel_long_term_memory="...",
    channel_short_term_memory="...",
    thread_memory="...",
)
```

### 変更後

```python
# ChannelMessages を構築
channel_messages = ChannelMessages(
    channel_id="C123",
    channel_name="general",
    top_level_messages=top_messages,
    thread_messages={"thread_ts": thread_messages},
)

# ChannelMemory を構築
channel_memories = {
    "C123": ChannelMemory(
        channel_id="C123",
        channel_name="general",
        long_term_memory="...",
        short_term_memory="...",
    ),
}

context = Context(
    persona=persona_config,
    conversation_history=channel_messages,
    channel_memories=channel_memories,
    thread_memories={"thread_ts": "..."},
    target_thread_ts="thread_ts",
)
```

---

## 暫定処置（タスク 08 実装まで）

本タスクで Context の構造を変更すると、以下のコンポーネントに影響が出る。
タスク 08（ResponseGenerator への記憶組み込み）が実装されるまでの間、テストが壊れないよう暫定処置を適用する。

### 影響を受けるコンポーネント

| コンポーネント | 影響 | 暫定処置 |
|---------------|------|---------|
| `LiteLLMResponseGenerator` | `conversation_history` の型変更 | `get_all_messages()` で `list[Message]` を取得して既存ロジックを維持 |
| `LiteLLMResponseJudgment` | 同上 | 同上 |
| `AutonomousResponseUseCase` | Context 構築方法の変更 | 新しい Context 構造で構築するが、記憶フィールドは空で渡す |
| `ReplyToMentionUseCase` | 同上 | 同上 |

### ResponseGenerator の暫定実装

```python
def _build_system_prompt(
    self,
    user_message: Message,
    context: Context,
) -> str:
    """system prompt を構築する（暫定）"""
    parts: list[str] = []

    # 1. ペルソナ
    parts.append(context.persona.system_prompt)

    # 2. 会話履歴（暫定: ChannelMessages から list[Message] を取得）
    all_messages = context.conversation_history.get_all_messages()
    if all_messages:
        parts.append("## 会話履歴")
        parts.append(self._format_conversation_history(all_messages))

    # 3. 返答すべきメッセージ
    parts.append("## 返答すべきメッセージ")
    parts.append(self._format_message_with_metadata(user_message))

    # 4. 指示
    parts.append("---")
    parts.append(
        "上記の情報を元に、「返答すべきメッセージ」に対して自然な返答を生成してください。"
    )

    return "\n\n".join(parts)
```

### UseCase の暫定実装

```python
async def _build_context(
    self,
    channel: Channel,
    messages: list[Message],
    thread_ts: str | None,
) -> Context:
    """Context を構築する（暫定）"""
    # メッセージをトップレベルとスレッドに分類
    top_level_messages: list[Message] = []
    thread_messages: dict[str, list[Message]] = {}

    for msg in messages:
        if msg.thread_ts is None:
            top_level_messages.append(msg)
        else:
            if msg.thread_ts not in thread_messages:
                thread_messages[msg.thread_ts] = []
            thread_messages[msg.thread_ts].append(msg)

    channel_messages = ChannelMessages(
        channel_id=channel.id,
        channel_name=channel.name,
        top_level_messages=top_level_messages,
        thread_messages=thread_messages,
    )

    return Context(
        persona=self._persona_config,
        conversation_history=channel_messages,
        target_thread_ts=thread_ts,
        # 以下は暫定で空のまま（タスク 08 で実装）
        # workspace_long_term_memory=...,
        # workspace_short_term_memory=...,
        # channel_memories=...,
        # thread_memories=...,
    )
```

### 暫定処置の解除

タスク 08 の実装時に以下を行う：

1. `ResponseGenerator` の `_build_system_prompt` を新しいプロンプト構造に変更
2. `ResponseJudgment` も同様に変更
3. UseCase で記憶フィールドを適切に設定
4. 暫定コードを削除

---

## 完了基準

- [ ] ChannelMessages エンティティが実装されている
- [ ] ChannelMemory エンティティが実装されている
- [ ] Context が新しい構造に変更されている
- [ ] ResponseConfig に新しい設定が追加されている
- [ ] config.yaml.example が更新されている
- [ ] 影響を受けるコンポーネントに暫定処置が適用されている
- [ ] 全てのテストケースが通過する
