"""設定データクラス"""

from dataclasses import dataclass


@dataclass
class SlackConfig:
    """Slack接続設定"""

    bot_token: str
    app_token: str


@dataclass
class LLMConfig:
    """LLM設定（LiteLLMのcompletionに渡すdict）"""

    model: str
    temperature: float = 0.7
    max_tokens: int = 1000


@dataclass
class PersonaConfig:
    """ペルソナ設定"""

    name: str
    system_prompt: str


@dataclass
class MemoryConfig:
    """記憶設定"""

    database_path: str
    long_term_update_interval_seconds: int = 3600


@dataclass
class LoggingConfig:
    """ログ設定"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    loggers: dict[str, str] | None = None
    debug_llm_messages: bool = False


@dataclass
class ResponseConfig:
    """自律応答設定"""

    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
    message_limit: int = 20


@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    llm: dict[str, LLMConfig]
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig
    logging: LoggingConfig | None = None
