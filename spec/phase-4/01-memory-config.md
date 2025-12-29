# 01: MemoryConfig 拡張

## 目的

現在の MemoryConfig を拡張し、記憶生成に必要な設定を追加する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/config/models.py` | MemoryConfig 拡張（修正） |
| `src/myao2/config/loader.py` | memory セクション読み込み拡張（修正） |
| `config.yaml.example` | memory セクション設定例追加（修正） |
| `tests/config/test_loader.py` | MemoryConfig テスト追加 |

---

## 設定仕様

### config.yaml の memory セクション（拡張後）

```yaml
memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600  # 長期記憶更新間隔（秒）
  short_term_window_hours: 24              # 短期記憶の時間窓（時間）
  long_term_summary_max_tokens: 500        # 長期記憶の最大トークン数
  short_term_summary_max_tokens: 300       # 短期記憶の最大トークン数
  memory_generation_llm: "default"         # 記憶生成に使用する LLM 設定名
```

### フィールド一覧

| フィールド | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| database_path | str | - | データベースファイルのパス（必須） |
| long_term_update_interval_seconds | int | 3600 | 長期記憶の更新間隔（秒） |
| short_term_window_hours | int | 24 | 短期記憶の時間窓（時間） |
| long_term_summary_max_tokens | int | 500 | 長期記憶の最大トークン数 |
| short_term_summary_max_tokens | int | 300 | 短期記憶の最大トークン数 |
| memory_generation_llm | str | "default" | 記憶生成に使用する LLM 設定名 |

---

## インターフェース設計

### MemoryConfig（拡張後）

```python
@dataclass
class MemoryConfig:
    """記憶設定"""

    database_path: str
    long_term_update_interval_seconds: int = 3600
    short_term_window_hours: int = 24
    long_term_summary_max_tokens: int = 500
    short_term_summary_max_tokens: int = 300
    memory_generation_llm: str = "default"
```

---

## loader.py の変更

### 読み込み処理

- 新しいフィールドが存在しない場合はデフォルト値を使用
- 部分的な設定も許容（指定されたフィールドのみ上書き）

### 実装例

```python
def _load_memory_config(memory_data: dict[str, Any]) -> MemoryConfig:
    """memory セクションを MemoryConfig に変換"""
    return MemoryConfig(
        database_path=memory_data["database_path"],
        long_term_update_interval_seconds=memory_data.get(
            "long_term_update_interval_seconds", 3600
        ),
        short_term_window_hours=memory_data.get("short_term_window_hours", 24),
        long_term_summary_max_tokens=memory_data.get(
            "long_term_summary_max_tokens", 500
        ),
        short_term_summary_max_tokens=memory_data.get(
            "short_term_summary_max_tokens", 300
        ),
        memory_generation_llm=memory_data.get("memory_generation_llm", "default"),
    )
```

---

## テストケース

### MemoryConfig

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト値 | database_path のみ指定 | 他フィールドはデフォルト値 |
| カスタム値 | 全フィールド指定 | 指定した値が設定される |
| 部分設定 | 一部のみ指定 | 指定分はカスタム、残りはデフォルト |

### loader

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新フィールドあり | 設定ファイルに記載 | MemoryConfig が正しく読み込まれる |
| 新フィールドなし | 設定ファイルに未記載 | デフォルトの MemoryConfig が使用される |
| memory_generation_llm | 存在しない LLM 設定名 | 読み込み成功（使用時に検証） |

---

## 完了基準

- [ ] MemoryConfig に新しいフィールドが追加されている
- [ ] loader.py で新しいフィールドが読み込まれる
- [ ] 新しいフィールドがない場合はデフォルト値が使用される
- [ ] 全テストケースが通過する
