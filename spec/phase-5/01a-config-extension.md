# 01a: 設定項目の追加

## 目的

短期記憶履歴機能に必要な設定項目を追加する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/config/models.py` | ShortTermHistoryConfig dataclass 追加（修正） |
| `src/myao2/config/loader.py` | 新設定項目の読み込み（修正） |
| `config.yaml.example` | 設定例の追加（修正） |
| `tests/config/test_loader.py` | 設定読み込みテスト追加（修正） |

---

## インターフェース設計

### ShortTermHistoryConfig dataclass

```python
@dataclass
class ShortTermHistoryConfig:
    """短期記憶履歴設定

    Attributes:
        enabled: 履歴機能の有効/無効
        max_history_count: プロンプトに含める履歴数
        conversation_idle_seconds: 会話終了と判定する静止時間（秒）
        message_threshold: コンテキスト圧迫と判定するメッセージ数閾値
    """

    enabled: bool = True
    max_history_count: int = 5
    conversation_idle_seconds: int = 7200  # 2時間
    message_threshold: int = 50
```

### MemoryConfig の拡張

```python
@dataclass
class MemoryConfig:
    """記憶設定"""

    database_path: str
    long_term_update_interval_seconds: int = 3600
    short_term_window_hours: int = 24
    long_term_summary_max_tokens: int = 500
    short_term_summary_max_tokens: int = 300
    short_term_history: ShortTermHistoryConfig | None = None  # 追加
```

---

## 設定ファイル例

### config.yaml.example への追加

```yaml
memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 3600
  short_term_window_hours: 24
  long_term_summary_max_tokens: 500
  short_term_summary_max_tokens: 300
  # 短期記憶履歴設定
  short_term_history:
    enabled: true
    max_history_count: 5          # プロンプトに含める履歴数
    conversation_idle_seconds: 7200  # 会話終了判定（2時間）
    message_threshold: 50         # メッセージ数閾値
```

---

## 設定読み込みロジック

### loader.py での処理

```python
def _load_memory_config(memory_dict: dict[str, Any]) -> MemoryConfig:
    """記憶設定を読み込む"""
    short_term_history = None
    if "short_term_history" in memory_dict:
        sth = memory_dict["short_term_history"]
        short_term_history = ShortTermHistoryConfig(
            enabled=sth.get("enabled", True),
            max_history_count=sth.get("max_history_count", 5),
            conversation_idle_seconds=sth.get("conversation_idle_seconds", 7200),
            message_threshold=sth.get("message_threshold", 50),
        )

    return MemoryConfig(
        database_path=memory_dict["database_path"],
        long_term_update_interval_seconds=memory_dict.get(
            "long_term_update_interval_seconds", 3600
        ),
        short_term_window_hours=memory_dict.get("short_term_window_hours", 24),
        long_term_summary_max_tokens=memory_dict.get("long_term_summary_max_tokens", 500),
        short_term_summary_max_tokens=memory_dict.get("short_term_summary_max_tokens", 300),
        short_term_history=short_term_history,
    )
```

---

## 設定項目の説明

| 項目 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `enabled` | bool | true | 履歴機能の有効/無効。無効の場合は従来通り上書き |
| `max_history_count` | int | 5 | プロンプトに含める短期記憶履歴の件数 |
| `conversation_idle_seconds` | int | 7200 | 会話終了と判定する静止時間（秒）。この時間メッセージがなければ短期記憶を更新 |
| `message_threshold` | int | 50 | コンテキスト圧迫と判定するメッセージ数。この件数を超えたら短期記憶を更新 |

---

## テストケース

### ShortTermHistoryConfig

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト値 | 引数なしで生成 | enabled=True, max_history_count=5, etc. |
| カスタム値 | 全項目を指定 | 指定した値が設定される |

### MemoryConfig

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| short_term_history あり | 設定ファイルに含む | ShortTermHistoryConfig が設定される |
| short_term_history なし | 設定ファイルに含まない | None |

### 設定読み込み

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 完全な設定 | 全項目を含む YAML | 正しく読み込まれる |
| デフォルト値 | short_term_history の一部項目のみ | デフォルト値で補完される |
| 未指定 | short_term_history セクションなし | short_term_history が None |

---

## 完了基準

- [ ] ShortTermHistoryConfig dataclass が定義されている
- [ ] MemoryConfig に short_term_history フィールドが追加されている
- [ ] loader.py で short_term_history を読み込める
- [ ] config.yaml.example に設定例が追加されている
- [ ] 全テストケースが通過する
