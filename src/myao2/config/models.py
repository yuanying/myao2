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
class LLMConfig:
    """LLM設定（後方互換性用、extra08f で削除予定）

    Note:
        このクラスは後方互換性のために維持されています。
        新規コードでは AgentConfig を使用してください。
    """

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
    short_term_window_hours: int = 24
    long_term_summary_max_tokens: int = 500
    short_term_summary_max_tokens: int = 300
    # 後方互換性用（extra08f で削除予定）
    memory_generation_llm: str = "memory"


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
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    agents: dict[str, AgentConfig]
    persona: PersonaConfig
    memory: MemoryConfig
    response: ResponseConfig
    logging: LoggingConfig | None = None
    # 後方互換性用（extra08f で削除予定）
    _llm_compat: dict[str, LLMConfig] | None = field(default=None, repr=False)

    def __init__(
        self,
        slack: SlackConfig,
        persona: PersonaConfig,
        memory: MemoryConfig,
        response: ResponseConfig,
        agents: dict[str, AgentConfig] | None = None,
        logging: LoggingConfig | None = None,
        *,
        llm: dict[str, LLMConfig] | None = None,  # 後方互換性用（extra08f で削除予定）
    ) -> None:
        self.slack = slack
        self.persona = persona
        self.memory = memory
        self.response = response
        self.logging = logging
        # llm= が指定された場合は _llm_compat に保存し、agents としても使用
        if llm is not None:
            self._llm_compat = llm
            self.agents = llm  # type: ignore[assignment]
        elif agents is not None:
            self._llm_compat = None
            self.agents = agents
        else:
            self._llm_compat = None
            self.agents = {}

    @property
    def llm(self) -> dict[str, LLMConfig]:
        """後方互換性用プロパティ（extra08f で削除予定）"""
        if self._llm_compat is not None:
            return self._llm_compat
        return self.agents  # type: ignore[return-value]
