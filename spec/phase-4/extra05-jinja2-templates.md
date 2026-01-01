# extra05: 全LLM呼び出しのJinja2テンプレート化

## 目的

ResponseGenerator 以外のLLM呼び出し（ResponseJudgment, MemorySummarizer）でも
Jinja2テンプレートを使用してシステムプロンプトを組み立てるようにする。

---

## 背景

### 現状

| コンポーネント | プロンプト組み立て方式 |
|--------------|-------------------|
| LiteLLMResponseGenerator | Jinja2テンプレート (`system_prompt.j2`) |
| LLMResponseJudgment | Python format 文字列 |
| LLMMemorySummarizer | Python 固定文字列 |

### 問題点

1. プロンプトの管理方法が統一されていない
2. プロンプトの変更時にコード修正が必要
3. テンプレートの再利用性が低い

### 解決方針

- 全LLM呼び出しでJinja2テンプレートを使用
- MemorySummarizer は scope/memory_type に応じて条件分岐する1つのテンプレート

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/templates/judgment_prompt.j2` | 新規作成 |
| `src/myao2/infrastructure/llm/templates/memory_prompt.j2` | 新規作成 |
| `src/myao2/infrastructure/llm/response_judgment.py` | Jinja2テンプレート使用に変更 |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | Jinja2テンプレート使用に変更 |
| `tests/infrastructure/llm/test_response_judgment.py` | テスト更新 |
| `tests/infrastructure/llm/test_memory_summarizer.py` | テスト更新 |

---

## テンプレート設計

### judgment_prompt.j2

```jinja2
あなたは会話への参加判断を行うアシスタントです。

以下の情報をもとに、{{ persona_name }} として会話に参加すべきかを判断してください。

## 判断基準
1. 直接的な質問や相談がある場合
2. 自分の専門知識が役立つ場合
3. 会話の流れで発言が期待される場合
4. 重要な情報を補足できる場合
5. 盛り上がっている会話に参加できる場合

## 応答しない条件
- 既に会話が終了している
- 他の人が対応済み
- 自分が参加すべきでないプライベートな会話

## 現在時刻
{{ current_time }}

必ずJSON形式で回答してください。
回答形式：
{"should_respond": true/false, "reason": "理由", "confidence": 0.0-1.0}

信頼度スケール：
- 0.0-0.3: 確信度低（判断に迷う）
- 0.4-0.6: 確信度中
- 0.7-1.0: 確信度高
```

### memory_prompt.j2

```jinja2
{% if memory_type == "LONG_TERM" %}
あなたは会話履歴を長期記憶として要約するアシスタントです。

以下の点を踏まえて、時系列で出来事を整理してください：
- 重要なトピックや決定事項
- 参加者の傾向や特徴
- 繰り返し登場するテーマ
- 具体的な日時を含める

{% elif memory_type == "SHORT_TERM" %}
あなたは最近の会話を短期記憶として要約するアシスタントです。

以下の点を踏まえて要約してください：
- 現在進行中のテーマや話題
- 直近の質問や未解決事項
- 参加者の最近の関心事

{% endif %}

{% if scope == "WORKSPACE" %}
## ワークスペース全体の要約
チャンネル横断的なトピック、重要プロジェクト、組織全体の動向をまとめてください。

{% elif scope == "CHANNEL" %}
## チャンネルの要約
このチャンネル固有のトピック、議論、傾向をまとめてください。

{% elif scope == "THREAD" %}
## スレッドの要約
このスレッドの議論内容、結論、未解決事項をまとめてください。

{% endif %}

{% if existing_memory %}
## 既存の記憶
以下は既存の記憶です。新しい情報で更新してください：

{{ existing_memory }}
{% endif %}
```

---

## 実装詳細

### LLMResponseJudgment の変更

```python
class LLMResponseJudgment:
    def __init__(self, client: LLMClient, config: Config) -> None:
        self._client = client
        self._config = config
        self._jinja_env = self._create_jinja_env()
        self._template = self._jinja_env.get_template("judgment_prompt.j2")

    def _create_jinja_env(self) -> Environment:
        return Environment(
            loader=PackageLoader("myao2.infrastructure.llm", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _build_system_prompt(self, persona: PersonaConfig) -> str:
        return self._template.render(
            persona_name=persona.name,
            current_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
```

### LLMMemorySummarizer の変更

```python
class LLMMemorySummarizer:
    def __init__(self, client: LLMClient, config: MemoryConfig) -> None:
        self._client = client
        self._config = config
        self._jinja_env = self._create_jinja_env()
        self._template = self._jinja_env.get_template("memory_prompt.j2")

    def _build_system_prompt(
        self,
        scope: MemoryScope,
        memory_type: MemoryType,
        existing_memory: str | None = None,
    ) -> str:
        return self._template.render(
            scope=scope.value,
            memory_type=memory_type.value,
            existing_memory=existing_memory,
        )
```

---

## テストケース

### ResponseJudgment テンプレート

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| render | persona_name 設定 | プロンプトにペルソナ名が含まれる |
| render | current_time 設定 | プロンプトに現在時刻が含まれる |

### MemorySummarizer テンプレート

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| render | LONG_TERM | 長期記憶用の指示が含まれる |
| render | SHORT_TERM | 短期記憶用の指示が含まれる |
| render | WORKSPACE scope | ワークスペース用の指示が含まれる |
| render | CHANNEL scope | チャンネル用の指示が含まれる |
| render | THREAD scope | スレッド用の指示が含まれる |
| render | existing_memory あり | 既存記憶が含まれる |
| render | existing_memory なし | 既存記憶セクションなし |

---

## 完了基準

- [ ] judgment_prompt.j2 が作成されている
- [ ] memory_prompt.j2 が作成されている
- [ ] LLMResponseJudgment が Jinja2 テンプレートを使用している
- [ ] LLMMemorySummarizer が Jinja2 テンプレートを使用している
- [ ] 既存のテストが通過する
- [ ] 新規テストケースが追加されている
