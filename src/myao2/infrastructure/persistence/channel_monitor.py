"""DB implementation of ChannelMonitor."""

from datetime import datetime, timezone

from myao2.domain.entities import Channel, Message
from myao2.domain.repositories import ChannelRepository, MessageRepository


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
    ) -> list[Message]:
        """未応答メッセージを DB から取得する

        指定時間以上経過し、かつボットが応答していないメッセージを取得する。

        Args:
            channel_id: チャンネル ID
            min_wait_seconds: 最低待機時間（秒）

        Returns:
            未応答メッセージリスト
        """
        now = datetime.now(timezone.utc)
        cutoff_timestamp = now.timestamp() - min_wait_seconds

        # チャンネルの最近のメッセージを取得
        messages = await self._message_repository.find_by_channel(channel_id, limit=50)

        # ボットのメッセージ時刻を収集
        bot_message_times: list[float] = []
        for msg in messages:
            if msg.user.id == self._bot_user_id:
                bot_message_times.append(msg.timestamp.timestamp())

        unreplied_messages: list[Message] = []

        for msg in messages:
            # ボット自身のメッセージはスキップ
            if msg.user.id == self._bot_user_id:
                continue

            # 最近すぎるメッセージはスキップ
            msg_ts = msg.timestamp.timestamp()
            if msg_ts > cutoff_timestamp:
                continue

            # このメッセージ以降にボットが返信しているかチェック
            bot_replied = False
            for bot_time in bot_message_times:
                if bot_time > msg_ts:
                    bot_replied = True
                    break

            if not bot_replied:
                unreplied_messages.append(msg)

        return unreplied_messages
