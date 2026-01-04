# extra08d: StrandsResponseJudgment の実装

## 目的

ResponseJudgment Protocol の strands-agents ベース実装を作成する。
Structured Output を使用して型安全な JSON 出力を実現する。

---

## 背景

### 現状

| 項目 | 現在の実装 |
|------|----------|
| クラス名 | LLMResponseJudgment |
| LLM呼び出し | LLMClient.complete() |
| 出力形式 | プロンプトで JSON 形式を指示、正規表現でパース |
| テンプレート | judgment_prompt.j2（全て1つのプロンプトに結合） |

### 問題点

1. JSON パースロジックが複雑（埋め込み JSON の抽出等）
2. 型安全性がない
3. LiteLLM を直接使用しており、strands-agents への移行が必要

### 解決方針

- strands-agents の Structured Output を使用
- Pydantic モデルで出力スキーマを定義
- テンプレートを system_prompt（固定）と query_prompt（動的）に分割
- JSON 形式指定のプロンプトは不要（Structured Output が自動処理）

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/strands/response_judgment.py` | 新規作成 |
| `src/myao2/infrastructure/llm/strands/models.py` | Pydantic モデル定義 |
| `src/myao2/infrastructure/llm/templates/judgment_system.j2` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/judgment_query.j2` | 新規作成 |
| `tests/infrastructure/llm/strands/test_response_judgment.py` | 新規作成 |

---

## Pydantic モデル設計

### models.py

```python
from pydantic import BaseModel, Field


class JudgmentOutput(BaseModel):
    """応答判定の出力モデル

    strands-agents の Structured Output で使用される。
    """

    should_respond: bool = Field(
        description="応答すべきかどうか"
    )
    reason: str = Field(
        description="判断理由"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="確信度 (0.0-1.0)"
    )
```

---

## テンプレート設計

### judgment_system.j2（固定部分）

```jinja2
{{ persona.system_prompt }}

あなたは会話への参加判断を行います。

## 判断基準

1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

## 応答しない条件

- 明らかな独り言
- 活発な会話に無理に割り込む場合

## confidence について

- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）
```

### judgment_query.j2（動的部分）

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
{% for thread_ts, thread_msgs in thread_messages.items() %}
{% if thread_ts != target_thread_ts %}
### スレッド: {{ thread_ts }}

{{ render_messages(thread_msgs) }}
{% endif %}
{% endfor %}
## 判定対象スレッド: {{ target_thread_ts }}

{{ render_messages(target_thread_messages) }}
{% else %}
## 判定対象: トップレベル会話

{{ render_messages(top_level_messages) }}
{% for thread_ts, thread_msgs in thread_messages.items() %}
### スレッド: {{ thread_ts }}

{{ render_messages(thread_msgs) }}
{% endfor %}
{% endif %}
---
現在時刻: {{ current_time }}

上記の判定対象の会話を分析し、{{ persona.name }}として応答すべきかを判断してください。
```

---

## 実装詳細

### StrandsResponseJudgment

```python
from datetime import datetime, timezone

from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.domain.entities import Context, JudgmentResult
from myao2.domain.services.protocols import ResponseJudgment
from myao2.infrastructure.llm.strands import map_strands_exception
from myao2.infrastructure.llm.strands.models import JudgmentOutput
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp


class StrandsResponseJudgment:
    """strands-agents ベースの ResponseJudgment 実装

    Structured Output を使用して型安全な JSON 出力を実現する。
    """

    def __init__(self, model: LiteLLMModel) -> None:
        """初期化

        Args:
            model: LiteLLMModel インスタンス（再利用される）
        """
        self._model = model
        self._jinja_env = create_jinja_env()
        self._jinja_env.filters["format_timestamp"] = format_timestamp
        self._system_template = self._jinja_env.get_template("judgment_system.j2")
        self._query_template = self._jinja_env.get_template("judgment_query.j2")

    async def judge(self, context: Context) -> JudgmentResult:
        """応答判定を実行

        Args:
            context: 会話コンテキスト

        Returns:
            JudgmentResult（should_respond, reason, confidence）
        """
        system_prompt = self._build_system_prompt(context)
        query_prompt = self._build_query_prompt(context)

        # Agent をリクエストごとに生成
        agent = Agent(
            model=self._model,
            system_prompt=system_prompt,
        )

        try:
            # Structured Output を使用
            result = await agent.invoke_async(
                query_prompt,
                structured_output_model=JudgmentOutput,
            )
            output: JudgmentOutput = result.structured_output

            return JudgmentResult(
                should_respond=output.should_respond,
                reason=output.reason,
                confidence=output.confidence,
            )
        except Exception as e:
            raise map_strands_exception(e)

    def _build_system_prompt(self, context: Context) -> str:
        """システムプロンプト（固定部分）を構築"""
        return self._system_template.render(
            persona=context.persona,
        )

    def _build_query_prompt(self, context: Context) -> str:
        """クエリプロンプト（動的部分）を構築"""
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return self._query_template.render(
            workspace_long_term_memory=context.workspace_long_term_memory,
            workspace_short_term_memory=context.workspace_short_term_memory,
            channel_memories=context.channel_memories,
            current_channel_name=context.current_channel_name,
            top_level_messages=context.top_level_messages,
            thread_messages=context.thread_messages,
            target_thread_ts=context.target_thread_ts,
            target_thread_messages=context.target_thread_messages,
            current_time=current_time,
            persona=context.persona,
        )
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| judge | should_respond=True | JudgmentResult.should_respond が True |
| judge | should_respond=False | JudgmentResult.should_respond が False |
| judge | confidence 値 | 0.0-1.0 の範囲の値が返される |
| judge | reason が含まれる | JudgmentResult.reason に理由が設定される |
| _build_system_prompt | ペルソナ設定あり | 判断基準が含まれる |
| _build_query_prompt | 記憶あり | 記憶セクションが含まれる |
| _build_query_prompt | 現在時刻 | current_time が含まれる |
| judge | LLMエラー発生 | map_strands_exception で変換される |

---

## Structured Output の利点

1. **型安全性**: Pydantic モデルによる自動バリデーション
2. **パースロジック不要**: JSON 抽出・パースコードが不要
3. **信頼性向上**: スキーマに基づいた確実な出力形式
4. **コード簡素化**: エラーハンドリングの簡素化

---

## 完了基準

- [ ] JudgmentOutput Pydantic モデルが実装されている
- [ ] StrandsResponseJudgment が ResponseJudgment Protocol を実装している
- [ ] judgment_system.j2 が作成されている（JSON 形式指定なし）
- [ ] judgment_query.j2 が作成されている
- [ ] Structured Output を使用して型安全な出力を取得している
- [ ] JSON パースロジックが不要になっている
- [ ] 全テストが通過する
