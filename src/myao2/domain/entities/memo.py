"""Memo entity for LLM-managed notes."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Memo:
    """メモエンティティ

    Attributes:
        id: メモの一意識別子（UUID）
        content: メモ本文（50文字程度を推奨）
        priority: 優先度（1-5、5が最高）
        tags: タグリスト（最大3タグ）
        detail: 詳細情報（edit_memoで上書き更新）
        created_at: 作成日時
        updated_at: 更新日時
    """

    id: UUID
    content: str
    priority: int
    tags: list[str]
    detail: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """バリデーション"""
        if not 1 <= self.priority <= 5:
            raise ValueError("Priority must be between 1 and 5")
        if not self.content.strip():
            raise ValueError("Content cannot be empty")
        if len(self.tags) > 3:
            raise ValueError("Maximum 3 tags allowed per memo")

    @property
    def has_detail(self) -> bool:
        """詳細情報があるかどうか"""
        return self.detail is not None and len(self.detail.strip()) > 0


@dataclass(frozen=True)
class TagStats:
    """タグ統計情報

    Attributes:
        tag: タグ名
        count: 使用数
        latest_updated_at: 最新更新日時
    """

    tag: str
    count: int
    latest_updated_at: datetime


def create_memo(
    content: str,
    priority: int,
    tags: list[str] | None = None,
) -> Memo:
    """Memo エンティティを生成する

    Args:
        content: メモの内容
        priority: 優先度（1-5）
        tags: タグリスト（省略時は空リスト）

    Returns:
        Memo エンティティ

    Raises:
        ValueError: バリデーションエラーの場合
    """
    now = datetime.now(timezone.utc)
    return Memo(
        id=uuid4(),
        content=content,
        priority=priority,
        tags=tags or [],
        detail=None,
        created_at=now,
        updated_at=now,
    )
