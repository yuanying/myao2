"""SQLModel table definitions."""

from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
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
