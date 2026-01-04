# extra08e: StrandsMemorySummarizer の実装

## 目的

MemorySummarizer Protocol の strands-agents ベース実装を作成する。
テンプレートを system_prompt（固定）と query_prompt（動的）に分割する。

---

## 背景

### 現状

| 項目 | 現在の実装 |
|------|----------|
| クラス名 | LLMMemorySummarizer |
| LLM呼び出し | LLMClient.complete() |
| テンプレート | memory_prompt.j2（scope/memory_type で条件分岐） |

### 問題点

1. LiteLLM を直接使用しており、strands-agents への移行が必要
2. 全ての情報を1つのプロンプトに詰め込んでおり、system/user の分離ができていない

### 解決方針

- strands-agents の Agent を使用
- テンプレートを system_prompt（固定）と query_prompt（動的）に分割
- Model は保持し、Agent はリクエストごとに生成
- scope/memory_type 別の要約指針は system_prompt に含める

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/strands/memory_summarizer.py` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/memory_system.j2` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/memory_query.j2` | 新規作成 |
| `tests/infrastructure/llm/strands/test_memory_summarizer.py` | 新規作成 |

---

## テンプレート設計

### memory_system.j2（固定部分）

```jinja2
{{ persona.system_prompt }}
{% if agent_system_prompt %}

{{ agent_system_prompt }}
{% endif %}

あなたは会話履歴を要約するアシスタントです。

## 要約の基本ルール

- 要約は箇条書きで、簡潔かつ具体的に記述してください
- 重要なトピックや決定事項を優先してください
- 参加者の傾向や特徴を記録してください

{% if memory_type == "long_term" %}
## 長期記憶の要約指針

以下の点を踏まえて、時系列で出来事を整理してください：
- 重要なトピックや決定事項
- 参加者の傾向や特徴
- 繰り返し登場するテーマ
- 具体的な日時を含める

{% elif memory_type == "short_term" %}
## 短期記憶の要約指針

以下の点を踏まえて要約してください：
- 現在進行中のテーマや話題
- 直近の質問や未解決事項
- 参加者の最近の関心事

{% endif %}
{% if scope == "workspace" %}
## ワークスペーススコープ

チャンネル横断的なトピック、重要プロジェクト、組織全体の動向をまとめてください。

{% elif scope == "channel" %}
## チャンネルスコープ

このチャンネル固有のトピック、議論、傾向をまとめてください。

{% elif scope == "thread" %}
## スレッドスコープ

このスレッドの議論内容、結論、未解決事項をまとめてください。

{% endif %}
```

### memory_query.j2（動的部分）

```jinja2
{% macro render_messages(messages) %}
{% for msg in messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user.name }}:
{{ msg.text }}

{% endfor %}
{% endmacro %}
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

{% if target_thread_ts and top_level_messages %}
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
要約対象の内容を要約してください。

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
要約対象のチャンネルの会話を要約してください。

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

