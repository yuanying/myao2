# extra05a: MemorySummarizerのシステムプロンプト方式への変更

## 目的

MemorySummarizerのLLM呼び出し方式をResponseGeneratorと同様に、システムプロンプトのみで全ての情報を渡す方式に統一する。
これにより、要約生成時に周辺コンテキスト（ワークスペース記憶、チャンネル記憶、会話履歴）を適切に参照できるようになり、より文脈を理解した要約が生成される。

## 背景

### 現状

| 項目 | ResponseGenerator | MemorySummarizer |
|-----|------------------|------------------|
| LLMメッセージ形式 | `[{"role": "system", ...}]` | `[{"role": "system", ...}, {"role": "user", ...}]` |
| コンテキスト渡し方 | システムプロンプトに全情報を含める | システムプロンプトは指示のみ、ユーザーメッセージにコンテンツ |
| 周辺情報の扱い | Jinja2テンプレートで構造化 | `_build_auxiliary_info()`で手動追加 |
| Contextの活用 | 全フィールドを使用 | 部分的に使用 |

### 問題点

1. ResponseGeneratorとMemorySummarizerでLLM呼び出しのアーキテクチャが異なる
2. 要約生成時に周辺コンテキストが十分に活用されていない
3. スレッド要約時に会話履歴全体を参照できない
4. プロンプト構築ロジックがコード内に分散している
5. Context構築ロジックが重複している
   - `helpers.py` の `build_context_with_memory()`: ReplyToMention、AutonomousResponse用
   - `generate_memory.py` 内で4箇所: メモリ生成用（独自実装）

### 解決方針

- ResponseGeneratorと同じアーキテクチャに統一
- システムプロンプトのみでコンテキスト全体を渡す
- Jinja2テンプレート `memory_prompt.j2` を拡張し、スコープ別に最適なプロンプトを生成
- Context構築ロジックを共通化し、GenerateMemoryUseCaseでも同じ関数を使用

## 実装するファイル

### インフラ層（LLM）

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `src/myao2/infrastructure/llm/templates/memory_prompt.j2` | 全面改修: システムプロンプト方式対応 | 修正 |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | システムプロンプトのみ使用に変更 | 修正 |

### アプリケーション層（UseCase）

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `src/myao2/application/use_cases/helpers.py` | Context構築関数の拡張・共通化 | 修正 |
| `src/myao2/application/use_cases/generate_memory.py` | 共通のContext構築関数を使用 | 修正 |

### テスト

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `tests/infrastructure/llm/test_memory_summarizer.py` | 新しいプロンプト形式に対応 | 修正 |
| `tests/application/use_cases/test_generate_memory.py` | Context構築の変更に対応 | 修正 |

## 依存関係

- タスク 05（MemorySummarizer 基本実装）に依存
- タスク extra05（Jinja2テンプレート化）に依存
- タスク 04a（Context、ChannelMessages構造）に依存

## インターフェース設計

### MemorySummarizer Protocol（変更なし）

既存の Protocol を維持する。呼び出し側の変更は不要。

```python
class MemorySummarizer(Protocol):
    async def summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        ...
```

## Context構築の共通化

### 現状の問題

現在、Context構築ロジックが2箇所に分散している：

1. **helpers.py の `build_context_with_memory()`**
   - ReplyToMentionUseCase、AutonomousResponseUseCase で使用
   - 全ての記憶（WS長期/短期、CH長期/短期）を取得
   - 会話履歴を含む完全なContextを構築

2. **generate_memory.py 内の独自実装**
   - 4箇所で異なるContextを手動構築
   - 必要最小限の情報のみ設定（記憶情報が不完全）

### 解決方針

`helpers.py` の `build_context_with_memory()` を拡張し、GenerateMemoryUseCaseでも使用できるようにする。

### 共通化後の Context 構築関数

