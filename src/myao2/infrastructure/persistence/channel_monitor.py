"""DB implementation of ChannelMonitor."""

from datetime import datetime, timedelta, timezone

from myao2.domain.entities import Channel, Message
from myao2.domain.repositories import ChannelRepository, MessageRepository

# Limit for fetching all messages
_MESSAGE_LIMIT = 200


class DBChannelMonitor:
    """DB 実装の ChannelMonitor

    MessageRepository と ChannelRepository を使用してデータベースから
    チャンネル情報とメッセージを取得する。
    Slack API を呼び出さないため、高速かつレート制限の心配がない。
    """

    def __init__(
        self,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        bot_user_id: str,
    ) -> None:
        """初期化

        Args:
            message_repository: メッセージリポジトリ
            channel_repository: チャンネルリポジトリ
            bot_user_id: ボットのユーザー ID
        """
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._bot_user_id = bot_user_id

    async def get_channels(self) -> list[Channel]:
        """DB からチャンネル一覧を取得する

        Returns:
            チャンネルリスト
        """
        return await self._channel_repository.find_all()

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """DB から最近のメッセージを取得する

        Args:
            channel_id: チャンネル ID
            since: この時刻以降のメッセージを取得
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        if since is not None:
            return await self._message_repository.find_by_channel_since(
                channel_id, since, limit
            )
        return await self._message_repository.find_by_channel(channel_id, limit)

    async def get_unreplied_messages(
        self,
        channel_id: str,
        min_wait_seconds: int,
        max_message_age_seconds: int | None = None,
    ) -> list[Message]:
        """未応答メッセージを DB から取得する

        指定時間以上経過し、かつボットが応答していないメッセージを取得する。
        スレッド内のメッセージも含む。

        Args:
            channel_id: チャンネル ID
            min_wait_seconds: 最低待機時間（秒）
            max_message_age_seconds: 最大メッセージ経過時間（秒）。
                この時間より古いメッセージは除外する。None の場合は制限なし。

        Returns:
            未応答メッセージリスト
        """
        now = datetime.now(timezone.utc)
        cutoff_ts = (now - timedelta(seconds=min_wait_seconds)).timestamp()

        # 最大経過時間を計算
        min_timestamp = None
        if max_message_age_seconds is not None:
            min_timestamp = now - timedelta(seconds=max_message_age_seconds)

        # ボットを含む全メッセージを一度に取得
        all_messages = await self._message_repository.find_all_in_channel(
            channel_id=channel_id,
            limit=_MESSAGE_LIMIT,
            min_timestamp=min_timestamp,
        )

        # スレッドごとにメッセージをグループ化
        # key: thread_ts (None の場合はトップレベル)
        thread_messages: dict[str, list[Message]] = {}
        channel_messages: list[Message] = []

        # 第1パス: thread_ts のセットを収集
        thread_ts_set: set[str] = set()
        for msg in all_messages:
            if msg.thread_ts:
                thread_ts_set.add(msg.thread_ts)

        # 第2パス: メッセージを分類
        for msg in all_messages:
            if msg.thread_ts:
                # スレッド返信
                if msg.thread_ts not in thread_messages:
                    thread_messages[msg.thread_ts] = []
                thread_messages[msg.thread_ts].append(msg)
            elif msg.id in thread_ts_set:
                # スレッド親（自身の id が thread_ts として参照されている）
                if msg.id not in thread_messages:
                    thread_messages[msg.id] = []
                thread_messages[msg.id].append(msg)
            else:
                # 純粋なトップレベルメッセージ
                channel_messages.append(msg)

        unreplied_messages: list[Message] = []

        # トップレベルメッセージの処理
        # 最新メッセージがボットでなく、時間条件を満たす場合のみ追加
        if channel_messages:
            latest_msg = channel_messages[0]
            if (
                latest_msg.user.id != self._bot_user_id
                and latest_msg.timestamp.timestamp() <= cutoff_ts
            ):
                unreplied_messages.append(latest_msg)

        # スレッド内メッセージの処理
        for thread_ts, messages in thread_messages.items():
            if not messages:
                continue
            latest_msg = messages[0]
            if (
                latest_msg.user.id != self._bot_user_id
                and latest_msg.timestamp.timestamp() <= cutoff_ts
            ):
                unreplied_messages.append(latest_msg)

        return unreplied_messages
