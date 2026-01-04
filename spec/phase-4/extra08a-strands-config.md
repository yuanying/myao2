# extra08a: strands-agents用設定構造の拡張

## 目的

strands-agents の LiteLLMModel に渡すパラメーター（model_id, params, client_args）を
各Agent（response, judgment, memory）で個別に設定できるようにする。

---

## 背景

### 現状

```yaml
llm:
  default:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 1000
  judgment:
    model: "gpt-4o-mini"
    temperature: 0.3
```

| 項目 | 現状 |
|------|------|
| 設定形式 | LLMConfig (model, temperature, max_tokens) |
| Agent別設定 | default/judgment の2種類のみ |
| APIキー管理 | 環境変数から自動取得（LiteLLM） |

### 問題点

1. strands-agents の LiteLLMModel に必要なパラメーターが不足
2. client_args（API キー、エンドポイント等）の明示的な設定ができない
3. 各Agent（response, judgment, memory）で異なる設定ができない

### 解決方針

- 新しい `agents` セクションを追加
- AgentConfig dataclass で model_id, params, client_args を定義
- 旧 `llm` セクションは削除（後方互換性なし）

---

## 新config構造

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
```

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | AgentConfig dataclass 追加、Config.agents フィールド追加 |
| `src/myao2/config/loader.py` | agents セクションの読み込み対応 |
| `config.yaml.example` | 新形式の例追加 |
| `tests/config/test_loader.py` | 新形式テスト追加 |

---

## 設計

### AgentConfig dataclass

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """strands-agents用設定

    Attributes:
        model_id: LiteLLMのモデルID（例: "openai/gpt-4o"）
        params: LLMパラメーター（temperature, max_tokens等）
        client_args: LiteLLMクライアント引数（api_key, api_base等）
    """

    model_id: str
    params: dict[str, Any] = field(default_factory=dict)
    client_args: dict[str, Any] = field(default_factory=dict)
```

### Config dataclass の変更

```python
@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    agents: dict[str, AgentConfig]  # 新規追加
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig
    logging: LoggingConfig | None = None
    # llm: dict[str, LLMConfig] を削除
```

### MemoryConfig の変更

```python
@dataclass
class MemoryConfig:
    """記憶設定"""

    database_path: str
    long_term_update_interval_seconds: int = 3600
    short_term_window_hours: int = 24
    long_term_summary_max_tokens: int = 500
    short_term_summary_max_tokens: int = 300
    # memory_generation_llm を削除（agents.memory を直接使用）
```

### loader.py の変更

```python
def load_config(path: str | Path) -> Config:
    # ...

    # AgentConfig (response, judgment, memory は必須)
    agents_data = _validate_required_field(data, "agents")
    _validate_required_field(agents_data, "response", "agents")
    _validate_required_field(agents_data, "judgment", "agents")
    _validate_required_field(agents_data, "memory", "agents")

    agents: dict[str, AgentConfig] = {}
    for key, agent_item in agents_data.items():
        model_id = _validate_required_field(agent_item, "model_id", f"agents.{key}")
        agents[key] = AgentConfig(
            model_id=model_id,
            params=agent_item.get("params", {}),
            client_args=agent_item.get("client_args", {}),
        )

    # ...

    return Config(
        slack=slack,
        agents=agents,  # llm を agents に変更
        persona=persona,
        memory=memory,
        response=response,
        logging=logging_config,
    )
```

---

## テストケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| load_config | 全agents設定あり | 3つのAgentConfigが読み込まれる |
| load_config | response が欠落 | ConfigValidationError |
| load_config | judgment が欠落 | ConfigValidationError |
| load_config | memory が欠落 | ConfigValidationError |
| load_config | model_id が欠落 | ConfigValidationError |
| load_config | params 省略 | 空のdictがデフォルト |
| load_config | client_args 省略 | 空のdictがデフォルト |
| load_config | client_args に ${ENV_VAR} | 環境変数が展開される |

---

## 依存関係追加

`pyproject.toml` に追加:

```toml
dependencies = [
    # 既存の依存関係
    "strands-agents[litellm]>=0.1.0",  # 新規追加
]
```

---

## 完了基準

- [ ] AgentConfig dataclass が実装されている
- [ ] Config.agents フィールドが追加されている
- [ ] Config.llm フィールドが削除されている
- [ ] MemoryConfig.memory_generation_llm が削除されている
- [ ] loader.py が agents セクションを読み込める
- [ ] 環境変数展開が client_args 内で機能する
- [ ] config.yaml.example が更新されている
- [ ] 全テストが通過する
