# extra08f: LiteLLM 直接使用コードの削除

## 概要

strands-agents への移行完了後、LiteLLM 直接使用コードと後方互換性シムを削除する。

## 前提条件

- extra08a-e が完了していること
- 全てのLLM呼び出しが strands-agents Agent ベースになっていること

## 削除対象

### 1. 後方互換性シム（extra08a で追加）

以下の後方互換性コードを削除する：

#### src/myao2/config/models.py

```python
# 削除対象
@dataclass
class LLMConfig:
    """LLM設定（後方互換性用、extra08f で削除予定）"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000

# 削除対象: MemoryConfig.memory_generation_llm フィールド
memory_generation_llm: str = "memory"

# 削除対象: Config._llm_compat フィールド
_llm_compat: dict[str, LLMConfig] | None = field(default=None, repr=False)

# 削除対象: Config.llm プロパティ
@property
def llm(self) -> dict[str, LLMConfig]:
    ...

# 削除対象: Config.__init__ の llm= パラメーター
llm: dict[str, LLMConfig] | None = None
```

#### src/myao2/config/__init__.py

```python
# 削除対象: LLMConfig のエクスポート
from myao2.config.models import (
    LLMConfig,  # 後方互換性用（extra08f で削除予定）
)

__all__ = [
    "LLMConfig",  # 後方互換性用（extra08f で削除予定）
]
```

### 2. LLMClient クラス

`src/myao2/infrastructure/llm/client.py` の `LLMClient` クラス全体を削除。
strands-agents の Agent が直接 LLM 呼び出しを行うため不要になる。

### 3. 依存関係

`pyproject.toml` から `litellm>=1.0.0` を削除（strands-agents[litellm] に含まれるため）。

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | `LLMConfig` 削除、`Config.llm` 削除、`Config._llm_compat` 削除、`MemoryConfig.memory_generation_llm` 削除 |
| `src/myao2/config/__init__.py` | `LLMConfig` エクスポート削除 |
| `src/myao2/infrastructure/llm/client.py` | ファイル削除または `LLMClient` 削除 |
| `src/myao2/infrastructure/llm/__init__.py` | `LLMClient` エクスポート削除 |
| `src/myao2/__main__.py` | `config.llm` → `config.agents` に更新 |
| `pyproject.toml` | `litellm>=1.0.0` 依存関係削除 |
| `tests/infrastructure/llm/test_client.py` | ファイル削除または更新 |

## 完了基準

- [ ] `LLMConfig` クラスが削除されている
- [ ] `Config.llm` プロパティが削除されている
- [ ] `Config._llm_compat` フィールドが削除されている
- [ ] `Config.__init__` の `llm=` パラメーターが削除されている
- [ ] `MemoryConfig.memory_generation_llm` が削除されている
- [ ] `LLMClient` クラスが削除されている
- [ ] 全テストが `agents` 形式のみを使用している
- [ ] 全テストが通過する
- [ ] ruff check が通過する
- [ ] ty check が通過する
