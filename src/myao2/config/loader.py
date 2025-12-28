"""YAML設定ファイルの読み込みと環境変数展開"""

import os
import re
from pathlib import Path
from typing import Any

import yaml

from myao2.config.models import (
    Config,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    PersonaConfig,
    SlackConfig,
)


class ConfigError(Exception):
    """設定関連の基底例外"""


class ConfigValidationError(ConfigError):
    """設定値のバリデーションエラー"""


class EnvironmentVariableError(ConfigError):
    """環境変数が見つからないエラー"""


# 環境変数パターン: ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def expand_env_vars(value: str) -> str:
    """文字列中の ${VAR_NAME} を環境変数の値に置換する

    Args:
        value: 置換対象の文字列

    Returns:
        環境変数が展開された文字列

    Raises:
        EnvironmentVariableError: 環境変数が未設定
    """
    if not value:
        return value

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise EnvironmentVariableError(
                f"Environment variable '{var_name}' is not set"
            )
        return env_value

    return ENV_VAR_PATTERN.sub(replace_var, value)


def _expand_recursive(data: Any) -> Any:
    """データ構造を再帰的に走査し、文字列中の環境変数を展開する

    Args:
        data: 展開対象のデータ（dict, list, str, その他）

    Returns:
        環境変数が展開されたデータ
    """
    if isinstance(data, dict):
        return {key: _expand_recursive(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_expand_recursive(item) for item in data]
    elif isinstance(data, str):
        return expand_env_vars(data)
    else:
        return data


def _validate_required_field(data: dict[str, Any], field: str, parent: str = "") -> Any:
    """必須フィールドの存在を検証する

    Args:
        data: 検証対象のdict
        field: フィールド名
        parent: 親フィールド名（エラーメッセージ用）

    Returns:
        フィールドの値

    Raises:
        ConfigValidationError: フィールドが存在しない
    """
    if field not in data or data[field] is None:
        full_path = f"{parent}.{field}" if parent else field
        raise ConfigValidationError(f"Required field '{full_path}' is missing")
    return data[field]


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
        yaml.YAMLError: YAML構文エラー
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    # 環境変数を展開
    data = _expand_recursive(raw_data)

    # 必須セクションの検証
    slack_data = _validate_required_field(data, "slack")
    llm_data = _validate_required_field(data, "llm")
    persona_data = _validate_required_field(data, "persona")

    # SlackConfig
    slack = SlackConfig(
        bot_token=_validate_required_field(slack_data, "bot_token", "slack"),
        app_token=_validate_required_field(slack_data, "app_token", "slack"),
    )

    # LLMConfig (defaultは必須)
    _validate_required_field(llm_data, "default", "llm")
    llm: dict[str, LLMConfig] = {}
    for key, llm_item in llm_data.items():
        model = _validate_required_field(llm_item, "model", f"llm.{key}")
        llm[key] = LLMConfig(
            model=model,
            temperature=llm_item.get("temperature", 0.7),
            max_tokens=llm_item.get("max_tokens", 1000),
        )

    # PersonaConfig
    persona = PersonaConfig(
        name=_validate_required_field(persona_data, "name", "persona"),
        system_prompt=_validate_required_field(
            persona_data, "system_prompt", "persona"
        ),
    )

    # MemoryConfig
    memory_data = _validate_required_field(data, "memory")
    memory = MemoryConfig(
        database_path=_validate_required_field(memory_data, "database_path", "memory"),
        long_term_update_interval_seconds=memory_data.get(
            "long_term_update_interval_seconds", 3600
        ),
    )

    # LoggingConfig (optional)
    logging_config: LoggingConfig | None = None
    logging_data = data.get("logging")
    if logging_data:
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            format=logging_data.get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            loggers=logging_data.get("loggers"),
            debug_llm_messages=logging_data.get("debug_llm_messages", False),
        )

    return Config(
        slack=slack, llm=llm, persona=persona, memory=memory, logging=logging_config
    )