```python
# helpers.py

async def build_context_with_memory(
    memory_repository: MemoryRepository,
    message_repository: MessageRepository,
    channel_repository: ChannelRepository,
    channel: Channel,
    persona: PersonaConfig,
    target_thread_ts: str | None = None,
    message_limit: int = DEFAULT_MESSAGE_LIMIT,
    since: datetime | None = None,  # 新規追加: メッセージ取得開始時刻
) -> Context:
    """
    ResponseGenerator と MemorySummarizer で共通使用するContext構築関数。

    Args:
        memory_repository: メモリリポジトリ
        message_repository: メッセージリポジトリ
        channel_repository: チャンネルリポジトリ
        channel: 現在のチャンネル
        persona: ペルソナ設定
        target_thread_ts: 対象スレッドのタイムスタンプ（オプション）
        message_limit: 取得するメッセージ数の上限
        since: メッセージ取得開始時刻（オプション、GenerateMemory用）

    Returns:
        完全なContext（全記憶情報を含む）
    """
    # 1. メッセージ取得
    if since:
        messages = await message_repository.find_by_channel_since(
            channel.id, since, limit=message_limit
        )
    else:
        messages = await message_repository.find_all_in_channel(
            channel.id, limit=message_limit
        )

    # 2. ChannelMessages構築
    channel_messages = build_channel_messages(channel, messages)

    # 3. ワークスペース記憶取得
    ws_long_term = await memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
    )
    ws_short_term = await memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.SHORT_TERM
    )

    # 4. 全チャンネルの記憶取得
    channels = await channel_repository.find_all()
    channel_memories: dict[str, ChannelMemory] = {}
    for ch in channels:
        ch_long = await memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, ch.id, MemoryType.LONG_TERM
        )
        ch_short = await memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, ch.id, MemoryType.SHORT_TERM
        )
        channel_memories[ch.id] = ChannelMemory(
            channel_id=ch.id,
            channel_name=ch.name,
            long_term_memory=ch_long.content if ch_long else None,
            short_term_memory=ch_short.content if ch_short else None,
        )

    # 5. Context構築
    return Context(
        persona=persona,
        conversation_history=channel_messages,
        workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
        workspace_short_term_memory=ws_short_term.content if ws_short_term else None,
        channel_memories=channel_memories,
        target_thread_ts=target_thread_ts,
    )
```

### GenerateMemoryUseCase での使用

```python
# generate_memory.py

async def _generate_channel_short_term_memory(
    self, channel: Channel, since: datetime
) -> None:
    # 共通関数を使用してContext構築
    context = await build_context_with_memory(
        memory_repository=self._memory_repository,
        message_repository=self._message_repository,
        channel_repository=self._channel_repository,
        channel=channel,
        persona=self._persona,
        since=since,
    )

    # MemorySummarizerで要約生成
    summary = await self._summarizer.summarize(
        context=context,
        scope=MemoryScope.CHANNEL,
        memory_type=MemoryType.SHORT_TERM,
    )
    ...

async def _generate_thread_memory(
    self, channel: Channel, thread_ts: str, since: datetime
) -> None:
    # 共通関数を使用してContext構築
    context = await build_context_with_memory(
        memory_repository=self._memory_repository,
        message_repository=self._message_repository,
        channel_repository=self._channel_repository,
        channel=channel,
        persona=self._persona,
        target_thread_ts=thread_ts,
        since=since,
    )

    # MemorySummarizerで要約生成
    summary = await self._summarizer.summarize(
        context=context,
        scope=MemoryScope.THREAD,
        memory_type=MemoryType.SHORT_TERM,
    )
    ...
```

### WORKSPACE スコープの Context 構築

WORKSPACE スコープでは特定のチャンネルに紐づかないため、空の ChannelMessages を使用する。

```python
async def _generate_workspace_memory(self) -> None:
    # 空のChannelMessagesを作成
    empty_channel = Channel(id="", name="")
    empty_messages = ChannelMessages(
        channel_id="",
        channel_name="",
        top_level_messages=[],
        thread_messages={},
    )

    # チャンネル記憶のみを取得（メッセージ不要）
    channel_memories = await self._fetch_all_channel_memories()

    context = Context(
        persona=self._persona,
        conversation_history=empty_messages,
        workspace_long_term_memory=existing_ws_long.content if existing_ws_long else None,
        workspace_short_term_memory=existing_ws_short.content if existing_ws_short else None,
        channel_memories=channel_memories,
    )
    ...
```

