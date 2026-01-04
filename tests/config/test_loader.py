"""設定ローダーのテスト"""

import os
from pathlib import Path
from typing import Generator

import pytest
import yaml

from myao2.config import (
    AgentConfig,
    Config,
    ConfigValidationError,
    EnvironmentVariableError,
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
        "TEST_API_KEY": "sk-test-api-key",
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


def _get_minimal_agents_config_yaml() -> str:
    """テスト用の最小agents設定のYAML文字列を返す"""
    return """
agents:
  response:
    model_id: "openai/gpt-4o"
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"
"""


class TestLoadConfig:
    """load_config関数のテスト"""

    def test_load_valid_config(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """有効な設定ファイルを読み込める"""
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        assert "response" in config.agents
        assert config.agents["response"].model_id == "openai/gpt-4o"
        assert config.persona.name == "myao"
        assert config.memory.database_path == "./data/memory.db"

    def test_env_var_expansion(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """環境変数が正しく展開される"""
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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

    def test_file_not_found(self) -> None:
        """存在しないファイルでFileNotFoundErrorが発生"""
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))

    def test_undefined_env_var(self, temp_config_dir: Path) -> None:
        """未設定の環境変数でEnvironmentVariableErrorが発生"""
        config_content = f"""
slack:
  bot_token: ${{UNDEFINED_TOKEN_12345}}
  app_token: ${{UNDEFINED_APP_12345}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
{_get_minimal_agents_config_yaml()}
persona:
  name: "myao"
  system_prompt: "test"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "slack" in str(exc_info.value)

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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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

    def test_persona_config(self) -> None:
        """PersonaConfigが正しく作成される"""
        config = PersonaConfig(name="myao", system_prompt="テストプロンプト")
        assert config.name == "myao"
        assert config.system_prompt == "テストプロンプト"

    def test_config(self) -> None:
        """Configが正しく作成される"""
        slack = SlackConfig(bot_token="t1", app_token="t2")
        agents = {
            "response": AgentConfig(model_id="openai/gpt-4o"),
            "judgment": AgentConfig(model_id="openai/gpt-4o-mini"),
            "memory": AgentConfig(model_id="openai/gpt-4o"),
        }
        persona = PersonaConfig(name="myao", system_prompt="test")
        memory = MemoryConfig(database_path="./data/memory.db")
        response = ResponseConfig()

        config = Config(
            slack=slack,
            agents=agents,
            persona=persona,
            memory=memory,
            response=response,
        )

        assert config.slack == slack
        assert config.agents == agents
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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

    def test_memory_config_custom_values(self) -> None:
        """MemoryConfigの全フィールドにカスタム値が設定できる"""
        config = MemoryConfig(
            database_path="./custom/memory.db",
            long_term_update_interval_seconds=7200,
            short_term_window_hours=48,
            long_term_summary_max_tokens=1000,
            short_term_summary_max_tokens=600,
        )
        assert config.database_path == "./custom/memory.db"
        assert config.long_term_update_interval_seconds == 7200
        assert config.short_term_window_hours == 48
        assert config.long_term_summary_max_tokens == 1000
        assert config.short_term_summary_max_tokens == 600

    def test_memory_config_partial_values(self) -> None:
        """MemoryConfigの部分的なカスタム値が設定できる"""
        config = MemoryConfig(
            database_path="./data/memory.db",
            short_term_window_hours=12,
        )
        assert config.database_path == "./data/memory.db"
        assert config.long_term_update_interval_seconds == 3600  # default
        assert config.short_term_window_hours == 12
        assert config.long_term_summary_max_tokens == 500  # default
        assert config.short_term_summary_max_tokens == 300  # default


class TestLoadConfigWithMemoryExtension:
    """load_config関数のMemoryConfig拡張テスト"""

    def test_load_config_with_all_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """全ての新しいmemoryフィールドを読み込める"""
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
  long_term_update_interval_seconds: 7200
  short_term_window_hours: 48
  long_term_summary_max_tokens: 1000
  short_term_summary_max_tokens: 600
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.database_path == "./data/memory.db"
        assert config.memory.long_term_update_interval_seconds == 7200
        assert config.memory.short_term_window_hours == 48
        assert config.memory.long_term_summary_max_tokens == 1000
        assert config.memory.short_term_summary_max_tokens == 600

    def test_load_config_without_new_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """新しいmemoryフィールドがない場合はデフォルト値が使用される"""
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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

    def test_load_config_with_partial_memory_fields(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """memoryフィールドが部分的な場合、残りはデフォルト値が使用される"""
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
  short_term_window_hours: 12
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.memory.database_path == "./data/memory.db"
        assert config.memory.long_term_update_interval_seconds == 3600  # default
        assert config.memory.short_term_window_hours == 12
        assert config.memory.long_term_summary_max_tokens == 500  # default
        assert config.memory.short_term_summary_max_tokens == 300  # default


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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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
        config_content = f"""
slack:
  bot_token: ${{TEST_BOT_TOKEN}}
  app_token: ${{TEST_APP_TOKEN}}
{_get_minimal_agents_config_yaml()}
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


class TestAgentConfigDataClass:
    """AgentConfigデータクラスのテスト"""

    def test_agent_config_required_model_id(self) -> None:
        """AgentConfigはmodel_idが必須"""
        config = AgentConfig(model_id="openai/gpt-4o")
        assert config.model_id == "openai/gpt-4o"

    def test_agent_config_with_defaults(self) -> None:
        """AgentConfigのデフォルト値が正しい"""
        config = AgentConfig(model_id="openai/gpt-4o")
        assert config.model_id == "openai/gpt-4o"
        assert config.params == {}
        assert config.client_args == {}

    def test_agent_config_with_params(self) -> None:
        """AgentConfigのparamsが設定できる"""
        config = AgentConfig(
            model_id="openai/gpt-4o",
            params={"temperature": 0.7, "max_tokens": 1000},
        )
        assert config.params == {"temperature": 0.7, "max_tokens": 1000}

    def test_agent_config_with_client_args(self) -> None:
        """AgentConfigのclient_argsが設定できる"""
        config = AgentConfig(
            model_id="openai/gpt-4o",
            client_args={"api_key": "sk-test"},
        )
        assert config.client_args == {"api_key": "sk-test"}

    def test_agent_config_full(self) -> None:
        """AgentConfigの全フィールドが設定できる"""
        config = AgentConfig(
            model_id="openai/gpt-4o",
            params={"temperature": 0.7},
            client_args={"api_key": "sk-test", "api_base": "https://api.example.com"},
        )
        assert config.model_id == "openai/gpt-4o"
        assert config.params == {"temperature": 0.7}
        assert config.client_args == {
            "api_key": "sk-test",
            "api_base": "https://api.example.com",
        }


class TestLoadConfigWithAgents:
    """load_config関数のagentsセクションテスト"""

    def test_load_config_with_all_agents(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """全agents設定ありで3つのAgentConfigが読み込まれる"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
    params:
      temperature: 0.7
      max_tokens: 1000
    client_args:
      api_key: ${TEST_API_KEY}

  judgment:
    model_id: "openai/gpt-4o-mini"
    params:
      temperature: 0.3
      max_tokens: 500
    client_args:
      api_key: ${TEST_API_KEY}

  memory:
    model_id: "openai/gpt-4o"
    params:
      temperature: 0.5
      max_tokens: 800
    client_args:
      api_key: ${TEST_API_KEY}

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert "response" in config.agents
        assert "judgment" in config.agents
        assert "memory" in config.agents
        assert config.agents["response"].model_id == "openai/gpt-4o"
        assert config.agents["response"].params == {
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        assert config.agents["response"].client_args == {"api_key": "sk-test-api-key"}
        assert config.agents["judgment"].model_id == "openai/gpt-4o-mini"
        assert config.agents["memory"].model_id == "openai/gpt-4o"

    def test_load_config_missing_response_agent(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """responseが欠落でConfigValidationError"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "response" in str(exc_info.value)

    def test_load_config_missing_judgment_agent(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """judgmentが欠落でConfigValidationError"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "judgment" in str(exc_info.value)

    def test_load_config_missing_memory_agent(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """memoryが欠落でConfigValidationError"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
  judgment:
    model_id: "openai/gpt-4o-mini"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "memory" in str(exc_info.value)

    def test_load_config_missing_model_id(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """model_idが欠落でConfigValidationError"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    params:
      temperature: 0.7
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "model_id" in str(exc_info.value)

    def test_load_config_params_omitted(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """params省略で空のdictがデフォルト"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.agents["response"].params == {}
        assert config.agents["judgment"].params == {}
        assert config.agents["memory"].params == {}

    def test_load_config_client_args_omitted(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """client_args省略で空のdictがデフォルト"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.agents["response"].client_args == {}
        assert config.agents["judgment"].client_args == {}
        assert config.agents["memory"].client_args == {}

    def test_load_config_client_args_env_var_expansion(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """client_argsに${ENV_VAR}で環境変数が展開される"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
    client_args:
      api_key: ${TEST_API_KEY}
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert config.agents["response"].client_args == {"api_key": "sk-test-api-key"}

    def test_load_config_custom_agent(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """追加のagent設定（例: custom）も読み込める"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

agents:
  response:
    model_id: "openai/gpt-4o"
  judgment:
    model_id: "openai/gpt-4o-mini"
  memory:
    model_id: "openai/gpt-4o"
  custom:
    model_id: "anthropic/claude-3-opus"
    params:
      temperature: 0.9

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        config = load_config(config_path)

        assert "custom" in config.agents
        assert config.agents["custom"].model_id == "anthropic/claude-3-opus"
        assert config.agents["custom"].params == {"temperature": 0.9}

    def test_load_config_missing_agents_section(
        self, temp_config_dir: Path, env_vars: dict[str, str]
    ) -> None:
        """agentsセクション欠落でConfigValidationError（後方互換性テスト）"""
        config_content = """
slack:
  bot_token: ${TEST_BOT_TOKEN}
  app_token: ${TEST_APP_TOKEN}

persona:
  name: "myao"
  system_prompt: "test"

memory:
  database_path: "./data/memory.db"
"""
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_path)
        assert "agents" in str(exc_info.value)
