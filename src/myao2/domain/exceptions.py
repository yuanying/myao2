"""Domain exceptions."""


class ChannelNotAccessibleError(Exception):
    """チャンネルにアクセスできない場合に発生する例外

    ボットがチャンネルから退出した場合や、
    チャンネルがアーカイブされた場合などに発生する。
    """

    def __init__(self, channel_id: str, message: str = "") -> None:
        """初期化

        Args:
            channel_id: アクセスできないチャンネルのID
            message: エラーメッセージ（オプション）
        """
        self.channel_id = channel_id
        super().__init__(message or f"Channel {channel_id} is not accessible")
