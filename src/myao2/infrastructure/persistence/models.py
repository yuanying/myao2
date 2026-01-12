"""SQLModel table definitions."""

from datetime import datetime, timezone

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class MessageModel(SQLModel, table=True):
    """メッセージテーブル"""

    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(index=True)
    channel_id: str = Field(index=True)
    user_id: str
    user_name: str
    user_is_bot: bool = False
    text: str
    timestamp: datetime
    thread_ts: str | None = Field(default=None, index=True)
    mentions: str = ""  # JSON format: ["U123", "U456"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),
    )


class UserModel(SQLModel, table=True):
    """ユーザーテーブル"""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(unique=True, index=True)
    name: str
    is_bot: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChannelModel(SQLModel, table=True):
    """チャンネルテーブル"""

    __tablename__ = "channels"

    id: int | None = Field(default=None, primary_key=True)
    channel_id: str = Field(unique=True, index=True)
    name: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JudgmentCacheModel(SQLModel, table=True):
    """応答判定キャッシュテーブル"""

    __tablename__ = "judgment_caches"

    id: int | None = Field(default=None, primary_key=True)
    channel_id: str = Field(index=True)
    thread_ts: str | None = Field(default=None, index=True)
    should_respond: bool
    confidence: float
    reason: str
    latest_message_ts: str  # キャッシュ作成時の最新メッセージのタイムスタンプ
    next_check_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("channel_id", "thread_ts", name="uq_channel_thread"),
    )


class MemoryModel(SQLModel, table=True):
    """記憶の永続化モデル"""

    __tablename__ = "memories"

    id: int | None = Field(default=None, primary_key=True)
    scope: str = Field(index=True)
    scope_id: str = Field(index=True)
    memory_type: str = Field(index=True)
    content: str
    created_at: datetime
    updated_at: datetime
    source_message_count: int
    source_latest_message_ts: str | None = None

    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "memory_type", name="uq_scope_type"),
    )


class MemoModel(SQLModel, table=True):
    """メモテーブル"""

    __tablename__ = "memos"

    id: str = Field(primary_key=True)  # UUID を文字列として保存
    name: str = Field(unique=True, index=True)  # ユニークな名前
    content: str
    priority: int = Field(index=True)
    tags: list[str] = Field(default_factory=list, sa_type=JSON)  # SQLite JSON型
    detail: str | None = Field(default=None)
    created_at: datetime
    updated_at: datetime = Field(index=True)
