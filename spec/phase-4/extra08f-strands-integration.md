# extra08f: エントリポイント統合と旧実装削除

## 目的

新しい strands-agents ベースの実装に切り替え、旧実装を削除する。

---

## 背景

### 現状

extra08a〜08e で以下の新実装が完成している：

| コンポーネント | 新実装 |
|--------------|-------|
| 設定 | AgentConfig, Config.agents |
| ファクトリー | StrandsAgentFactory |
| 応答生成 | StrandsResponseGenerator |
| 応答判定 | StrandsResponseJudgment |
| 記憶要約 | StrandsMemorySummarizer |

### 移行対象

| 旧実装 | 新実装 |
|-------|-------|
| LLMClient | 削除（不要） |
| LiteLLMResponseGenerator | StrandsResponseGenerator |
| LLMResponseJudgment | StrandsResponseJudgment |
| LLMMemorySummarizer | StrandsMemorySummarizer |
| Config.llm | Config.agents |
| MemoryConfig.memory_generation_llm | 削除（agents.memory を使用） |

---

## 実装するファイル

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/__main__.py` | 新実装への切り替え |
| `src/myao2/infrastructure/llm/__init__.py` | エクスポート更新 |
| `config.yaml` | 新形式に更新 |
| `config.yaml.example` | 新形式に更新 |
| `hack/prompt_tester.py` | 新実装への切り替え |

### 削除ファイル

| ファイル | 理由 |
|---------|------|
| `src/myao2/infrastructure/llm/client.py` | LLMClient 不要 |
| `src/myao2/infrastructure/llm/response_generator.py` | StrandsResponseGenerator に置換 |
| `src/myao2/infrastructure/llm/response_judgment.py` | StrandsResponseJudgment に置換 |
| `src/myao2/infrastructure/llm/memory_summarizer.py` | StrandsMemorySummarizer に置換 |
| `src/myao2/infrastructure/llm/templates/system_prompt.j2` | response_system/query.j2 に置換 |
| `src/myao2/infrastructure/llm/templates/judgment_prompt.j2` | judgment_system/query.j2 に置換 |
| `src/myao2/infrastructure/llm/templates/memory_prompt.j2` | memory_system/query.j2 に置換 |
| `tests/infrastructure/llm/test_client.py` | 対応する実装が削除 |
| `tests/infrastructure/llm/test_response_generator.py` | strands/test_response_generator.py に置換 |
| `tests/infrastructure/llm/test_response_judgment.py` | strands/test_response_judgment.py に置換 |
| `tests/infrastructure/llm/test_memory_summarizer.py` | strands/test_memory_summarizer.py に置換 |

---

## 設計

### __main__.py の変更

```python
# 旧インポート（削除）
# from myao2.infrastructure.llm import (
#     LiteLLMResponseGenerator,
#     LLMClient,
#     LLMResponseJudgment,
# )
# from myao2.infrastructure.llm.memory_summarizer import LLMMemorySummarizer

# 新インポート
from myao2.infrastructure.llm.strands import (
    StrandsAgentFactory,
    StrandsMemorySummarizer,
    StrandsResponseGenerator,
    StrandsResponseJudgment,
)


async def main() -> None:
    # ...

    # agents セクションの検証
    if "response" not in config.agents:
        logger.error("No 'response' agent config found")
        sys.exit(1)
    if "judgment" not in config.agents:
        logger.error("No 'judgment' agent config found")
        sys.exit(1)
    if "memory" not in config.agents:
        logger.error("No 'memory' agent config found")
        sys.exit(1)

    # ファクトリーの生成
    factory = StrandsAgentFactory()

    # Model の生成（起動時に1回、再利用される）
    response_model = factory.create_model(config.agents["response"])
    judgment_model = factory.create_model(config.agents["judgment"])
    memory_model = factory.create_model(config.agents["memory"])

    # コンポーネントの生成
    response_generator = StrandsResponseGenerator(response_model)
    response_judgment = StrandsResponseJudgment(judgment_model)
    memory_summarizer = StrandsMemorySummarizer(memory_model, config.memory)

    # 以降は既存のユースケース構築と同じ
    # ...
```

### infrastructure/llm/__init__.py の変更

```python
# 旧エクスポート（削除）
# from myao2.infrastructure.llm.client import LLMClient
# from myao2.infrastructure.llm.response_generator import LiteLLMResponseGenerator
# from myao2.infrastructure.llm.response_judgment import LLMResponseJudgment

# 新エクスポート
from myao2.infrastructure.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
)
from myao2.infrastructure.llm.templates import create_jinja_env, format_timestamp

__all__ = [
    "LLMError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "create_jinja_env",
    "format_timestamp",
]
```

### config.yaml の更新

```yaml
# 旧形式（削除）
# llm:
#   default:
#     model: "gpt-4o"
#     temperature: 0.7
#     max_tokens: 1000
#   judgment:
#     model: "gpt-4o-mini"
#     temperature: 0.3

# 新形式
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

# memory セクションの変更
memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600
  short_term_window_hours: 24
  long_term_summary_max_tokens: 2000
  short_term_summary_max_tokens: 500
  # memory_generation_llm を削除
```

---

## ファイル構造（最終）

```
src/myao2/infrastructure/llm/
├── __init__.py
├── exceptions.py
├── templates.py
├── templates/
│   ├── response_system.j2
│   ├── response_query.j2
│   ├── judgment_system.j2
│   ├── judgment_query.j2
│   ├── memory_system.j2
│   └── memory_query.j2
└── strands/
    ├── __init__.py
    ├── factory.py
    ├── exceptions.py
    ├── models.py
    ├── response_generator.py
    ├── response_judgment.py
    └── memory_summarizer.py
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| integration | 全コンポーネント起動 | エラーなく起動 |
| integration | 応答生成 | StrandsResponseGenerator が使用される |
| integration | 応答判定 | StrandsResponseJudgment が使用される |
| integration | 記憶要約 | StrandsMemorySummarizer が使用される |
| config | agents.response 欠落 | エラー終了 |
| config | agents.judgment 欠落 | エラー終了 |
| config | agents.memory 欠落 | エラー終了 |

---

## 移行手順

1. 新しいテンプレートファイルが作成されていることを確認
2. strands/ ディレクトリの実装が完了していることを確認
3. config.yaml を新形式に更新
4. __main__.py を新実装に切り替え
5. infrastructure/llm/__init__.py を更新
6. 全テストを実行して通過を確認
7. 旧実装ファイルを削除
8. 旧テストファイルを削除
9. 最終テストを実行

---

## 完了基準

- [ ] __main__.py が新実装を使用している
- [ ] config.yaml が新形式になっている
- [ ] config.yaml.example が新形式になっている
- [ ] 旧実装ファイルが全て削除されている
- [ ] 旧テンプレートファイルが全て削除されている
- [ ] 旧テストファイルが全て削除されている
- [ ] infrastructure/llm/__init__.py が更新されている
- [ ] 全テストが通過する
- [ ] アプリケーションが正常に起動・動作する
