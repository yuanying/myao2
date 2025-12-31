# 08: ResponseGenerator への記憶組み込み

> **注意**: この設計書は [04a-channel-messages-and-context.md](./04a-channel-messages-and-context.md) の変更に伴い更新されました。

## 目的

LiteLLMResponseGenerator を拡張し、記憶とチャンネル情報を system prompt に含める。
プロンプト構築には Jinja2 テンプレートを使用し、レビュー・保守性を高める。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/response_generator.py` | 記憶・チャンネル情報組み込み（修正） |
| `src/myao2/infrastructure/llm/templates/system_prompt.j2` | システムプロンプトテンプレート（新規） |
| `tests/infrastructure/llm/test_response_generator.py` | テスト追加（修正） |

---

## 依存関係

- タスク 04a（ChannelMessages と Context の構造変更）に依存
- タスク 06（GenerateMemoryUseCase）に依存（記憶が生成されていること）

---

## Jinja2 テンプレート

### テンプレートファイル配置

```
src/myao2/infrastructure/llm/templates/
└── system_prompt.j2
```

### テンプレート内容

```jinja2
{{ persona.system_prompt }}

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

### トップレベル

{% for msg in top_level_messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user_name }}:
{{ msg.text }}

{% endfor %}
{% for thread_ts, thread_msgs in thread_messages.items() %}
### スレッド: {{ thread_ts }}

{% for msg in thread_msgs %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user_name }}:
{{ msg.text }}

{% endfor %}
{% endfor %}
{% if target_thread_ts %}
### 返信対象スレッド: {{ target_thread_ts }}

{% for msg in target_thread_messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user_name }}:
{{ msg.text }}

{% endfor %}
{% else %}
### 返信対象: トップレベル

{% for msg in top_level_messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user_name }}:
{{ msg.text }}

{% endfor %}
{% endif %}
---
上記の情報をもとに、返信対象スレッドに返答してください。
```

### カスタムフィルター

Jinja2 環境に以下のカスタムフィルターを登録する：

```python
def format_timestamp(timestamp: str) -> str:
    """タイムスタンプをフォーマットする"""
    # Slack タイムスタンプ（例: "1234567890.123456"）を
    # 読みやすい形式（例: "2024-01-01 12:00:00"）に変換
    ...
```

---

## 変更内容

### LiteLLMResponseGenerator クラスの拡張

```python
from jinja2 import Environment, PackageLoader, select_autoescape

