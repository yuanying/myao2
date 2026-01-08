"""設定データクラス"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlackConfig:
    """Slack接続設定"""

    bot_token: str
    app_token: str


@dataclass
class AgentConfig:
    """strands-agents用設定

    Attributes:
        model_id: LiteLLMのモデルID（例: "openai/gpt-4o"）
        system_prompt: Agent固有のシステムプロンプト（オプション）
        params: LLMパラメーター（temperature, max_tokens等）
        client_args: LiteLLMクライアント引数（api_key, api_base等）
    """

    model_id: str
    system_prompt: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    client_args: dict[str, Any] = field(default_factory=dict)


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
    short_term_window_hours: int = 24
    long_term_summary_max_tokens: int = 500
    short_term_summary_max_tokens: int = 300


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
class ResponseIntervalConfig:
    """スレッド間応答間隔設定"""

    min: float = 3.0
    max: float = 10.0


@dataclass
class ResponseConfig:
    """自律応答設定"""

    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
    jitter_ratio: float = 0.3
    message_limit: int = 20
    max_message_age_seconds: int = 43200  # 12 hours
    channel_messages_limit: int = 50
    active_channel_days: int = 7
    thread_memory_days: int = 7
    judgment_skip: JudgmentSkipConfig | None = None
    response_interval: ResponseIntervalConfig | None = None


@dataclass
class WebFetchConfig:
    """Web Fetch ツール設定

    Attributes:
        enabled: ツール有効/無効
        api_endpoint: Web Fetch API のエンドポイント
        timeout_seconds: タイムアウト秒数
        max_content_length: 取得コンテンツの最大文字数
    """

    api_endpoint: str
    enabled: bool = True
    timeout_seconds: int = 60
    max_content_length: int = 20000


@dataclass
class ToolsConfig:
    """ツール設定

    Attributes:
        web_fetch: Web Fetch ツール設定
    """

    web_fetch: WebFetchConfig | None = None


@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    agents: dict[str, AgentConfig]
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig
    logging: LoggingConfig | None = None
    tools: ToolsConfig | None = None
