# 01d: ResponseGenerator統合 - 詳細設計書

**Status**: ✅ Completed

## 概要

メモツールを ResponseGenerator に統合し、プロンプトテンプレートを更新する。

---

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/entities/context.py` | high_priority_memos, recent_memos フィールド追加 |
| `src/myao2/infrastructure/llm/strands/response_generator.py` | ツール統合 |
| `src/myao2/infrastructure/llm/templates/response_query.j2` | メモセクション追加 |
| `src/myao2/infrastructure/llm/templates/judgment_query.j2` | メモセクション追加 |
| `src/myao2/application/use_cases/autonomous_response.py` | メモ取得・Context設定 |
| `src/myao2/application/use_cases/reply_to_mention.py` | メモ取得・Context設定 |
| `src/myao2/__main__.py` | MemoRepository 初期化 |

---

## Context 変更

### 新規フィールド

```python
@dataclass(frozen=True)
class Context:
    # ... 既存フィールド ...
    high_priority_memos: list[Memo] = field(default_factory=list)
    recent_memos: list[Memo] = field(default_factory=list)
```

### 説明

| フィールド | 説明 |
|-----------|------|
| high_priority_memos | 優先度4以上のメモ（上限20件）|
| recent_memos | 直近5件のメモ（high_priority_memos との重複除外）|

---

## StrandsResponseGenerator 変更

### コンストラクタ

```python
class StrandsResponseGenerator:
    def __init__(
        self,
        model: LiteLLMModel,
        agent_config: AgentConfig | None = None,
        memo_tools_factory: MemoToolsFactory | None = None,  # 追加
    ) -> None:
        self._model = model
        self._agent_config = agent_config
        self._memo_tools_factory = memo_tools_factory
        # ... 既存の初期化 ...
```

### generate メソッド

```python
async def generate(self, context: Context) -> GenerationResult:
    system_prompt = self.build_system_prompt(context)
    query_prompt = self.build_query_prompt(context)

    # ツールの設定
    tools = []
    invocation_state = {}
    if self._memo_tools_factory:
        tools = self._memo_tools_factory.tools
        invocation_state = self._memo_tools_factory.get_invocation_state()

    agent = Agent(
        model=self._model,
        system_prompt=system_prompt,
        tools=tools,
    )

    try:
        result = await agent.invoke_async(query_prompt, **invocation_state)
        metrics = LLMMetrics.from_strands_result(result)
        return GenerationResult(text=str(result), metrics=metrics)
    except Exception as e:
        raise map_strands_exception(e)
```

### build_query_prompt 変更

```python
def build_query_prompt(self, context: Context) -> str:
    # ... 既存のコード ...
    return self._query_template.render(
        # ... 既存のパラメータ ...
        high_priority_memos=context.high_priority_memos,
        recent_memos=context.recent_memos,
    )
```

---

## プロンプトテンプレート変更

### response_query.j2

judgment_query.j2 にも同様のセクションを追加。

```jinja2
{% if high_priority_memos or recent_memos %}
## メモ管理

あなたが記憶しておくべき重要な情報です。メモツールを使って管理できます。

### メモ管理ガイドライン

- **いつメモすべきか**: ユーザーの好み、興味、家族構成、仕事情報、依頼事項、約束、予定など重要な情報を聞いた時
- **優先度の付け方**:
  - 5: 常に覚えておくべき重要情報（名前、家族、重要な予定）
  - 4: 頻繁に参照すべき情報（好み、興味、定期的な予定）
  - 3: 参考になる情報（一般的な話題、一時的な予定）
  - 2: 補足情報
  - 1: 一時的なメモ
- **タグの付け方**: 既存タグを確認してから使用（list_memo_tagsで確認）。類似タグがあればそれを使う
- **詳細情報**: より詳しい情報はedit_memoのdetailパラメータで記録。get_memoで詳細を確認可能
- **メモの更新**: 情報が古くなったら edit_memo で更新、不要になったら remove_memo で削除
- **重複注意**: 以下のメモ一覧を確認し、同じ内容のメモを追加しないこと
- **主語を明記**: 複数人のチャットなので「誰が」が重要。人に関連するメモには必ず主語を入れる（例: 「ラーメンが好き」→「○○さんはラーメンが好き」）

{% if high_priority_memos %}
### 重要なメモ（優先度4以上）

{% for memo in high_priority_memos %}
- **ID**: {{ memo.id | string | truncate(8, True, '') }}
  - 優先度: {{ memo.priority }}
  - タグ: {{ memo.tags | join(", ") if memo.tags else "なし" }}
  - 更新日: {{ memo.updated_at | format_timestamp }}
  - 内容: {{ memo.content }}{% if memo.has_detail %} **[詳細あり]**{% endif %}

{% endfor %}
{% endif %}

{% if recent_memos %}
### 直近のメモ

{% for memo in recent_memos %}
- **ID**: {{ memo.id | string | truncate(8, True, '') }} / 優先度: {{ memo.priority }} / タグ: {{ memo.tags | join(", ") if memo.tags else "なし" }} / {{ memo.content }}{% if memo.has_detail %} [詳細あり]{% endif %}

{% endfor %}
{% endif %}

{% endif %}
```

---

## ユースケース変更

### メモ取得ロジック

autonomous_response.py と reply_to_mention.py に共通のロジックを追加。

```python
async def _get_memos_for_context(
    memo_repository: MemoRepository,
) -> tuple[list[Memo], list[Memo]]:
    """Context 用のメモを取得

    Returns:
        (high_priority_memos, recent_memos) のタプル
        recent_memos は high_priority_memos との重複を除外
    """
    # 高優先度メモを取得
    high_priority_memos = await memo_repository.find_by_priority_gte(4, limit=20)
    high_priority_ids = {m.id for m in high_priority_memos}

    # 直近メモを取得（重複除外）
    all_recent = await memo_repository.find_recent(limit=5)
    recent_memos = [m for m in all_recent if m.id not in high_priority_ids]

    return high_priority_memos, recent_memos
```

### Context 生成時

```python
# メモを取得
high_priority_memos, recent_memos = await _get_memos_for_context(memo_repository)

# Context 生成
context = Context(
    # ... 既存フィールド ...
    high_priority_memos=high_priority_memos,
    recent_memos=recent_memos,
)
```

---

## __main__.py 変更

### MemoRepository 初期化

```python
from myao2.infrastructure.persistence.memo_repository import SQLiteMemoRepository
from myao2.infrastructure.llm.strands.memo_tools import MemoToolsFactory

# SQLiteMemoRepository の初期化
memo_repository = SQLiteMemoRepository(session_factory)

# MemoToolsFactory の初期化
memo_tools_factory = MemoToolsFactory(memo_repository)

# StrandsResponseGenerator の初期化
response_generator = StrandsResponseGenerator(
    model=model,
    agent_config=agent_config,
    memo_tools_factory=memo_tools_factory,
)
```

---

## テスト項目

### TestContextWithMemos

- high_priority_memos フィールドの初期化
- recent_memos フィールドの初期化
- デフォルト値（空リスト）

### TestStrandsResponseGeneratorWithTools

- ツールなしの場合の動作
- ツールありの場合の動作
- invocation_state の渡し方

### TestResponseQueryTemplate

- メモなしの場合（セクション非表示）
- high_priority_memos のみの場合
- recent_memos のみの場合
- 両方ある場合
- 詳細ありマーカーの表示

### TestGetMemosForContext

- 重複除外の動作
- 高優先度メモがない場合
- 直近メモがない場合
- 全て重複する場合
