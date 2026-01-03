# extra05b: ResponseJudgmentのシステムプロンプト方式への変更

## 目的

ResponseJudgmentのLLM呼び出し方式をResponseGeneratorと同様に、システムプロンプトのみで全ての情報を渡す方式に統一する。
また、判定対象をメッセージ単位からスレッド単位に変更し、ワークスペース・チャンネルレベルの記憶情報をコンテキストに含めることで、より文脈を理解した判定を可能にする。

## 背景

### 現状

| 項目 | ResponseGenerator | ResponseJudgment |
|-----|------------------|------------------|
| LLMメッセージ形式 | `[{"role": "system", ...}]` | `[{"role": "system", ...}, {"role": "user", ...}]` |
| コンテキスト渡し方 | システムプロンプトに全情報を含める | システムプロンプトは指示のみ、ユーザーメッセージに会話履歴 |
| 周辺情報の扱い | WS記憶、CH記憶を含む | 会話履歴のみ（記憶情報なし） |
| 判定/生成対象 | スレッド全体 | 最新メッセージのみ |

### 問題点

1. ResponseGeneratorとResponseJudgmentでLLM呼び出しのアーキテクチャが異なる
2. 判定時にワークスペース・チャンネルレベルの記憶情報が参照されない
3. 最新メッセージのみを判定対象としているため、スレッド全体の文脈が考慮されにくい
4. プロンプト構築ロジックがResponseGeneratorと異なる

### 解決方針

- ResponseGeneratorと同じアーキテクチャに統一
- システムプロンプトのみでコンテキスト全体を渡す
- 判定対象をスレッド全体に変更
- ワークスペース・チャンネルレベルの記憶情報を含める

## 実装するファイル

### インフラ層（LLM）

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `src/myao2/infrastructure/llm/templates/judgment_prompt.j2` | 全面改修: システムプロンプト方式対応 | 修正 |
| `src/myao2/infrastructure/llm/response_judgment.py` | システムプロンプトのみ使用に変更 | 修正 |

### アプリケーション層（UseCase）

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `src/myao2/application/use_cases/helpers.py` | Context構築関数の共通化（extra05aで対応済みの場合は確認のみ） | 修正/確認 |
| `src/myao2/application/use_cases/autonomous_response.py` | 共通のContext構築関数を確実に使用 | 確認 |

### テスト

| ファイル | 変更内容 | 状態 |
|---------|---------|------|
| `tests/infrastructure/llm/test_response_judgment.py` | 新しいプロンプト形式に対応 | 修正 |
| `tests/application/use_cases/test_autonomous_response.py` | Context構築の変更に対応 | 修正 |

## 依存関係

- タスク extra04（ResponseJudgment#judge インターフェース簡素化）に依存
- タスク extra05（Jinja2テンプレート化）に依存
- タスク extra05a（MemorySummarizer システムプロンプト方式）と並行可能

## インターフェース設計

### ResponseJudgment Protocol（変更なし）

既存の Protocol を維持する。呼び出し側の変更は不要。

```python
class ResponseJudgment(Protocol):
    """Response judgment service."""

    async def judge(
        self,
        context: Context,
    ) -> JudgmentResult:
        """Determine whether to respond.

        The target thread/message is identified by context.target_thread_ts.
        - If target_thread_ts is None, judges top-level messages
        - If target_thread_ts is set, judges the specified thread
        """
        ...
```

### JudgmentResult（変更なし）

```python
@dataclass(frozen=True)
class JudgmentResult:
    should_respond: bool
    reason: str
    confidence: float  # 0.0 - 1.0
```

## Context構築の共通化

### 現状

AutonomousResponseUseCase は既に `build_context_with_memory()` を使用している。
ResponseJudgment に渡される Context が完全な記憶情報を含んでいることを確認する。

### 確認事項

- `helpers.py` の `build_context_with_memory()` が以下を含むこと:
  - `workspace_long_term_memory`
  - `workspace_short_term_memory`
  - `channel_memories`（全チャンネルの長期・短期記憶）
  - `conversation_history`
  - `target_thread_ts`

## 判定対象の変更

### 現在の動作

```python
# 現在: 最新メッセージのみを判定対象として表示
user_content = f"会話履歴:\n{conversation}\n\n判定対象メッセージ:\n{target_msg}"
```

### 新しい動作

```python
# 変更後: スレッド全体を判定対象として表示（ResponseGeneratorと同様）
# システムプロンプト内に全情報を含める
```

## プロンプト設計（Jinja2テンプレート）

### judgment_prompt.j2 新構成

```jinja2
{% macro render_messages(messages) %}
{% for msg in messages %}
**{{ msg.timestamp | format_timestamp }}** {{ msg.user.name }}:
{{ msg.text }}

{% endfor %}
{% endmacro %}
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

上記の会話を分析し、{{ persona.name }}として応答すべきかを判断してください。

判断基準：
1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

以下の場合は応答しないでください：
- 明らかな独り言
- 活発な会話に無理に割り込む場合

必ずJSON形式で回答してください。他のテキストは含めないでください。
回答形式：
{"should_respond": true/false, "reason": "理由", "confidence": 0.0-1.0}

confidence について：
- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）
```

## プロンプト例

### 前提データ

```python
# Context の内容
persona.name = "みゃお"
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
}

target_thread_ts = "1709280000.000001"
current_time = "2024-03-01 12:00:00 UTC"
```

---

### スレッド判定の例

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

現在、あなたは #general にいます。

## 各チャンネルの記憶

### #general

