"""設定ローダーのテスト"""

import os
from pathlib import Path
from typing import Generator

import pytest
import yaml

from myao2.config import (
    Config,
    ConfigValidationError,
    EnvironmentVariableError,
    LLMConfig,
    MemoryConfig,
    PersonaConfig,
    ResponseConfig,
    ResponseIntervalConfig,
    SlackConfig,
    expand_env_vars,
    load_config,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """一時的な設定ディレクトリを作成"""
    return tmp_path


@pytest.fixture
def env_vars() -> Generator[dict[str, str], None, None]:
    """テスト用環境変数を設定・クリーンアップ"""
    test_vars = {
        "TEST_BOT_TOKEN": "xoxb-test-token",
        "TEST_APP_TOKEN": "xapp-test-token",
        "TEST_VAR_A": "valueA",
        "TEST_VAR_B": "valueB",
    }
    # 設定
    for key, value in test_vars.items():
        os.environ[key] = value
    yield test_vars
    # クリーンアップ
    for key in test_vars:
        os.environ.pop(key, None)


class TestExpandEnvVars:
    """expand_env_vars関数のテスト"""

    def test_single_variable(self, env_vars: dict[str, str]) -> None:
        """単一の変数を展開できる"""
        result = expand_env_vars("${TEST_BOT_TOKEN}")
        assert result == "xoxb-test-token"

    def test_multiple_variables(self, env_vars: dict[str, str]) -> None:
        """複数の変数を展開できる"""
        result = expand_env_vars("${TEST_VAR_A}_${TEST_VAR_B}")
        assert result == "valueA_valueB"

    def test_no_variables(self) -> None:
        """変数がない場合はそのまま返す"""
        result = expand_env_vars("plain text")
        assert result == "plain text"

    def test_mixed_content(self, env_vars: dict[str, str]) -> None:
        """テキストと変数が混在する場合"""
        result = expand_env_vars("prefix_${TEST_VAR_A}_suffix")
        assert result == "prefix_valueA_suffix"

    def test_undefined_variable(self) -> None:
        """未設定の変数でEnvironmentVariableErrorが発生"""
        with pytest.raises(EnvironmentVariableError) as exc_info:
            expand_env_vars("${UNDEFINED_VAR_12345}")
        assert "UNDEFINED_VAR_12345" in str(exc_info.value)

    def test_empty_string(self) -> None:
        """空文字列はそのまま返す"""
        result = expand_env_vars("")
        assert result == ""


class TestLoadConfig:
    """load_config関数のテスト"""

    def test_load_valid_config(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """有効な設定ファイルを読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 1000

persona:
  name: "myao"
  system_prompt: "テスト用システムプロンプト"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert isinstance(config, Config)
        assert config.slack.bot_token == "xoxb-test-token"
        assert config.slack.app_token == "xapp-test-token"
        assert "default" in config.llm
        assert config.llm["default"].model == "gpt-4o"
        assert config.persona.name == "myao"
        assert config.memory.database_path == "./data/memory.db"

    def test_env_var_expansion(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """環境変数が正しく展開される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "test"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.slack.bot_token == "xoxb-test-token"
        assert config.slack.app_token == "xapp-test-token"

    def test_multiple_llm_configs(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """複数のLLM設定を読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 1000
  judgment:
    model: "gpt-4o-mini"
    temperature: 0.3
    max_tokens: 500

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert "default" in config.llm
        assert "judgment" in config.llm
        assert config.llm["default"].model == "gpt-4o"
        assert config.llm["default"].temperature == 0.7
        assert config.llm["judgment"].model == "gpt-4o-mini"
        assert config.llm["judgment"].temperature == 0.3

    def test_llm_config_defaults(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """LLM設定のデフォルト値が適用される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.llm["default"].temperature == 0.7
        assert config.llm["default"].max_tokens == 1000

    def test_file_not_found(self) -> None:
        """存在しないファイルでFileNotFoundErrorが発生"""
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))

    def test_undefined_env_var(self, temp_config_dir: Path) -> None:
        """未設定の環境変数でEnvironmentVariableErrorが発生"""
        config_content = """
slack:
  bot_token: ${UNDEFINED_TOKEN_12345}
  app_token: ${UNDEFINED_APP_12345}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(EnvironmentVariableError):
            load_config(config_path)

    def test_missing_required_field_slack(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """必須フィールド（slack.bot_token）欠落でConfigValidationErrorが発生"""
        config_content = """
slack:
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "bot_token" in str(exc_info.value)

    def test_missing_required_section(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """必須セクション（slack）欠落でConfigValidationErrorが発生"""
        config_content = """
llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "slack" in str(exc_info.value)

    def test_missing_default_llm(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """llm.defaultが欠落でConfigValidationErrorが発生"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  judgment:
    model: "gpt-4o-mini"

persona:
  name: "myao"
  system_prompt: "test"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "default" in str(exc_info.value)

    def test_yaml_syntax_error(self, temp_config_dir: Path) -> None:
        """YAML構文エラーでyaml.YAMLErrorが発生"""
        config_content = """
slack:
  bot_token: [invalid yaml
  app_token: test
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(yaml.YAMLError):
            load_config(config_path)

    def test_string_path(self, temp_config_dir: Path, env_vars: dict[str, str]) -> None:
        """文字列パスでも読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(str(config_path))

        assert isinstance(config, Config)


class TestDataClasses:
    """データクラスのテスト"""

    def test_slack_config(self) -> None:
        """SlackConfigが正しく作成される"""
        config = SlackConfig(bot_token="token1", app_token="token2")
        assert config.bot_token == "token1"
        assert config.app_token == "token2"

    def test_llm_config_with_defaults(self) -> None:
        """LLMConfigのデフォルト値が正しい"""
        config = LLMConfig(model="gpt-4o")
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 1000

    def test_llm_config_custom_values(self) -> None:
        """LLMConfigのカスタム値が設定できる"""
        config = LLMConfig(model="gpt-4o", temperature=0.3, max_tokens=500)
        assert config.temperature == 0.3
        assert config.max_tokens == 500

    def test_persona_config(self) -> None:
        """PersonaConfigが正しく作成される"""
        config = PersonaConfig(name="myao", system_prompt="テストプロンプト")
        assert config.name == "myao"
        assert config.system_prompt == "テストプロンプト"

    def test_config(self) -> None:
        """Configが正しく作成される"""
        slack = SlackConfig(bot_token="t1", app_token="t2")
        llm = {"default": LLMConfig(model="gpt-4o")}
        persona = PersonaConfig(name="myao", system_prompt="test")
        memory = MemoryConfig(database_path="./data/memory.db")
        response = ResponseConfig()

        config = Config(
            slack=slack, llm=llm, persona=persona, memory=memory, response=response
        )

        assert config.slack == slack
        assert config.llm == llm
        assert config.persona == persona
        assert config.memory == memory
        assert config.response == response

    def test_response_config_with_defaults(self) -> None:
        """ResponseConfigのデフォルト値が正しい"""
        config = ResponseConfig()
        assert config.check_interval_seconds == 60
        assert config.min_wait_seconds == 300
        assert config.message_limit == 20

    def test_response_config_custom_values(self) -> None:
        """ResponseConfigのカスタム値が設定できる"""
        config = ResponseConfig(
            check_interval_seconds=30, min_wait_seconds=600, message_limit=50
        )
        assert config.check_interval_seconds == 30
        assert config.min_wait_seconds == 600
        assert config.message_limit == 50


class TestLoadConfigWithResponse:
    """load_config関数のResponseConfigテスト"""

    def test_load_config_with_response_section(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """responseセクションありの設定ファイルを読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  check_interval_seconds: 30
  min_wait_seconds: 600
  message_limit: 50
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.check_interval_seconds == 30
        assert config.response.min_wait_seconds == 600
        assert config.response.message_limit == 50

    def test_load_config_without_response_section(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """responseセクションなしの場合はデフォルト値が使用される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.check_interval_seconds == 60
        assert config.response.min_wait_seconds == 300
        assert config.response.message_limit == 20

    def test_load_config_with_partial_response_section(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """responseセクションが部分的な場合、残りはデフォルト値が使用される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  check_interval_seconds: 120
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.check_interval_seconds == 120
        assert config.response.min_wait_seconds == 300


class TestMemoryConfigDataClass:
    """MemoryConfigデータクラスのテスト"""

    def test_memory_config_with_defaults(self) -> None:
        """MemoryConfigのデフォルト値が正しい（database_pathのみ指定）"""
        config = MemoryConfig(database_path="./data/memory.db")
        assert config.database_path == "./data/memory.db"
        assert config.long_term_update_interval_seconds == 3600
        assert config.short_term_window_hours == 24
        assert config.long_term_summary_max_tokens == 500
        assert config.short_term_summary_max_tokens == 300
        assert config.memory_generation_llm == "default"

    def test_memory_config_custom_values(self) -> None:
        """MemoryConfigの全フィールドにカスタム値が設定できる"""
        config = MemoryConfig(
            database_path="./custom/memory.db",
            long_term_update_interval_seconds=7200,
            short_term_window_hours=48,
            long_term_summary_max_tokens=1000,
            short_term_summary_max_tokens=600,
            memory_generation_llm="memory",
        )
        assert config.database_path == "./custom/memory.db"
        assert config.long_term_update_interval_seconds == 7200
        assert config.short_term_window_hours == 48
        assert config.long_term_summary_max_tokens == 1000
        assert config.short_term_summary_max_tokens == 600
        assert config.memory_generation_llm == "memory"

    def test_memory_config_partial_values(self) -> None:
        """MemoryConfigの部分的なカスタム値が設定できる"""
        config = MemoryConfig(
            database_path="./data/memory.db",
            short_term_window_hours=12,
            memory_generation_llm="custom",
        )
        assert config.database_path == "./data/memory.db"
        assert config.long_term_update_interval_seconds == 3600  # default
        assert config.short_term_window_hours == 12
        assert config.long_term_summary_max_tokens == 500  # default
        assert config.short_term_summary_max_tokens == 300  # default
        assert config.memory_generation_llm == "custom"


class TestLoadConfigWithMemoryExtension:
    """load_config関数のMemoryConfig拡張テスト"""

    def test_load_config_with_all_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """全ての新しいmemoryフィールドを読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 7200
  short_term_window_hours: 48
  long_term_summary_max_tokens: 1000
  short_term_summary_max_tokens: 600
  memory_generation_llm: "memory"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.database_path == "./data/memory.db"
        assert config.memory.long_term_update_interval_seconds == 7200
        assert config.memory.short_term_window_hours == 48
        assert config.memory.long_term_summary_max_tokens == 1000
        assert config.memory.short_term_summary_max_tokens == 600
        assert config.memory.memory_generation_llm == "memory"

    def test_load_config_without_new_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """新しいmemoryフィールドがない場合はデフォルト値が使用される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.database_path == "./data/memory.db"
        assert config.memory.long_term_update_interval_seconds == 3600
        assert config.memory.short_term_window_hours == 24
        assert config.memory.long_term_summary_max_tokens == 500
        assert config.memory.short_term_summary_max_tokens == 300
        assert config.memory.memory_generation_llm == "default"

    def test_load_config_with_partial_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """memoryフィールドが部分的な場合、残りはデフォルト値が使用される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
  short_term_window_hours: 12
  memory_generation_llm: "custom"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.database_path == "./data/memory.db"
        assert config.memory.long_term_update_interval_seconds == 3600  # default
        assert config.memory.short_term_window_hours == 12
        assert config.memory.long_term_summary_max_tokens == 500  # default
        assert config.memory.short_term_summary_max_tokens == 300  # default
        assert config.memory.memory_generation_llm == "custom"

    def test_load_config_memory_generation_llm_nonexistent(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """存在しないLLM設定名でも読み込み成功（使用時に検証）"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
  memory_generation_llm: "nonexistent_llm"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.memory_generation_llm == "nonexistent_llm"


class TestResponseIntervalConfigDataClass:
    """ResponseIntervalConfigデータクラスのテスト"""

    def test_response_interval_config_with_defaults(self) -> None:
        """ResponseIntervalConfigのデフォルト値が正しい"""
        config = ResponseIntervalConfig()
        assert config.min == 3.0
        assert config.max == 10.0

    def test_response_interval_config_custom_values(self) -> None:
        """ResponseIntervalConfigのカスタム値が設定できる"""
        config = ResponseIntervalConfig(min=1.0, max=5.0)
        assert config.min == 1.0
        assert config.max == 5.0


class TestResponseConfigJitterRatio:
    """ResponseConfigのjitter_ratio関連テスト"""

    def test_response_config_jitter_ratio_default(self) -> None:
        """jitter_ratioのデフォルト値が0.3"""
        config = ResponseConfig()
        assert config.jitter_ratio == 0.3

    def test_response_config_jitter_ratio_custom(self) -> None:
        """jitter_ratioのカスタム値が設定できる"""
        config = ResponseConfig(jitter_ratio=0.5)
        assert config.jitter_ratio == 0.5

    def test_response_config_response_interval_default(self) -> None:
        """response_intervalのデフォルト値がNone"""
        config = ResponseConfig()
        assert config.response_interval is None

    def test_response_config_response_interval_custom(self) -> None:
        """response_intervalのカスタム値が設定できる"""
        interval = ResponseIntervalConfig(min=2.0, max=8.0)
        config = ResponseConfig(response_interval=interval)
        assert config.response_interval is not None
        assert config.response_interval.min == 2.0
        assert config.response_interval.max == 8.0


class TestLoadConfigWithJitterRatio:
    """load_config関数のjitter_ratio関連テスト"""

    def test_load_config_with_jitter_ratio(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """jitter_ratioが正しく読み込まれる"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  jitter_ratio: 0.5
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.jitter_ratio == 0.5

    def test_load_config_without_jitter_ratio(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """jitter_ratio未指定時はデフォルト値0.3"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  min_wait_seconds: 300
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.jitter_ratio == 0.3

    def test_load_config_jitter_ratio_negative_clipped(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """jitter_ratioが負の値の場合0.0にクリップ"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  jitter_ratio: -0.5
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.jitter_ratio == 0.0

    def test_load_config_jitter_ratio_over_one_clipped(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """jitter_ratioが1.0超の場合1.0にクリップ"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  jitter_ratio: 1.5
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.jitter_ratio == 1.0

    def test_load_config_with_response_interval(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """response_intervalが正しく読み込まれる"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  response_interval:
    min: 2.0
    max: 8.0
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.response_interval is not None
        assert config.response.response_interval.min == 2.0
        assert config.response.response_interval.max == 8.0

    def test_load_config_without_response_interval(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """response_interval未指定時はデフォルト値{min: 3.0, max: 10.0}"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

llm:
  default:
    model: "gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"

response:
  min_wait_seconds: 300
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.response.response_interval is not None
        assert config.response.response_interval.min == 3.0
        assert config.response.response_interval.max == 10.0