## スコープ別の動作

### THREAD スコープ（SHORT_TERM のみ）

**目的**: スレッドの内容を後で参照するために保存する要約を生成

**メモリタイプ**: SHORT_TERM のみ（LONG_TERM は使用しない）

**入力**:
- `context.target_thread_ts` に対応するスレッドメッセージが要約対象
- 周辺情報としてワークスペース記憶、チャンネル記憶、会話履歴全体を含める

**プロンプト構成**:
1. ペルソナのシステムプロンプト（`context.persona.system_prompt`）
2. ワークスペースの記憶（長期・短期）
3. チャンネル情報と各チャンネルの記憶
4. 現在の会話（トップレベル + 他のスレッド）
5. **要約対象スレッド**（最後に配置して強調）
6. 要約指示

### CHANNEL 短期記憶

**目的**: チャンネルの直近の状況を要約

**入力**:
- `context.conversation_history` の全メッセージ（トップレベル + 全スレッド）
- 周辺情報としてワークスペース記憶を含める

**プロンプト構成**:
1. ペルソナのシステムプロンプト
2. ワークスペースの記憶（長期・短期）
3. **要約対象: チャンネルの会話履歴**
4. 要約指示（短期記憶用）

### CHANNEL 長期記憶

**目的**: チャンネルの短期記憶を長期記憶に統合

**入力**:
- `context.channel_memories[channel_id].short_term_memory`
- `existing_memory`（既存の長期記憶）

**プロンプト構成**:
1. ペルソナのシステムプロンプト
2. ワークスペースの記憶（長期のみ）
3. 既存の長期記憶
4. **統合対象: チャンネルの短期記憶**
5. 統合指示

### WORKSPACE 短期記憶

**目的**: 各チャンネルの短期記憶を統合してワークスペース全体の状況を要約

**入力**:
- `context.channel_memories` の各チャンネルの `short_term_memory`

**プロンプト構成**:
1. ペルソナのシステムプロンプト
2. **統合対象: 各チャンネルの短期記憶**
3. 統合指示（短期記憶用）

### WORKSPACE 長期記憶

**目的**: 既存のワークスペース長期記憶と各チャンネルの長期記憶を全て統合

**入力**:
- `existing_memory`（既存のワークスペース長期記憶）
- `context.channel_memories` の各チャンネルの `long_term_memory`

**プロンプト構成**:
1. ペルソナのシステムプロンプト
2. **統合対象**: 既存のワークスペース長期記憶 + 各チャンネルの長期記憶
3. 統合指示（長期記憶用）

## プロンプト設計（Jinja2テンプレート）

### memory_prompt.j2 新構成

