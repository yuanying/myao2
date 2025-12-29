"""設定データクラス"""

from dataclasses import dataclass, field


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
class JudgmentSkipThreshold:
    """判定スキップ閾値設定

    Attributes:
        min_confidence: 最小 confidence（この値以上で適用）
        skip_seconds: スキップする秒数
    """

    min_confidence: float
    skip_seconds: int


@dataclass
class JudgmentSkipConfig:
    """応答判定スキップ設定

    Attributes:
        enabled: スキップ機能有効/無効
        thresholds: confidence 閾値リスト（高い順にソート推奨）
        default_skip_seconds: どの閾値にも該当しない場合のスキップ秒数
    """

    enabled: bool = True
    thresholds: list[JudgmentSkipThreshold] = field(
        default_factory=lambda: [
            JudgmentSkipThreshold(min_confidence=0.9, skip_seconds=43200),  # 12時間
            JudgmentSkipThreshold(min_confidence=0.7, skip_seconds=3600),  # 1時間
        ]
    )
    default_skip_seconds: int = 600  # 10分


@dataclass
class ResponseConfig:
    """自律応答設定"""

    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
    message_limit: int = 20
    max_message_age_seconds: int = 43200  # 12 hours
    judgment_skip: JudgmentSkipConfig | None = None


@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    llm: dict[str, LLMConfig]
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig
    logging: LoggingConfig | None = None
