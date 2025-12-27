# 02: 設定ファイル基盤

## 目的

config.yaml の読み込みと環境変数展開を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/config/loader.py` | YAML 読み込み・環境変数展開 |
| `src/myao2/config/models.py` | 設定データクラス |
| `tests/config/test_loader.py` | ローダーのテスト |

---

## 設定ファイル形式

```yaml
# config.yaml
slack:
  bot_token: ${SLACK_BOT_TOKEN}
  app_token: ${SLACK_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 1000

persona:
  name: "myao"
  system_prompt: "あなたは友達のように振る舞うチャットボットです。"
```

---

## インターフェース設計

### `src/myao2/config/models.py`

#### SlackConfig

```
@dataclass
class SlackConfig:
    """Slack接続設定"""
    bot_token: str
    app_token: str
```

#### LLMConfig

```
@dataclass
class LLMConfig:
    """LLM設定（LiteLLMのcompletionに渡すdict）"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    # 追加パラメータは **kwargs で対応
```

#### PersonaConfig

```
@dataclass
class PersonaConfig:
    """ペルソナ設定"""
    name: str
    system_prompt: str
```

#### Config

```
@dataclass
class Config:
    """アプリケーション設定"""
    slack: SlackConfig
    llm: dict[str, LLMConfig]  # "default", "judgment" 等のキー
    persona: PersonaConfig
```

### `src/myao2/config/loader.py`

#### load_config

```
def load_config(path: str | Path) -> Config:
    """設定ファイルを読み込む

    Args:
        path: config.yaml のパス

    Returns:
        Config オブジェクト

    Raises:
        FileNotFoundError: ファイルが存在しない
        ConfigValidationError: 必須項目が欠落
        EnvironmentVariableError: 環境変数が未設定
    """
```

#### expand_env_vars

```
def expand_env_vars(value: str) -> str:
    """文字列中の ${VAR_NAME} を環境変数の値に置換する

    Args:
        value: 置換対象の文字列

    Returns:
        環境変数が展開された文字列

    Raises:
        EnvironmentVariableError: 環境変数が未設定
    """
```

### 例外クラス

```
class ConfigError(Exception):
    """設定関連の基底例外"""

class ConfigValidationError(ConfigError):
    """設定値のバリデーションエラー"""

class EnvironmentVariableError(ConfigError):
    """環境変数が見つからないエラー"""
```

---

## テストケース

### test_loader.py

#### 正常系

| テスト | 入力 | 期待結果 |
|--------|-----|---------|
| 正常な設定ファイル読み込み | 有効なconfig.yaml | Configオブジェクトが返る |
| 環境変数の展開 | `${EXISTING_VAR}` | 環境変数の値に置換される |
| 複数のLLM設定 | default, judgment | dict[str, LLMConfig]で取得できる |

#### 異常系

| テスト | 入力 | 期待結果 |
|--------|-----|---------|
| ファイルが存在しない | 存在しないパス | FileNotFoundError |
| 環境変数が未設定 | `${UNDEFINED_VAR}` | EnvironmentVariableError |
| 必須項目の欠落 | slack.bot_tokenなし | ConfigValidationError |
| YAMLの構文エラー | 不正なYAML | yaml.YAMLError |

#### expand_env_vars

| テスト | 入力 | 期待結果 |
|--------|-----|---------|
| 単一の変数 | `${HOME}` | `/home/user` 等 |
| 複数の変数 | `${A}_${B}` | `valueA_valueB` |
| 変数なし | `plain text` | `plain text`（そのまま） |
| 未設定の変数 | `${UNDEFINED}` | EnvironmentVariableError |

---

## 設計上の考慮事項

### 環境変数展開の仕様

- `${VAR_NAME}` 形式のみサポート
- ネストした値も再帰的に展開
- 未設定の環境変数は即座にエラー（デフォルト値は設けない）

### LLM設定の柔軟性

- `llm.default` は必須
- 追加設定（`llm.judgment` 等）は任意
- 各設定はLiteLLMの `completion()` にそのまま渡せる形式

---

## 完了基準

- [x] `load_config()` が正常な設定ファイルを読み込める
- [x] `${VAR_NAME}` 形式の環境変数が展開される
- [x] 必須項目が欠落している場合にエラーが発生する
- [x] 未設定の環境変数参照時にエラーが発生する
- [x] 全テストケースが通過する