```jinja2
{% macro render_messages(messages) %}
{% for msg in messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user.name }}:
{{ msg.text }}

{% endfor %}
{% endmacro %}
{{ persona.system_prompt }}

{% if scope == "thread" %}
{# === THREAD SCOPE === #}
{% if workspace_long_term_memory or workspace_short_term_memory %}
## 記憶

{% if workspace_long_term_memory %}
### ワークスペースの歴史
{{ workspace_long_term_memory }}

{% endif %}
{% if workspace_short_term_memory %}
### ワークスペースの最近の出来事
{{ workspace_short_term_memory }}

{% endif %}
{% endif %}
{% if channel_memories %}
## チャンネル情報

あなたが参加しているチャンネルは以下です。

{% for channel in channel_memories.values() %}
- #{{ channel.channel_name }}
{% endfor %}

現在、あなたは #{{ current_channel_name }} にいます。

## 各チャンネルの記憶

{% for channel in channel_memories.values() %}
{% if channel.long_term_memory or channel.short_term_memory %}
### #{{ channel.channel_name }}

{% if channel.long_term_memory %}
#### 歴史
{{ channel.long_term_memory }}

{% endif %}
{% if channel.short_term_memory %}
#### 最近の出来事
{{ channel.short_term_memory }}

{% endif %}
{% endif %}
{% endfor %}
{% endif %}
## 現在の会話

現在は、#{{ current_channel_name }} チャンネルにいます。
直近の会話は以下の通りです。

{% if target_thread_ts %}
### トップレベル

{{ render_messages(top_level_messages) }}
{% endif %}
{% for thread_ts, thread_msgs in thread_messages.items() %}
{% if thread_ts != target_thread_ts %}
### スレッド: {{ thread_ts }}

{{ render_messages(thread_msgs) }}
{% endif %}
{% endfor %}
## 要約対象スレッド: {{ target_thread_ts }}

{{ render_messages(target_thread_messages) }}
---
上記のスレッドの内容を要約してください。
現在進行中の話題、未解決の事項を中心に要約してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。

{% elif scope == "channel" %}
{# === CHANNEL SCOPE === #}
{% if workspace_long_term_memory %}
## ワークスペースの概要
{{ workspace_long_term_memory }}

{% endif %}
{% if memory_type == "short_term" %}
## 要約対象: チャンネル会話履歴

以下は #{{ current_channel_name }} チャンネルの直近の会話です。

{% if top_level_messages %}
### トップレベル

{{ render_messages(top_level_messages) }}
{% endif %}
{% for thread_ts, thread_msgs in thread_messages.items() %}
### スレッド: {{ thread_ts }}

{{ render_messages(thread_msgs) }}
{% endfor %}
---
上記のチャンネルの会話を要約してください。
現在進行中の話題、参加者の関心事、未解決の事項を中心に要約してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。

{% else %}
{# CHANNEL LONG_TERM #}
{% if existing_memory %}
## 既存のチャンネル長期記憶
{{ existing_memory }}

{% endif %}
## 統合対象: チャンネルの短期記憶
{{ channel_short_term_memory }}

---
上記の短期記憶を既存の長期記憶に統合してください。
時系列で出来事を整理し、重要なトピックや決定事項を記録してください。
古い情報は必要に応じて要約・統合しても構いません。
要約は箇条書きで、簡潔かつ具体的に記述してください。

{% endif %}

{% elif scope == "workspace" %}
{# === WORKSPACE SCOPE === #}
{% if memory_type == "short_term" %}
## 統合対象: 各チャンネルの短期記憶

{% for channel in channel_memories.values() %}
{% if channel.short_term_memory %}
### #{{ channel.channel_name }}
{{ channel.short_term_memory }}

{% endif %}
{% endfor %}
---
上記の各チャンネルの短期記憶を統合し、ワークスペース全体の現在の状況を要約してください。
チャンネル横断的なトピックや傾向を把握し、重要なプロジェクトや議論を記録してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。

{% else %}
{# WORKSPACE LONG_TERM #}
## 統合対象

{% if existing_memory %}
### 既存のワークスペース長期記憶
{{ existing_memory }}

{% endif %}
{% for channel in channel_memories.values() %}
{% if channel.long_term_memory %}
### #{{ channel.channel_name }} の長期記憶
{{ channel.long_term_memory }}

{% endif %}
{% endfor %}
---
上記の全ての記憶を統合し、ワークスペース全体の長期記憶を生成してください。
チャンネル横断的なトピックや傾向、重要なプロジェクト、組織全体の動向を記録してください。
古い情報は必要に応じて要約・統合しても構いません。
要約は箇条書きで、簡潔かつ具体的に記述してください。

{% endif %}
{% endif %}
```

## プロンプト例

以下に、各スコープ×メモリタイプの組み合わせで生成されるシステムプロンプトの具体例を示す。

### 前提データ

