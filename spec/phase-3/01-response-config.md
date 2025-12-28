# 01: ResponseConfig モデル追加

## 目的

config.yaml の `response` セクションを Config に反映し、
自律応答機能の設定を管理できるようにする。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/config/models.py` | ResponseConfig 追加（修正） |
| `src/myao2/config/loader.py` | response セクション読み込み（修正） |
| `tests/config/test_loader.py` | ResponseConfig テスト追加 |

---

## 設定仕様

### config.yaml の response セクション

```yaml
response:
  check_interval_seconds: 60    # 判定ループの間隔（秒）
  min_wait_seconds: 300         # 最低待機時間（秒）
```

| フィールド | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| check_interval_seconds | int | 60 | 定期チェックの間隔（秒） |
| min_wait_seconds | int | 300 | メッセージ投稿後の最低待機時間（秒） |

---

## インターフェース設計

### ResponseConfig

```python
@dataclass
class ResponseConfig:
    """自律応答設定"""

    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
```

### Config への統合

```python
@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    llm: dict[str, LLMConfig]
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig  # 追加
    logging: LoggingConfig | None = None
```

---

## loader.py の変更

### 読み込み処理

- `response` セクションが存在しない場合はデフォルト値を使用
- 部分的な設定も許容（指定されたフィールドのみ上書き）

---

## テストケース

### ResponseConfig

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| デフォルト値 | フィールド未指定 | check_interval=60, min_wait=300 |
| カスタム値 | 全フィールド指定 | 指定した値が設定される |

### loader

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| response セクションあり | 設定ファイルに記載 | ResponseConfig が正しく読み込まれる |
| response セクションなし | 設定ファイルに未記載 | デフォルトの ResponseConfig が使用される |
| 部分設定 | 一部のみ指定 | 指定分はカスタム、残りはデフォルト |

---

## 完了基準

- [x] ResponseConfig が定義されている
- [x] Config に response フィールドが追加されている
- [x] loader.py で response セクションが読み込まれる
- [x] response セクションがない場合はデフォルト値が使用される
- [x] 全テストケースが通過する
