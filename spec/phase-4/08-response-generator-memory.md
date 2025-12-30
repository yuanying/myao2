# 08: ResponseGenerator への記憶組み込み

> **注意**: この設計書は [04a-channel-messages-and-context.md](./04a-channel-messages-and-context.md) の変更に伴い更新されました。

## 目的

LiteLLMResponseGenerator を拡張し、記憶とチャンネル情報を system prompt に含める。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/response_generator.py` | 記憶・チャンネル情報組み込み（修正） |
| `tests/infrastructure/llm/test_response_generator.py` | テスト追加（修正） |

---

## 依存関係

- タスク 04a（ChannelMessages と Context の構造変更）に依存
- タスク 06（GenerateMemoryUseCase）に依存（記憶が生成されていること）

---

## 変更内容

### _build_system_prompt メソッドの拡張

```python
def _build_system_prompt(
    self,
    user_message: Message,
    context: Context,
) -> str:
    """system prompt を構築する"""
    parts: list[str] = []

    # 1. ペルソナ
    parts.append(context.persona.system_prompt)

    # 2. ワークスペース記憶
    workspace_memory = self._build_workspace_memory_section(context)
    if workspace_memory:
        parts.append(workspace_memory)

    # 3. チャンネル一覧
    channel_list = self._build_channel_list_section(context)
    if channel_list:
        parts.append(channel_list)

    # 4. 各チャンネルの記憶
    channel_memories = self._build_channel_memories_section(context)
    if channel_memories:
        parts.append(channel_memories)

    # 5. スレッド一覧と要約
    thread_memories = self._build_thread_memories_section(context)
    if thread_memories:
        parts.append(thread_memories)

    # 6. 現在の会話
    current_conversation = self._build_current_conversation_section(context)
    parts.append(current_conversation)

    # 7. 指示
    parts.append("---")
    parts.append(
        "上記の情報をもとに、現在の会話に返答してください。"
    )

    return "\n\n".join(parts)
```

### _build_workspace_memory_section メソッド

```python
def _build_workspace_memory_section(self, context: Context) -> str | None:
    """ワークスペース記憶セクションを構築する"""
    sections: list[str] = []

    if context.workspace_long_term_memory:
        sections.append("### ワークスペースの歴史")
        sections.append(context.workspace_long_term_memory)

    if context.workspace_short_term_memory:
        sections.append("### ワークスペースの最近の出来事")
        sections.append(context.workspace_short_term_memory)

    if not sections:
        return None

    return "## 記憶\n\n" + "\n\n".join(sections)
```

### _build_channel_list_section メソッド

```python
def _build_channel_list_section(self, context: Context) -> str | None:
    """チャンネル一覧セクションを構築する"""
    if not context.channel_memories:
        return None

    lines: list[str] = ["## チャンネル情報", ""]
    lines.append("あなたが参加しているチャンネルは以下です。")
    lines.append("")

    for channel_memory in context.channel_memories.values():
        lines.append(f"- #{channel_memory.channel_name}")

    lines.append("")
    lines.append(
        f"現在、あなたは #{context.conversation_history.channel_name} にいます。"
    )

    return "\n".join(lines)
```

### _build_channel_memories_section メソッド

```python
def _build_channel_memories_section(self, context: Context) -> str | None:
    """各チャンネルの記憶セクションを構築する"""
    if not context.channel_memories:
        return None

    sections: list[str] = ["## 各チャンネルの記憶"]

    for channel_memory in context.channel_memories.values():
        if not channel_memory.long_term_memory and not channel_memory.short_term_memory:
            continue

        sections.append(f"### #{channel_memory.channel_name}")

        if channel_memory.long_term_memory:
            sections.append("#### 歴史")
            sections.append(channel_memory.long_term_memory)

        if channel_memory.short_term_memory:
            sections.append("#### 最近の出来事")
            sections.append(channel_memory.short_term_memory)

    if len(sections) == 1:  # ヘッダーのみ
        return None

    return "\n\n".join(sections)
```

### _build_thread_memories_section メソッド

```python
def _build_thread_memories_section(self, context: Context) -> str | None:
    """スレッド一覧と要約セクションを構築する"""
    if not context.thread_memories:
        return None

    sections: list[str] = ["## 現在のスレッド一覧"]

    for thread_ts, memory in context.thread_memories.items():
        sections.append(f"### スレッド: {thread_ts}")
        sections.append(memory)

    return "\n\n".join(sections)