```python
# Context の内容
persona.system_prompt = "あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。"

workspace_long_term_memory = """
- 2024年1月: プロジェクトAが開始された
- 2024年2月: 新メンバーが参加した
"""

workspace_short_term_memory = """
- プロジェクトAの進捗確認中
- 来週のミーティング準備
"""

channel_memories = {
    "C001": ChannelMemory(
        channel_id="C001",
        channel_name="general",
        long_term_memory="- チーム全体の連絡に使用\n- 週次報告が行われる",
        short_term_memory="- 今週の進捗報告が投稿された\n- 新しいツールの導入検討中",
    ),
    "C002": ChannelMemory(
        channel_id="C002",
        channel_name="project-a",
        long_term_memory="- プロジェクトAの議論用\n- 設計レビューが行われた",
        short_term_memory="- APIの仕様変更を議論中\n- 次のマイルストーンを計画中",
    ),
}

# 現在のチャンネル: #general (C001)
conversation_history.channel_name = "general"
conversation_history.top_level_messages = [
    Message(timestamp="2024-03-01 10:00", user="alice", text="おはよう！"),
    Message(timestamp="2024-03-01 10:05", user="bob", text="おはよう〜"),
]
conversation_history.thread_messages = {
    "1709280000.000001": [
        Message(timestamp="2024-03-01 10:10", user="alice", text="今日のタスク確認しよう"),
        Message(timestamp="2024-03-01 10:15", user="bob", text="了解、リスト共有するね"),
    ],
    "1709280000.000002": [
        Message(timestamp="2024-03-01 11:00", user="carol", text="ミーティングの時間変更できる？"),
        Message(timestamp="2024-03-01 11:05", user="alice", text="14時からなら大丈夫"),
    ],
}

target_thread_ts = "1709280000.000001"  # THREADスコープの場合
existing_memory = "- 過去の重要な出来事..."  # 長期記憶更新時
```

---

### 1. THREAD（SHORT_TERM のみ）

```
あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。

## 記憶

### ワークスペースの歴史
- 2024年1月: プロジェクトAが開始された
- 2024年2月: 新メンバーが参加した

### ワークスペースの最近の出来事
- プロジェクトAの進捗確認中
- 来週のミーティング準備

## チャンネル情報

あなたが参加しているチャンネルは以下です。

- #general
- #project-a

現在、あなたは #general にいます。

## 各チャンネルの記憶

### #general

#### 歴史
- チーム全体の連絡に使用
- 週次報告が行われる

#### 最近の出来事
- 今週の進捗報告が投稿された
- 新しいツールの導入検討中

### #project-a

#### 歴史
- プロジェクトAの議論用
- 設計レビューが行われた

#### 最近の出来事
- APIの仕様変更を議論中
- 次のマイルストーンを計画中

## 現在の会話

現在は、#general チャンネルにいます。
直近の会話は以下の通りです。

### トップレベル

**2024-03-01 10:00:00** alice:
おはよう！

**2024-03-01 10:05:00** bob:
おはよう〜

### スレッド: 1709280000.000002

**2024-03-01 11:00:00** carol:
ミーティングの時間変更できる？

**2024-03-01 11:05:00** alice:
14時からなら大丈夫

## 要約対象スレッド: 1709280000.000001

**2024-03-01 10:10:00** alice:
今日のタスク確認しよう

**2024-03-01 10:15:00** bob:
了解、リスト共有するね

---
上記のスレッドの内容を要約してください。
現在進行中の話題、未解決の事項を中心に要約してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。
```

---

### 2. CHANNEL × SHORT_TERM

```
あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。

## ワークスペースの概要
- 2024年1月: プロジェクトAが開始された
- 2024年2月: 新メンバーが参加した

## 要約対象: チャンネル会話履歴

以下は #general チャンネルの直近の会話です。

### トップレベル

**2024-03-01 10:00:00** alice:
おはよう！

**2024-03-01 10:05:00** bob:
おはよう〜

### スレッド: 1709280000.000001

**2024-03-01 10:10:00** alice:
今日のタスク確認しよう

**2024-03-01 10:15:00** bob:
了解、リスト共有するね

### スレッド: 1709280000.000002

**2024-03-01 11:00:00** carol:
ミーティングの時間変更できる？

**2024-03-01 11:05:00** alice:
14時からなら大丈夫

---
上記のチャンネルの会話を要約してください。
現在進行中の話題、参加者の関心事、未解決の事項を中心に要約してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。
```

