# 08: ResponseGenerator への記憶組み込み

## 目的

LiteLLMResponseGenerator を拡張し、記憶を system prompt に含める。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/response_generator.py` | 記憶組み込み（修正） |
| `tests/infrastructure/llm/test_response_generator.py` | 記憶組み込みテスト追加（修正） |

---

## 依存関係

- タスク 04（Context への記憶フィールド追加）に依存
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

    # 2. 長期記憶（新規追加）
    memory_section = self._build_memory_section(context)
    if memory_section:
        parts.append(memory_section)

    # 3. 会話履歴
    if context.conversation_history:
        parts.append("## 会話履歴")
        parts.append(self._format_conversation_history(context.conversation_history))

    # 4. 返答すべきメッセージ
    parts.append("## 返答すべきメッセージ")
    parts.append(self._format_message_with_metadata(user_message))

    # 5. 他チャンネルのメッセージ
    if context.other_channel_messages:
        parts.append("## 他のチャンネルでの最近の会話")
        parts.append(self._format_other_channels(context.other_channel_messages))

    # 6. 指示
    parts.append("---")
    parts.append(
        "上記の情報を元に、「返答すべきメッセージ」に対して自然な返答を生成してください。"
    )

    return "\n\n".join(parts)
```

### _build_memory_section メソッド

```python
def _build_memory_section(self, context: Context) -> str | None:
    """記憶セクションを構築する

    Args:
        context: コンテキスト

    Returns:
        記憶セクションの文字列、または記憶がない場合は None
    """
    sections: list[str] = []

    # ワークスペースの長期記憶
    if context.workspace_long_term_memory:
        sections.append("### ワークスペースの歴史")
        sections.append(context.workspace_long_term_memory)

    # ワークスペースの短期記憶
    if context.workspace_short_term_memory:
        sections.append("### ワークスペースの最近の出来事")
        sections.append(context.workspace_short_term_memory)

    # チャンネルの長期記憶
    if context.channel_long_term_memory:
        sections.append("### このチャンネルの歴史")
        sections.append(context.channel_long_term_memory)

    # チャンネルの短期記憶
    if context.channel_short_term_memory:
        sections.append("### このチャンネルの最近の出来事")
        sections.append(context.channel_short_term_memory)

    # スレッドの記憶
    if context.thread_memory:
        sections.append("### このスレッドの要約")
        sections.append(context.thread_memory)

    if not sections:
        return None

    return "## 記憶\n\n" + "\n\n".join(sections)
```

---

## System Prompt 構成

### 記憶あり

```
{persona.system_prompt}

## 記憶

### ワークスペースの歴史
{workspace_long_term_memory}

### ワークスペースの最近の出来事
{workspace_short_term_memory}

### このチャンネルの歴史
{channel_long_term_memory}

### このチャンネルの最近の出来事
{channel_short_term_memory}

### このスレッドの要約
{thread_memory}

## 会話履歴
{conversation_history}

## 返答すべきメッセージ
{current_message}

## 他のチャンネルでの最近の会話
{other_channels}

---
上記の情報を元に、「返答すべきメッセージ」に対して自然な返答を生成してください。
```

### 記憶なし（従来通り）

```
{persona.system_prompt}

## 会話履歴
{conversation_history}

## 返答すべきメッセージ
{current_message}

## 他のチャンネルでの最近の会話
{other_channels}

---
上記の情報を元に、「返答すべきメッセージ」に対して自然な返答を生成してください。
```

---

## 記憶の優先順位

System prompt に含める記憶の順序：

1. **ワークスペースの長期記憶** - 最も広いコンテキスト
2. **ワークスペースの短期記憶** - ワークスペース全体の直近の状況
3. **チャンネルの長期記憶** - このチャンネルの歴史
4. **チャンネルの短期記憶** - このチャンネルの直近の状況
5. **スレッドの記憶** - 最も具体的なコンテキスト

この順序により、LLM は広いコンテキストから狭いコンテキストへと理解を深められる。

---

## 設計上の考慮事項

### トークン使用量

- 記憶が多い場合、system prompt のトークン数が増加
- 各記憶は MemoryConfig の max_tokens で制限済み
- 必要に応じて将来的にトークン制限を追加

### 後方互換性

- 記憶フィールドが None の場合は従来の動作
- 既存のテストが引き続き通過する必要がある

### ログ

- 記憶が使用された場合はデバッグログを出力

---

## テストケース

### _build_memory_section

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 全記憶あり | 5つの記憶すべて設定 | 全記憶がセクションに含まれる |
| 部分記憶 | 一部の記憶のみ設定 | 設定された記憶のみ含まれる |
| 記憶なし | 全記憶が None | None が返る |

### _build_system_prompt

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 記憶あり | 記憶フィールドが設定 | 記憶セクションが prompt に含まれる |
| 記憶なし | 記憶フィールドが None | 記憶セクションが含まれない |
| 後方互換 | 従来の Context | 従来通りの prompt |

### generate

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 記憶あり生成 | 記憶を含む Context | 記憶を考慮した応答 |
| 記憶なし生成 | 記憶なしの Context | 従来通りの応答 |

---

## AutonomousResponseUseCase での記憶取得

### 変更箇所

`AutonomousResponseUseCase` で Context を構築する際に、MemoryRepository から記憶を取得する。

```python
async def _build_context_with_memory(
    self,
    channel_id: str,
    thread_ts: str | None,
    conversation_history: list[Message],
    other_channel_messages: dict[str, list[Message]],
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

    # チャンネル記憶を取得
    ch_long_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.CHANNEL,
        channel_id,
        MemoryType.LONG_TERM,
    )
    ch_short_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.CHANNEL,
        channel_id,
        MemoryType.SHORT_TERM,
    )

    # スレッド記憶を取得（スレッドの場合のみ）
    thread_memory = None
    if thread_ts:
        scope_id = make_thread_scope_id(channel_id, thread_ts)
        thread_mem = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.THREAD,
            scope_id,
            MemoryType.SHORT_TERM,
        )
        thread_memory = thread_mem.content if thread_mem else None

    return Context(
        persona=self._persona_config,
        conversation_history=conversation_history,
        other_channel_messages=other_channel_messages,
        workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
        workspace_short_term_memory=ws_short_term.content if ws_short_term else None,
        channel_long_term_memory=ch_long_term.content if ch_long_term else None,
        channel_short_term_memory=ch_short_term.content if ch_short_term else None,
        thread_memory=thread_memory,
    )
```

---

## 完了基準

- [ ] _build_memory_section メソッドが実装されている
- [ ] _build_system_prompt で記憶セクションが含まれる
- [ ] 記憶の順序が正しい
- [ ] 記憶がない場合は従来通りの動作
- [ ] 既存のテストが引き続き通過する
- [ ] 新しいテストケースが通過する