{% endif %}
{% endif %}
```

---

## 実装詳細

### StrandsMemorySummarizer

```python
from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig, MemoryConfig
from myao2.domain.entities import Context, MemoryScope, MemoryType
from myao2.domain.services.protocols import MemorySummarizer
from myao2.infrastructure.llm.strands import map_strands_exception
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class StrandsMemorySummarizer:
    """strands-agents ベースの MemorySummarizer 実装"""

    def __init__(
        self,
        model: LiteLLMModel,
        config: MemoryConfig,
        agent_config: AgentConfig | None = None,
    ) -> None:
        """初期化

        Args:
            model: LiteLLMModel インスタンス（再利用される）
            config: メモリ設定
            agent_config: Agent 設定（オプション、system_prompt 等を含む）
        """
        self._model = model
        self._config = config
        self._agent_config = agent_config
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("memory_system.j2")
        self._query_template = self._jinja_env.get_template("memory_query.j2")

    async def summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        """記憶を要約

        Args:
            context: 会話コンテキスト
            scope: 要約スコープ（THREAD, CHANNEL, WORKSPACE）
            memory_type: 記憶タイプ（SHORT_TERM, LONG_TERM）
            existing_memory: 既存の記憶（統合用）

        Returns:
            要約されたテキスト
        """
        if not self._has_content_to_summarize(context, scope, memory_type):
            return existing_memory or ""

        system_prompt = self._build_system_prompt(context, scope, memory_type)
        query_prompt = self._build_query_prompt(
            context, scope, memory_type, existing_memory
        )

        # Agent をリクエストごとに生成
        agent = Agent(
            model=self._model,
            system_prompt=system_prompt,
        )

        try:
            result = await agent.invoke_async(query_prompt)
            return str(result)
        except Exception as e:
            raise map_strands_exception(e)

    def _build_system_prompt(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> str:
        """システムプロンプト（固定部分）を構築"""
        agent_system_prompt = (
            self._agent_config.system_prompt if self._agent_config else None
        )
        return self._system_template.render(
            persona=context.persona,
            agent_system_prompt=agent_system_prompt,
            scope=scope.value.lower(),
            memory_type=memory_type.value.lower(),
        )

    def _build_query_prompt(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None,
    ) -> str:
        """クエリプロンプト（動的部分）を構築"""
        return self._query_template.render(
            scope=scope.value.lower(),
            memory_type=memory_type.value.lower(),
            existing_memory=existing_memory,
            workspace_long_term_memory=context.workspace_long_term_memory,
            workspace_short_term_memory=context.workspace_short_term_memory,
            channel_memories=context.channel_memories,
            current_channel_name=context.current_channel_name,
            top_level_messages=context.top_level_messages,
            thread_messages=context.thread_messages,
            target_thread_ts=context.target_thread_ts,
            target_thread_messages=context.target_thread_messages,
            channel_short_term_memory=self._get_channel_short_term_memory(context),
        )

    def _has_content_to_summarize(
        self,
        context: Context,
        scope: MemoryScope,
        memory_type: MemoryType,
    ) -> bool:
        """要約すべきコンテンツがあるか確認"""
        # 既存実装と同じロジック
        ...

    def _get_channel_short_term_memory(self, context: Context) -> str | None:
        """現在チャンネルの短期記憶を取得"""
        if not context.channel_memories:
            return None
        for channel in context.channel_memories.values():
            if channel.channel_name == context.current_channel_name:
                return channel.short_term_memory
        return None

    def _get_max_tokens(self, memory_type: MemoryType) -> int:
        """memory_type に応じた max_tokens を取得"""
        if memory_type == MemoryType.LONG_TERM:
            return self._config.long_term_summary_max_tokens
        return self._config.short_term_summary_max_tokens
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| summarize | THREAD scope | スレッド要約が返される |
| summarize | CHANNEL scope, SHORT_TERM | チャンネル短期記憶が返される |
| summarize | CHANNEL scope, LONG_TERM | チャンネル長期記憶が統合される |
| summarize | WORKSPACE scope, SHORT_TERM | ワークスペース短期記憶が返される |
| summarize | WORKSPACE scope, LONG_TERM | ワークスペース長期記憶が統合される |
| summarize | 要約対象なし | 既存記憶または空文字が返される |
| _build_system_prompt | scope/memory_type 設定 | 適切な指針が含まれる |
| _build_query_prompt | existing_memory あり | 既存記憶セクションが含まれる |
| summarize | LLMエラー発生 | map_strands_exception で変換される |

---

## 完了基準

- [ ] StrandsMemorySummarizer が MemorySummarizer Protocol を実装している
- [ ] memory_system.j2 が作成されている
- [ ] memory_query.j2 が作成されている
- [ ] scope/memory_type に応じた適切なプロンプトが生成される
- [ ] Model は保持され、Agent はリクエストごとに生成される
- [ ] 例外が map_strands_exception で変換される
- [ ] 全テストが通過する