---

### 3. CHANNEL × LONG_TERM

```
あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。

## ワークスペースの概要
- 2024年1月: プロジェクトAが開始された
- 2024年2月: 新メンバーが参加した

## 既存のチャンネル長期記憶
- チーム全体の連絡に使用
- 週次報告が行われる

## 統合対象: チャンネルの短期記憶
- 今週の進捗報告が投稿された
- 新しいツールの導入検討中

---
上記の短期記憶を既存の長期記憶に統合してください。
時系列で出来事を整理し、重要なトピックや決定事項を記録してください。
古い情報は必要に応じて要約・統合しても構いません。
要約は箇条書きで、簡潔かつ具体的に記述してください。
```

---

### 4. WORKSPACE × SHORT_TERM

```
あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。

## 統合対象: 各チャンネルの短期記憶

### #general
- 今週の進捗報告が投稿された
- 新しいツールの導入検討中

### #project-a
- APIの仕様変更を議論中
- 次のマイルストーンを計画中

---
上記の各チャンネルの短期記憶を統合し、ワークスペース全体の現在の状況を要約してください。
チャンネル横断的なトピックや傾向を把握し、重要なプロジェクトや議論を記録してください。
要約は箇条書きで、簡潔かつ具体的に記述してください。
```

---

### 5. WORKSPACE × LONG_TERM

```
あなたは「みゃお」という名前の猫キャラクターです。友達のように振る舞います。

## 統合対象

### 既存のワークスペース長期記憶
- 2024年1月: プロジェクトAが開始された
- 2024年2月: 新メンバーが参加した

### #general の長期記憶
- チーム全体の連絡に使用
- 週次報告が行われる

### #project-a の長期記憶
- プロジェクトAの議論用
- 設計レビューが行われた

---
上記の全ての記憶を統合し、ワークスペース全体の長期記憶を生成してください。
チャンネル横断的なトピックや傾向、重要なプロジェクト、組織全体の動向を記録してください。
古い情報は必要に応じて要約・統合しても構いません。
要約は箇条書きで、簡潔かつ具体的に記述してください。
```

---

## LLMMemorySummarizer 実装変更

### 主要な変更点

1. `_build_system_prompt()` メソッドを追加し、Jinja2テンプレートでシステムプロンプトを生成
2. LLM呼び出しを `[{"role": "system", ...}]` のみに変更
3. `format_timestamp` フィルターを追加

### 削除するメソッド

以下のメソッドは不要となり削除:
- `_get_content_for_scope()`
- `_get_thread_content()`
- `_get_channel_content()`
- `_get_workspace_content()`
- `_build_prompt()`
- `_build_auxiliary_info()`
- `_get_scope_name()`
- `_format_messages()` （テンプレート内マクロに移行）

### 新規追加メソッド

```python
def _build_system_prompt(
    self,
    context: Context,
    scope: MemoryScope,
    memory_type: MemoryType,
    existing_memory: str | None,
) -> str:
    """Build system prompt using Jinja2 template."""
    channel_messages = context.conversation_history

    # ターゲットスレッドのメッセージを取得
    target_thread_messages = []
    if context.target_thread_ts:
        target_thread_messages = channel_messages.get_thread(
            context.target_thread_ts
        )

    # チャンネル短期記憶を取得（CHANNEL LONG_TERM用）
    channel_short_term_memory = None
    if scope == MemoryScope.CHANNEL and memory_type == MemoryType.LONG_TERM:
        channel_id = channel_messages.channel_id
        if channel_id in context.channel_memories:
            channel_short_term_memory = (
                context.channel_memories[channel_id].short_term_memory
            )

    template_context = {
        "persona": context.persona,
        "scope": scope.value,
        "memory_type": memory_type.value,
        "existing_memory": existing_memory,
        "workspace_long_term_memory": context.workspace_long_term_memory,
        "workspace_short_term_memory": context.workspace_short_term_memory,
        "channel_memories": context.channel_memories,
        "current_channel_name": channel_messages.channel_name,
        "top_level_messages": channel_messages.top_level_messages,
        "thread_messages": channel_messages.thread_messages,
        "target_thread_ts": context.target_thread_ts,
        "target_thread_messages": target_thread_messages,
        "channel_short_term_memory": channel_short_term_memory,
    }

    return self._template.render(**template_context)
```

