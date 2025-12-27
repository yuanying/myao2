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
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    llm: dict[str, LLMConfig]
    persona: PersonaConfig
