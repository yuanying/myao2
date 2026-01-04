# extra08c: StrandsResponseGenerator の実装

## 目的

ResponseGenerator Protocol の strands-agents ベース実装を作成する。
テンプレートを system_prompt（固定）と query_prompt（動的）に分割する。

---

## 背景

### 現状

| 項目 | 現在の実装 |
|------|----------|
| クラス名 | LiteLLMResponseGenerator |
| LLM呼び出し | LLMClient.complete() |
| テンプレート | system_prompt.j2（全て1つのプロンプトに結合） |

### 問題点

1. LiteLLM を直接使用しており、strands-agents への移行が必要
2. 全ての情報を1つのプロンプトに詰め込んでおり、system/user の分離ができていない

### 解決方針

- strands-agents の Agent を使用
- テンプレートを system_prompt（固定）と query_prompt（動的）に分割
- Model は保持し、Agent はリクエストごとに生成

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/strands/response_generator.py` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/response_system.j2` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/response_query.j2` | 新規作成 |
| `tests/infrastructure/llm/strands/test_response_generator.py` | 新規作成 |

---

## テンプレート設計

### response_system.j2（固定部分）

```jinja2
{{ persona.system_prompt }}
```

### response_query.j2（動的部分）

```jinja2
{% macro render_messages(messages) %}
{% for msg in messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user.name }}:
{{ msg.text }}

{% endfor %}
{% endmacro %}
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
{% if target_thread_ts %}
### 返信対象スレッド: {{ target_thread_ts }}

{{ render_messages(target_thread_messages) }}
{% else %}
### 返信対象: トップレベル

{{ render_messages(top_level_messages) }}
{% endif %}
---
{% if target_thread_ts %}
上記の情報をもとに、返信対象スレッドに返答してください。
{% else %}
上記の情報をもとに、返信対象メッセージに返答してください。
{% endif %}
```

---

## 実装詳細

### StrandsResponseGenerator

```python
from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.domain.entities import Context
from myao2.domain.services.protocols import ResponseGenerator
from myao2.infrastructure.llm.strands import map_strands_exception
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class StrandsResponseGenerator:
    """strands-agents ベースの ResponseGenerator 実装"""

    def __init__(self, model: LiteLLMModel) -> None:
        """初期化

        Args:
            model: LiteLLMModel インスタンス（再利用される）
        """
        self._model = model
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("response_system.j2")
        self._query_template = self._jinja_env.get_template("response_query.j2")

    async def generate(self, context: Context) -> str:
        """応答を生成

        Args:
            context: 会話コンテキスト

        Returns:
            生成された応答テキスト
        """
        system_prompt = self._build_system_prompt(context)
        query_prompt = self._build_query_prompt(context)

        # Agent をリクエストごとに生成（system_prompt が動的なため）
        agent = Agent(
            model=self._model,
            system_prompt=system_prompt,
        )

        try:
            result = await agent.invoke_async(query_prompt)
            return str(result)
        except Exception as e:
            raise map_strands_exception(e)

    def _build_system_prompt(self, context: Context) -> str:
        """システムプロンプト（固定部分）を構築"""
        return self._system_template.render(
            persona=context.persona,
        )

    def _build_query_prompt(self, context: Context) -> str:
        """クエリプロンプト（動的部分）を構築"""
        return self._query_template.render(
            workspace_long_term_memory=context.workspace_long_term_memory,
            workspace_short_term_memory=context.workspace_short_term_memory,
            channel_memories=context.channel_memories,
            current_channel_name=context.current_channel_name,
            top_level_messages=context.top_level_messages,
            thread_messages=context.thread_messages,
            target_thread_ts=context.target_thread_ts,
            target_thread_messages=context.target_thread_messages,
        )
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| generate | 正常な Context | 応答テキストが返される |
| generate | トップレベル返信 | 適切なプロンプトで Agent が呼び出される |
| generate | スレッド返信 | target_thread_ts が含まれるプロンプト |
| _build_system_prompt | ペルソナ設定あり | ペルソナの system_prompt が含まれる |
| _build_query_prompt | 記憶あり | 記憶セクションが含まれる |
| _build_query_prompt | 記憶なし | 記憶セクションが含まれない |
| _build_query_prompt | channel_memories あり | チャンネル情報が含まれる |
| generate | LLMエラー発生 | map_strands_exception で変換される |

---

## 完了基準

- [ ] StrandsResponseGenerator が ResponseGenerator Protocol を実装している
- [ ] response_system.j2 が作成されている
- [ ] response_query.j2 が作成されている
- [ ] Model は保持され、Agent はリクエストごとに生成される
- [ ] 例外が map_strands_exception で変換される
- [ ] 全テストが通過する
