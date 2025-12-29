"""JudgmentCache entity for response judgment caching."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class JudgmentCache:
    """応答判定キャッシュ

    スレッド/トップレベル単位で判定結果をキャッシュし、
    次回判定日時まで再判定をスキップする。

    Attributes:
        channel_id: チャンネル ID
        thread_ts: スレッド識別子（トップレベルは None）
        should_respond: 最後の判定結果
        confidence: 判定の確信度（0.0 - 1.0）
        reason: 判定理由
        latest_message_ts: キャッシュ作成時の最新メッセージのタイムスタンプ
        next_check_at: 次回判定日時（この時刻以降に再判定）
        created_at: 作成日時
        updated_at: 更新日時
    """

    channel_id: str
    thread_ts: str | None
    should_respond: bool
    confidence: float
    reason: str
    latest_message_ts: str
    next_check_at: datetime
    created_at: datetime
    updated_at: datetime

    @property
    def scope_key(self) -> str:
        """スコープを識別するキーを返す"""
        return f"{self.channel_id}:{self.thread_ts or 'top'}"

    def is_valid(self, current_time: datetime, current_latest_message_ts: str) -> bool:
        """キャッシュが有効かどうか判定

        Args:
            current_time: 現在時刻
            current_latest_message_ts: 現在の最新メッセージのタイムスタンプ

        Returns:
            next_check_at より前かつ新しいメッセージがなければ True（スキップ可能）
        """
        if current_time >= self.next_check_at:
            return False
        # 新しいメッセージがあればキャッシュ無効
        if current_latest_message_ts != self.latest_message_ts:
            return False
        return True
