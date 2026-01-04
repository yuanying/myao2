# extra08: strands-agents への LLM Client 移行

## 目的

バックエンドの LLM Client を LiteLLM 直接利用から strands-agents フレームワークに移行する。
各 Agent（response, judgment, memory）で個別の LLM 設定を可能にする。

---

## 背景

### 現状の問題点

| 問題 | 詳細 |
|------|------|
| LiteLLM 直接使用 | Agent フレームワークの恩恵を受けられない |
| LLM設定の共有 | response/judgment/memory で同じ設定を使用 |
| JSON パースの複雑さ | Judgment で手動 JSON パースが必要 |
| テンプレート構造 | system/query の分離ができていない |

### 解決方針

- strands-agents の Agent フレームワーク全体を使用
- 既存のドメイン層 Protocol（ResponseGenerator, ResponseJudgment, MemorySummarizer）は維持
- テンプレートを system_prompt（固定）と query_prompt（動的）に分割
- Judgment では Structured Output を使用して型安全な出力を実現

---

## 決定事項

| 項目 | 決定 | 備考 |
|------|------|------|
| Config セクション名 | `agents`（新規） | `llm` セクションは削除 |
| 後方互換性 | なし | 即座に新形式に移行 |
| Tool 機能 | 将来のために準備のみ | 今回は Tool 使用なし |
| Agent ライフサイクル | リクエストごとに生成 | Model は再利用 |
| 例外マッピング | 共通ユーティリティ関数 | `strands/exceptions.py` に配置 |
| ログ機能 | 最初はログなし | 後続タスクで対応 |
| API キー管理 | config で明示的に指定 | 環境変数参照可（`${VAR}` 形式） |
| Agent キー名 | response/judgment/memory | 短く明確 |
| memory_generation_llm | 削除 | agents.memory を直接使用 |
| テンプレート分割 | system（固定）/ query（動的） | Jinja2 テンプレート |
| Structured Output | Judgment で使用 | Pydantic モデルで型安全な JSON 出力 |

---

## サブタスク一覧

| サブタスク | 目的 | 主要成果物 |
|-----------|------|-----------|
| [08a](extra08a-strands-config.md) | 設定構造の拡張 | AgentConfig, Config.agents |
| [08b](extra08b-strands-factory.md) | ファクトリー実装 | StrandsAgentFactory, map_strands_exception |
| [08c](extra08c-strands-response-generator.md) | 応答生成 | StrandsResponseGenerator |
| [08d](extra08d-strands-response-judgment.md) | 応答判定 | StrandsResponseJudgment + Structured Output |
| [08e](extra08e-strands-memory-summarizer.md) | 記憶要約 | StrandsMemorySummarizer |
| [08f](extra08f-strands-integration.md) | 統合・削除 | エントリポイント切り替え、旧実装削除 |

### 依存関係

```
08a ─┬─→ 08b ─┬─→ 08c ─┐
     │        │        │
     │        ├─→ 08d ─┼─→ 08f
     │        │        │
     │        └─→ 08e ─┘
     │
     └─→ 08f（config変更）
```

---

## 新 config 構造

```yaml
agents:
  response:
    model_id: "openai/gpt-4o"
    params:
      temperature: 0.7
      max_tokens: 1000
    client_args:
      api_key: ${OPENAI_API_KEY}

  judgment:
    model_id: "openai/gpt-4o-mini"
    params:
      temperature: 0.3
      max_tokens: 500
    client_args:
      api_key: ${OPENAI_API_KEY}

  memory:
    model_id: "openai/gpt-4o"
    params:
      temperature: 0.5
      max_tokens: 800
    client_args:
      api_key: ${OPENAI_API_KEY}

# 削除される設定:
# - llm セクション全体
# - memory.memory_generation_llm
```

---

## ファイル構造（移行後）

```
src/myao2/infrastructure/llm/
├── __init__.py               # エクスポート更新
├── exceptions.py             # 維持
├── templates.py              # 維持
├── templates/
│   ├── response_system.j2    # 新規
│   ├── response_query.j2     # 新規
│   ├── judgment_system.j2    # 新規
│   ├── judgment_query.j2     # 新規
│   ├── memory_system.j2      # 新規
│   └── memory_query.j2       # 新規
└── strands/                  # 新規ディレクトリ
    ├── __init__.py
    ├── factory.py            # StrandsAgentFactory
    ├── exceptions.py         # map_strands_exception
    ├── models.py             # JudgmentOutput (Pydantic)
    ├── response_generator.py
    ├── response_judgment.py
    └── memory_summarizer.py
```

### 削除ファイル

- `src/myao2/infrastructure/llm/client.py`
- `src/myao2/infrastructure/llm/response_generator.py`
- `src/myao2/infrastructure/llm/response_judgment.py`
- `src/myao2/infrastructure/llm/memory_summarizer.py`
- `src/myao2/infrastructure/llm/templates/system_prompt.j2`
- `src/myao2/infrastructure/llm/templates/judgment_prompt.j2`
- `src/myao2/infrastructure/llm/templates/memory_prompt.j2`

---

## テンプレート分割設計

各 Agent のテンプレートを system_prompt（固定）と query_prompt（動的）に分割する。

| Agent | system_prompt | query_prompt |
|-------|---------------|--------------|
| Response | ペルソナ設定 | 記憶、会話履歴、応答指示 |
| Judgment | ペルソナ、判断基準 | 記憶、会話履歴、現在時刻、判定指示 |
| Memory | ペルソナ、要約ルール、scope/type別指針 | 既存記憶、統合対象、要約指示 |

### Structured Output（Judgment のみ）

```python
class JudgmentOutput(BaseModel):
    should_respond: bool = Field(description="応答すべきかどうか")
    reason: str = Field(description="判断理由")
    confidence: float = Field(ge=0.0, le=1.0, description="確信度")
```

---

## 依存関係追加

`pyproject.toml`:

```toml
dependencies = [
    "strands-agents[litellm]>=0.1.0",
]
```

---

## 移行手順

1. **08a**: AgentConfig 追加、config.yaml.example 更新
2. **08b**: StrandsAgentFactory、例外マッピング実装
3. **08c**: StrandsResponseGenerator、新テンプレート作成
4. **08d**: StrandsResponseJudgment、Structured Output 実装
5. **08e**: StrandsMemorySummarizer 実装
6. **08f**: エントリポイント切り替え、旧実装削除

各ステップで:
- TDD でテスト先行
- Protocol 準拠を確認
- 全テスト通過を確認

---

## テスト戦略

- `Agent` と `LiteLLMModel` をモック化
- 実際の LLM 呼び出しはしない
- Protocol に準拠したテストを先に作成

---

## 完了基準

- [x] 08a: AgentConfig が実装されている
- [x] 08b: StrandsAgentFactory が実装されている
- [x] 08c: StrandsResponseGenerator が実装されている
- [ ] 08d: StrandsResponseJudgment が Structured Output で実装されている
- [ ] 08e: StrandsMemorySummarizer が実装されている
- [ ] 08f: エントリポイントが新実装に切り替わっている
- [ ] 08f: 旧実装ファイルが全て削除されている
- [ ] 全テストが通過する
- [ ] アプリケーションが正常に起動・動作する