class LiteLLMResponseGenerator(ResponseGenerator):
    def __init__(
        self,
        client: LLMClient,
        *,
        debug_llm_messages: bool = False,
    ) -> None:
        self._client = client
        self._debug_llm_messages = debug_llm_messages
        self._jinja_env = self._create_jinja_env()
        self._template = self._jinja_env.get_template("system_prompt.j2")

    def _create_jinja_env(self) -> Environment:
        """Jinja2 環境を作成する"""
        env = Environment(
            loader=PackageLoader("myao2.infrastructure.llm", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["format_timestamp"] = self._format_timestamp
        return env

    @staticmethod
    def _format_timestamp(timestamp: str) -> str:
        """タイムスタンプを読みやすい形式に変換する"""
        from datetime import datetime
        ts = float(timestamp.split(".")[0])
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
```

### _build_system_prompt メソッドの変更

```python
def _build_system_prompt(
    self,
    user_message: Message,
    context: Context,
) -> str:
    """system prompt を構築する"""
    channel_messages = context.conversation_history

    # 返信対象スレッドのメッセージを取得
    target_thread_messages = []
    if context.target_thread_ts:
        target_thread_messages = channel_messages.get_thread(context.target_thread_ts)
    else:
        target_thread_messages = channel_messages.top_level_messages

    # テンプレートに渡すコンテキスト
    template_context = {
        "persona": context.persona,
        "workspace_long_term_memory": context.workspace_long_term_memory,
        "workspace_short_term_memory": context.workspace_short_term_memory,
        "channel_memories": context.channel_memories,
        "current_channel_name": channel_messages.channel_name,
        "top_level_messages": channel_messages.top_level_messages,
        "thread_messages": channel_messages.thread_messages,
        "target_thread_ts": context.target_thread_ts,
        "target_thread_messages": target_thread_messages,
    }

    return self._template.render(**template_context)
```

---

## System Prompt 構成

### 完全な記憶あり

```
{persona.system_prompt}

## 記憶

### ワークスペースの歴史
{workspace_long_term_memory}

### ワークスペースの最近の出来事
{workspace_short_term_memory}

## チャンネル情報

あなたが参加しているチャンネルは以下です。

- #general
- #random
- #dev

現在、あなたは #general にいます。

## 各チャンネルの記憶

### #general

#### 歴史
{general_long_term_memory}

#### 最近の出来事
{general_short_term_memory}

### #random

#### 歴史
{random_long_term_memory}

## 現在の会話

現在は、#general チャンネルにいます。
直近の会話は以下の通りです。

### トップレベル

**2024-01-02 12:00:00** user1:
メッセージ1

**2024-01-03 12:01:00** user2:
メッセージ2

### スレッド: 1234567890.000000

**2024-01-01 12:00:00** user1:
メッセージ1

**2024-01-01 12:01:00** user2:
メッセージ2

### 返信対象スレッド: 1234567890.000000

**2024-01-01 12:00:00** user1:
メッセージ1

**2024-01-01 12:01:00** user2:
メッセージ2

---
上記の情報をもとに、返信対象スレッドに返答してください。
```

### 記憶なし（従来互換）

```
{persona.system_prompt}

## 現在の会話

現在は、#general チャンネルにいます。
直近の会話は以下の通りです。

### トップレベル

**2024-01-01 12:00:00** user1:
メッセージ1

### 返信対象: トップレベル

**2024-01-01 12:00:00** user1:
メッセージ1

---
上記の情報をもとに、返信対象スレッドに返答してください。
```

---

## 記憶の優先順位

System prompt に含める記憶の順序：

1. **ワークスペースの長期記憶** - 最も広いコンテキスト
2. **ワークスペースの短期記憶** - ワークスペース全体の直近の状況
3. **チャンネル一覧** - 参加チャンネルの把握
4. **各チャンネルの記憶** - チャンネルごとの歴史と直近の状況
5. **現在の会話** - 全メッセージ（トップレベル＋スレッド）
6. **返信対象スレッド** - 返答対象の具体的なメッセージ

この順序により、LLM は広いコンテキストから狭いコンテキストへと理解を深められる。

---

## 設計上の考慮事項

### トークン使用量

- 記憶が多い場合、system prompt のトークン数が増加
- 各記憶は MemoryConfig の max_tokens で制限済み
- 必要に応じて将来的にトークン制限を追加

### 後方互換性

- **破壊的変更**: Context の構造が変わるため、既存コードの修正が必要
- 新しい Context 構造に対応した実装が必要

### ログ

- 記憶が使用された場合はデバッグログを出力

### Jinja2 採用理由

- テンプレートがコードから分離され、レビューが容易
- 条件分岐やループが可読性高く表現できる
- テンプレートの変更が実装に影響しない

---

## テストケース

### テンプレートレンダリング

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 全記憶あり | 全フィールド設定 | 全セクションが prompt に含まれる |
| 記憶なし | 記憶フィールドが空 | 現在の会話のみ含まれる |
| ワークスペース記憶のみ | workspace_*_memory のみ設定 | 記憶セクションのみ含まれる |

### _build_system_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッド返信 | target_thread_ts 設定 | 返信対象スレッドが表示 |
| トップレベル返信 | target_thread_ts が None | 返信対象: トップレベルが表示 |
| チャンネル記憶あり | channel_memories 設定 | チャンネル一覧と各チャンネルの記憶が表示 |

### format_timestamp フィルター

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 通常タイムスタンプ | "1234567890.123456" | "2009-02-14 08:31:30" 形式 |
| 整数のみ | "1234567890" | "2009-02-14 08:31:30" 形式 |

---

## AutonomousResponseUseCase での記憶取得

### 変更箇所

`AutonomousResponseUseCase` で Context を構築する際に、MemoryRepository から記憶を取得する。

```python
async def _build_context_with_memory(
    self,
    channel: Channel,
    thread_ts: str | None,
    channel_messages: ChannelMessages,
) -> Context:
    """記憶を含む Context を構築する"""
    # ワークスペース記憶を取得
    ws_long_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE,
        GenerateMemoryUseCase.WORKSPACE_SCOPE_ID,
        MemoryType.LONG_TERM,
    )
    ws_short_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE,
        GenerateMemoryUseCase.WORKSPACE_SCOPE_ID,
        MemoryType.SHORT_TERM,
    )

    # アクティブなチャンネルの記憶を取得
    channel_memories = await self._build_channel_memories()

    return Context(
        persona=self._persona_config,
        conversation_history=channel_messages,
        workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
        workspace_short_term_memory=ws_short_term.content if ws_short_term else None,
        channel_memories=channel_memories,
        target_thread_ts=thread_ts,
    )

async def _build_channel_memories(self) -> dict[str, ChannelMemory]:
    """アクティブなチャンネルの記憶を構築する"""
    channel_memories: dict[str, ChannelMemory] = {}

    # アクティブなチャンネルを取得（active_channel_days 以内にメッセージがあるチャンネル）
    active_channels = await self._get_active_channels()

    for channel in active_channels:
        long_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            channel.id,
            MemoryType.LONG_TERM,
        )
        short_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL,
            channel.id,
            MemoryType.SHORT_TERM,
        )

        channel_memories[channel.id] = ChannelMemory(
            channel_id=channel.id,
            channel_name=channel.name,
            long_term_memory=long_term.content if long_term else None,
            short_term_memory=short_term.content if short_term else None,
        )

    return channel_memories
```

---

## JudgeResponse のプロンプト

JudgeResponse では、プロンプトの最後の指示部分を以下のように変更：

```python
# 応答生成用
"上記の情報をもとに、返信対象スレッドに返答してください。"

# 判断用（JudgeResponse）
"上記の情報を元に、この会話に返答すべきかどうかを判断してください。"
```

---

## 完了基準

- [x] Jinja2 テンプレートファイルが作成されている
- [x] _build_system_prompt がテンプレートを使用して構築される
- [x] format_timestamp フィルターが実装されている
- [x] 記憶の順序が正しい（広いスコープ → 狭いスコープ）
- [x] 記憶がない場合は現在の会話のみ表示される
- [x] 返信対象スレッドが正しく表示される
- [x] 新しいテストケースが通過する