#### 歴史
- チーム全体の連絡に使用
- 週次報告が行われる

#### 最近の出来事
- 今週の進捗報告が投稿された
- 新しいツールの導入検討中

## 現在の会話

現在は、#general チャンネルにいます。
直近の会話は以下の通りです。

### トップレベル

**2024-03-01 10:00:00** alice:
おはよう！

**2024-03-01 10:05:00** bob:
おはよう〜

## 判定対象スレッド: 1709280000.000001

**2024-03-01 10:10:00** alice:
今日のタスク確認しよう

**2024-03-01 10:15:00** bob:
了解、リスト共有するね

---
現在時刻: 2024-03-01 12:00:00 UTC

上記の会話を分析し、みゃおとして応答すべきかを判断してください。

判断基準：
1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

以下の場合は応答しないでください：
- 明らかな独り言
- 活発な会話に無理に割り込む場合

必ずJSON形式で回答してください。他のテキストは含めないでください。
回答形式：
{"should_respond": true/false, "reason": "理由", "confidence": 0.0-1.0}

confidence について：
- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）
```

---

### トップレベル判定の例（target_thread_ts = None）

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

現在、あなたは #general にいます。

## 各チャンネルの記憶

### #general

#### 歴史
- チーム全体の連絡に使用
- 週次報告が行われる

#### 最近の出来事
- 今週の進捗報告が投稿された
- 新しいツールの導入検討中

## 現在の会話

現在は、#general チャンネルにいます。
直近の会話は以下の通りです。

## 判定対象: トップレベル会話

**2024-03-01 10:00:00** alice:
おはよう！

**2024-03-01 10:05:00** bob:
おはよう〜

### スレッド: 1709280000.000001

**2024-03-01 10:10:00** alice:
今日のタスク確認しよう

**2024-03-01 10:15:00** bob:
了解、リスト共有するね

---
現在時刻: 2024-03-01 12:00:00 UTC

上記の会話を分析し、みゃおとして応答すべきかを判断してください。

（以下、判断基準は同様）
```

## LLMResponseJudgment 実装変更

### 主要な変更点

1. `_build_system_prompt()` メソッドを追加し、Jinja2テンプレートで全情報を含むシステムプロンプトを生成
2. LLM呼び出しを `[{"role": "system", ...}]` のみに変更
3. `format_timestamp` フィルターを追加
4. 判定対象をスレッド全体に変更

### 削除するメソッド

以下のメソッドは不要となり削除:
- `_build_messages()` （システムプロンプトに統合）
- `_get_target_message()` （スレッド全体を使用するため不要）
- `_format_message()` （テンプレート内マクロに移行）
- `_format_messages()` （テンプレート内マクロに移行）

### 新規追加メソッド

```python
def _build_system_prompt(self, context: Context) -> str:
    """Build system prompt using Jinja2 template."""
    channel_messages = context.conversation_history
    current_time = datetime.now(timezone.utc)

    # ターゲットスレッドのメッセージを取得
    target_thread_messages = []
    if context.target_thread_ts:
        target_thread_messages = channel_messages.get_thread(
            context.target_thread_ts
        )
    else:
        target_thread_messages = channel_messages.top_level_messages

    template_context = {
        "persona": context.persona,
        "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
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

## テストケース

### システムプロンプト構成

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッド判定 | target_thread_ts あり | WS記憶、CH記憶、会話履歴、判定対象スレッドがプロンプトに含まれる |
| トップレベル判定 | target_thread_ts が None | WS記憶、CH記憶、トップレベル会話が判定対象として含まれる |
| 判定対象の位置 | 通常ケース | 判定対象がプロンプトの最後に配置される |
| 記憶情報の包含 | 記憶あり | ResponseGeneratorと同等のコンテキストが含まれる |
| ペルソナ名 | 通常ケース | ペルソナ名が判定指示に含まれる |

### LLM呼び出し形式

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| メッセージ形式 | 任意のケース | `[{"role": "system", ...}]` のみ（user メッセージなし）|
| JSON解析 | 正常応答 | JudgmentResult が正しく生成される |
| JSON解析 | 不正応答 | should_respond=False でフォールバック |

### 判定対象の変更

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッド全体表示 | target_thread_ts あり | スレッドの全メッセージが表示される（最新のみではない） |
| トップレベル全体表示 | target_thread_ts が None | トップレベルの全メッセージが表示される |

## 完了基準

### ResponseJudgment（LLM層）

- [x] judgment_prompt.j2 がシステムプロンプト方式に対応している
- [x] LLMResponseJudgment がシステムプロンプトのみで呼び出している
- [x] 判定対象がスレッド全体になっている（最新メッセージのみではない）
- [x] ワークスペース記憶が含まれる
- [x] チャンネル記憶が含まれる
- [x] 会話履歴全体が含まれる
- [x] 判定対象スレッド/トップレベルが最後に配置される
- [x] ペルソナのシステムプロンプトが含まれる
- [x] 判定指示（JSON形式、判断基準）が含まれる
- [x] 既存の Protocol インターフェースが維持されている
- [x] format_timestamp フィルターが実装されている

### Context構築の共通化（UseCase層）

- [x] AutonomousResponseUseCase が `build_context_with_memory()` を使用している
- [x] ResponseJudgment に渡される Context が完全な記憶情報を含んでいる
- [x] ResponseGenerator、MemorySummarizer、ResponseJudgment で同一のContext構築関数を使用

### テスト

- [x] 全テストケースが通過する
- [x] 既存の判定キャッシュ機構が正常に動作する
