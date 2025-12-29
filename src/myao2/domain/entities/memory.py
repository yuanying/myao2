"""Memory entity for long-term and short-term memories."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class MemoryScope(Enum):
    """記憶のスコープ"""

    WORKSPACE = "workspace"
    CHANNEL = "channel"
    THREAD = "thread"


class MemoryType(Enum):
    """記憶の種類"""

    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"


VALID_MEMORY_COMBINATIONS: set[tuple[MemoryScope, MemoryType]] = {
    (MemoryScope.WORKSPACE, MemoryType.LONG_TERM),
    (MemoryScope.WORKSPACE, MemoryType.SHORT_TERM),
    (MemoryScope.CHANNEL, MemoryType.LONG_TERM),
    (MemoryScope.CHANNEL, MemoryType.SHORT_TERM),
    (MemoryScope.THREAD, MemoryType.SHORT_TERM),
}


def is_valid_memory_combination(scope: MemoryScope, memory_type: MemoryType) -> bool:
    """記憶のスコープとタイプの組み合わせが有効かを判定

    Args:
        scope: 記憶のスコープ
        memory_type: 記憶の種類

    Returns:
        有効な組み合わせの場合 True
    """
    return (scope, memory_type) in VALID_MEMORY_COMBINATIONS


@dataclass(frozen=True)
class Memory:
    """記憶エンティティ

    記憶は (scope, scope_id, memory_type) の組み合わせで一意に識別される。
    例えば、チャンネル "C123" の長期記憶は1つだけ存在する。

    Attributes:
        scope: 記憶のスコープ（WORKSPACE / CHANNEL / THREAD）
        scope_id: スコープ固有の ID
            - WORKSPACE: workspace_id（通常は固定値 "default"）
            - CHANNEL: channel_id
            - THREAD: "{channel_id}:{thread_ts}"
        memory_type: 記憶の種類（LONG_TERM / SHORT_TERM）
        content: 記憶の内容（LLM 生成テキスト）
        created_at: 作成日時
        updated_at: 更新日時
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts
    """

    scope: MemoryScope
    scope_id: str
    memory_type: MemoryType
    content: str
    created_at: datetime
    updated_at: datetime
    source_message_count: int
    source_latest_message_ts: str | None = None

    def __post_init__(self) -> None:
        """バリデーション"""
        if not is_valid_memory_combination(self.scope, self.memory_type):
            raise ValueError(
                f"Invalid memory combination: scope={self.scope}, "
                f"memory_type={self.memory_type}"
            )


def create_memory(
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    content: str,
    source_message_count: int,
    source_latest_message_ts: str | None = None,
) -> Memory:
    """Memory エンティティを生成する

    Args:
        scope: 記憶のスコープ
        scope_id: スコープ固有の ID
        memory_type: 記憶の種類
        content: 記憶の内容
        source_message_count: 生成に使用したメッセージ数
        source_latest_message_ts: 生成に使用した最新メッセージの ts

    Returns:
        Memory エンティティ

    Raises:
        ValueError: 無効なスコープとタイプの組み合わせの場合
    """
    now = datetime.now(timezone.utc)
    return Memory(
        scope=scope,
        scope_id=scope_id,
        memory_type=memory_type,
        content=content,
        created_at=now,
        updated_at=now,
        source_message_count=source_message_count,
        source_latest_message_ts=source_latest_message_ts,
    )


def make_thread_scope_id(channel_id: str, thread_ts: str) -> str:
    """スレッドの scope_id を生成する

    Args:
        channel_id: チャンネル ID
        thread_ts: スレッドのタイムスタンプ

    Returns:
        "{channel_id}:{thread_ts}" 形式の scope_id
    """
    return f"{channel_id}:{thread_ts}"


def parse_thread_scope_id(scope_id: str) -> tuple[str, str]:
    """スレッドの scope_id をパースする

    Args:
        scope_id: "{channel_id}:{thread_ts}" 形式の scope_id

    Returns:
        (channel_id, thread_ts) のタプル

    Raises:
        ValueError: 無効な形式の場合
    """
    parts = scope_id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid thread scope_id format: {scope_id}")
    return parts[0], parts[1]
