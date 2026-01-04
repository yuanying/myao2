# extra08b: StrandsAgentFactory の実装

## 目的

strands-agents の Agent と LiteLLMModel を生成するファクトリークラスを実装する。
例外マッピングユーティリティも併せて実装する。

---

## 背景

### 現状

| コンポーネント | LLMクライアント |
|--------------|----------------|
| LiteLLMResponseGenerator | LLMClient (LiteLLM直接) |
| LLMResponseJudgment | LLMClient (LiteLLM直接) |
| LLMMemorySummarizer | LLMClient (LiteLLM直接) |

### 問題点

1. LiteLLMを直接使用しており、strands-agentsへの移行が困難
2. 各コンポーネントがLLMClientに依存している

### 解決方針

- StrandsAgentFactory で Agent/LiteLLMModel の生成を集約
- 例外マッピングユーティリティで strands-agents 例外をドメイン例外に変換
- 将来の Tool 機能追加に備えた設計

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/strands/__init__.py` | 新規作成 |
| `src/myao2/infrastructure/llm/strands/factory.py` | StrandsAgentFactory 実装 |
| `src/myao2/infrastructure/llm/strands/exceptions.py` | 例外マッピングユーティリティ |
| `tests/infrastructure/llm/strands/__init__.py` | 新規作成 |
| `tests/infrastructure/llm/strands/test_factory.py` | ファクトリーテスト |

---

## 設計

### ディレクトリ構造

```
src/myao2/infrastructure/llm/strands/
├── __init__.py
├── factory.py
└── exceptions.py
```

### StrandsAgentFactory

```python
from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig


class StrandsAgentFactory:
    """strands-agents の Agent/LiteLLMModel を生成するファクトリー"""

    def create_model(self, config: AgentConfig) -> LiteLLMModel:
        """AgentConfig から LiteLLMModel を生成

        Args:
            config: Agent設定

        Returns:
            LiteLLMModel インスタンス
        """
        return LiteLLMModel(
            model_id=config.model_id,
            params=config.params,
            client_args=config.client_args,
        )

    def create_agent(
        self,
        model: LiteLLMModel,
        system_prompt: str | None = None,
        tools: list | None = None,
    ) -> Agent:
        """LiteLLMModel から Agent を生成

        Args:
            model: LiteLLMModel インスタンス
            system_prompt: システムプロンプト（固定部分）
            tools: ツールリスト（将来の拡張用）

        Returns:
            Agent インスタンス
        """
        return Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools or [],
        )
```

### 例外マッピングユーティリティ

```python
from myao2.infrastructure.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
)


def map_strands_exception(e: Exception) -> LLMError:
    """strands-agents例外をドメイン例外に変換

    Args:
        e: strands-agents から発生した例外

    Returns:
        対応するドメイン例外
    """
    error_message = str(e).lower()

    # 認証エラーの検出
    if "authentication" in error_message or "api key" in error_message:
        return LLMAuthenticationError(str(e))

    # レート制限エラーの検出
    if "rate limit" in error_message or "too many requests" in error_message:
        return LLMRateLimitError(str(e))

    # その他のエラー
    return LLMError(str(e))
```

### __init__.py

```python
from myao2.infrastructure.llm.strands.exceptions import map_strands_exception
from myao2.infrastructure.llm.strands.factory import StrandsAgentFactory

__all__ = [
    "StrandsAgentFactory",
    "map_strands_exception",
]
```

---

## 使用例

```python
from myao2.config.models import AgentConfig
from myao2.infrastructure.llm.strands import StrandsAgentFactory, map_strands_exception

# ファクトリーの使用
factory = StrandsAgentFactory()

# Model の生成（起動時に1回）
config = AgentConfig(
    model_id="openai/gpt-4o",
    params={"temperature": 0.7, "max_tokens": 1000},
    client_args={"api_key": "sk-..."},
)
model = factory.create_model(config)

# Agent の生成（リクエストごと）
agent = factory.create_agent(
    model=model,
    system_prompt="あなたは親切なアシスタントです。",
)

# Agent の実行
try:
    result = await agent.invoke_async("こんにちは")
except Exception as e:
    raise map_strands_exception(e)
```

---

## テストケース

### StrandsAgentFactory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| create_model | 正常な AgentConfig | LiteLLMModel が生成される |
| create_model | params が空 | 空の params で LiteLLMModel が生成される |
| create_model | client_args が空 | 空の client_args で LiteLLMModel が生成される |
| create_agent | system_prompt あり | system_prompt が設定された Agent が生成される |
| create_agent | system_prompt なし | system_prompt なしの Agent が生成される |
| create_agent | tools あり | tools が設定された Agent が生成される |

### 例外マッピング

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| map_strands_exception | 認証エラー | LLMAuthenticationError |
| map_strands_exception | レート制限エラー | LLMRateLimitError |
| map_strands_exception | その他のエラー | LLMError |

---

## 完了基準

- [x] `strands/` ディレクトリが作成されている
- [x] StrandsAgentFactory が実装されている
- [x] create_model メソッドが AgentConfig から LiteLLMModel を生成できる
- [x] create_agent メソッドが Agent を生成できる
- [x] 例外マッピングユーティリティが実装されている
- [x] 全テストが通過する