```

### _build_current_conversation_section メソッド

```python
def _build_current_conversation_section(self, context: Context) -> str:
    """現在の会話セクションを構築する"""
    channel_messages = context.conversation_history
    sections: list[str] = ["## 現在の会話"]
    sections.append(f"### #{channel_messages.channel_name}")

    if context.target_thread_ts:
        # スレッドが対象
        sections.append(f"#### スレッド: {context.target_thread_ts}")
        thread_msgs = channel_messages.get_thread(context.target_thread_ts)
        for msg in thread_msgs:
            sections.append(self._format_message_with_metadata(msg))
    else:
        # トップレベルが対象
        sections.append("#### トップレベルメッセージ")
        for msg in channel_messages.top_level_messages:
            sections.append(self._format_message_with_metadata(msg))

    return "\n\n".join(sections)
```

---

## System Prompt 構成（新）

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

## 現在のスレッド一覧

### スレッド: 1234567890.000000
{thread_summary_1}

### スレッド: 1234567891.000000
{thread_summary_2}

## 現在の会話

### #general

#### スレッド: 1234567890.000000

**2024-01-01 12:00:00** user1:
メッセージ1

**2024-01-01 12:01:00** user2:
メッセージ2

---
上記の情報をもとに、現在の会話に返答してください。
```

### 記憶なし（従来互換）

```
{persona.system_prompt}

## 現在の会話

### #general

#### トップレベルメッセージ

**2024-01-01 12:00:00** user1:
メッセージ1

---
上記の情報をもとに、現在の会話に返答してください。
```

---

## 記憶の優先順位

System prompt に含める記憶の順序：

1. **ワークスペースの長期記憶** - 最も広いコンテキスト
2. **ワークスペースの短期記憶** - ワークスペース全体の直近の状況
3. **チャンネル一覧** - 参加チャンネルの把握
4. **各チャンネルの記憶** - チャンネルごとの歴史と直近の状況
5. **スレッド一覧と要約** - 現在進行中のスレッド
6. **現在の会話** - 返答対象の具体的なメッセージ

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

---

## テストケース

### _build_workspace_memory_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 両方あり | 長期・短期記憶あり | 両方がセクションに含まれる |
| 長期のみ | 長期記憶のみ | 長期記憶のみ含まれる |
| 記憶なし | 両方 None | None が返る |

### _build_channel_list_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数チャンネル | 3チャンネル分の記憶 | 全チャンネルがリストに含まれる |
| チャンネルなし | channel_memories が空 | None が返る |

### _build_channel_memories_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数チャンネル | 各チャンネルに記憶 | 全チャンネルの記憶が含まれる |
| 一部のみ | 一部のチャンネルのみ記憶 | 記憶があるチャンネルのみ含まれる |
| 記憶なし | channel_memories が空 | None が返る |

### _build_thread_memories_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数スレッド | 3スレッド分の要約 | 全スレッドが含まれる |
| スレッドなし | thread_memories が空 | None が返る |

### _build_current_conversation_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッド対象 | target_thread_ts 設定 | スレッドメッセージが表示 |
| トップレベル対象 | target_thread_ts が None | トップレベルメッセージが表示 |

### _build_system_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 全記憶あり | 全フィールド設定 | 全セクションが prompt に含まれる |
| 記憶なし | 記憶フィールドが空 | 現在の会話のみ含まれる |

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

    # 直近のスレッド記憶を取得
    thread_memories = await self._build_thread_memories(channel.id)

    return Context(
        persona=self._persona_config,
        conversation_history=channel_messages,
        workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
        workspace_short_term_memory=ws_short_term.content if ws_short_term else None,
        channel_memories=channel_memories,
        thread_memories=thread_memories,
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

async def _build_thread_memories(self, channel_id: str) -> dict[str, str]:
    """直近のスレッド記憶を構築する"""
    thread_memories: dict[str, str] = {}

    # thread_memory_days 以内のスレッド記憶を取得
    memories = await self._memory_repository.find_recent_thread_memories(
        channel_id=channel_id,
        days=self._response_config.thread_memory_days,
    )

    for memory in memories:
        _, thread_ts = parse_thread_scope_id(memory.scope_id)
        thread_memories[thread_ts] = memory.content

    return thread_memories
```

---

## JudgeResponse のプロンプト

JudgeResponse では、プロンプトの最後の指示部分を以下のように変更：

```python
# 応答生成用
"上記の情報をもとに、現在の会話に返答してください。"

# 判断用（JudgeResponse）
"上記の情報を元に、この会話に返答すべきかどうかを判断してください。"
```

---

## 完了基準

- [ ] _build_workspace_memory_section メソッドが実装されている
- [ ] _build_channel_list_section メソッドが実装されている
- [ ] _build_channel_memories_section メソッドが実装されている
- [ ] _build_thread_memories_section メソッドが実装されている
- [ ] _build_current_conversation_section メソッドが実装されている
- [ ] _build_system_prompt で全セクションが正しく構築される
- [ ] 記憶の順序が正しい（広いスコープ → 狭いスコープ）
- [ ] 記憶がない場合は現在の会話のみ表示される
- [ ] 新しいテストケースが通過する