## テストケース

### THREAD スコープ（SHORT_TERM のみ）

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| システムプロンプト構成 | target_thread_ts あり | ワークスペース記憶、チャンネル記憶、会話履歴、対象スレッドがプロンプトに含まれる |
| 対象スレッドの位置 | 通常ケース | 対象スレッドがプロンプトの最後に配置される |
| 周辺情報の包含 | 記憶あり | ResponseGeneratorと同等のコンテキストが含まれる |
| target なし | target_thread_ts が None | 空文字列を返す |

### CHANNEL スコープ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 短期記憶（全メッセージ） | 会話履歴あり | トップレベル + 全スレッドがプロンプトに含まれる |
| 短期記憶（ワークスペース記憶） | ワークスペース記憶あり | ワークスペースの概要がプロンプトに含まれる |
| 長期記憶（短期記憶統合） | 短期記憶あり | 短期記憶と既存長期記憶がプロンプトに含まれる |
| 空会話履歴 | メッセージなし | 既存記憶または空文字列を返す |

### WORKSPACE スコープ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 短期記憶統合 | 各チャンネル短期記憶あり | 各チャンネルの短期記憶のみがプロンプトに含まれる |
| 長期記憶統合 | 各チャンネル長期記憶あり | 既存のWS長期記憶と各チャンネルの長期記憶が全て「統合対象」として含まれる |
| ペルソナ含有 | 通常ケース | persona.system_prompt がプロンプトに含まれる |
| 空チャンネル記憶 | channel_memories が空 | 既存記憶または空文字列を返す |

### LLM呼び出し形式

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| メッセージ形式 | 任意のスコープ | `[{"role": "system", ...}]` のみ（user メッセージなし）|
| max_tokens | LONG_TERM | long_term_summary_max_tokens が使用される |
| max_tokens | SHORT_TERM | short_term_summary_max_tokens が使用される |

## 完了基準

### MemorySummarizer（LLM層）

- [x] memory_prompt.j2 がシステムプロンプト方式に対応している
- [x] LLMMemorySummarizer がシステムプロンプトのみで呼び出している
- [x] THREAD スコープで ResponseGenerator 同等のコンテキストが渡される
  - [x] ワークスペース記憶が含まれる
  - [x] チャンネル記憶が含まれる
  - [x] 会話履歴全体が含まれる
  - [x] 対象スレッドが最後に配置される
- [x] CHANNEL 短期記憶で全メッセージとワークスペース記憶が含まれる
- [x] CHANNEL 長期記憶で短期記憶が入力として使用される
- [x] WORKSPACE 短期記憶で各チャンネルの短期記憶のみが統合される
- [x] WORKSPACE 長期記憶で既存のWS長期記憶と各チャンネルの長期記憶が全て「統合対象」として含まれる
- [x] ペルソナのシステムプロンプトが全スコープで含まれる
- [x] 既存の Protocol インターフェースが維持されている
- [x] format_timestamp フィルターが実装されている

### Context構築の共通化（UseCase層）

- [x] `helpers.py` の `build_context_with_memory()` に `since` パラメータが追加されている
- [x] GenerateMemoryUseCase が共通の `build_context_with_memory()` を使用している
  - [x] チャンネル短期記憶生成で使用
  - [x] スレッド記憶生成で使用
- [x] ResponseGenerator用とMemorySummarizer用で同一のContext構築関数を使用している
- [x] 既存の ReplyToMentionUseCase、AutonomousResponseUseCase が正常に動作する

### テスト

- [x] 全テストケースが通過する
- [x] GenerateMemoryUseCase のテストがContext構築の変更に対応している
