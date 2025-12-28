# 02: チャンネル監視サービス

## 目的

ボットが参加しているチャンネルを監視し、
未応答メッセージを検出するサービスを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/channel_monitor.py` | ChannelMonitor Protocol |
| `src/myao2/domain/entities/channel_state.py` | ChannelState エンティティ（オプション） |
| `src/myao2/infrastructure/slack/channel_monitor.py` | SlackChannelMonitor 実装 |
| `tests/infrastructure/slack/test_channel_monitor.py` | テスト |

---

## 依存関係

- タスク 01（ResponseConfig）の check_interval_seconds を使用

---

## インターフェース設計

### ChannelMonitor Protocol

```python
class ChannelMonitor(Protocol):
    """チャンネル監視サービス

    ボットが参加しているチャンネルを監視し、
    応答判定が必要なメッセージを検出する。
    """

    async def get_channels(self) -> list[Channel]:
        """ボットが参加しているチャンネル一覧を取得する

        Returns:
            チャンネルリスト
        """
        ...

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルの最近のメッセージを取得する

        Args:
            channel_id: チャンネル ID
            since: この時刻以降のメッセージを取得（None の場合は制限なし）
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    async def get_unreplied_messages(
        self,
        channel_id: str,
        min_wait_seconds: int,
    ) -> list[Message]:
        """未応答メッセージを取得する

        指定時間以上経過し、かつボットが応答していないメッセージを取得する。

        Args:
            channel_id: チャンネル ID
            min_wait_seconds: 最低待機時間（秒）

        Returns:
            未応答メッセージリスト
        """
        ...
```

---

## 処理フロー

### get_unreplied_messages の判定ロジック

1. チャンネルの最近のメッセージを取得
2. 各メッセージについて以下を判定：
   - 投稿時刻が現在時刻 - min_wait_seconds より前か
   - ボット自身のメッセージではないか
   - 同一スレッド/チャンネルでボットが既に応答していないか
3. 条件を満たすメッセージを返す

### 応答済み判定

- スレッドメッセージの場合：同一スレッドでそのメッセージ以降にボットのメッセージがあれば応答済み
- チャンネルメッセージの場合：そのメッセージ以降にボットのメッセージがあれば応答済み

---

## Slack API 使用

### 使用する API

| API | 用途 |
|-----|------|
| `users.conversations` | ボットが参加しているチャンネル一覧 |
| `conversations.history` | チャンネルのメッセージ履歴 |
| `conversations.replies` | スレッドのメッセージ履歴 |

### API 呼び出し頻度

- get_channels: 起動時 + 定期的に更新（数分間隔）
- get_recent_messages: check_interval_seconds ごと

---

## テストケース

### get_channels

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常系 | チャンネルあり | チャンネルリストが返る |
| 正常系 | チャンネルなし | 空リストが返る |

### get_unreplied_messages

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 未応答メッセージあり | 待機時間経過 | メッセージが返る |
| 待機時間未経過 | 投稿直後 | 空リストが返る |
| ボット応答済み | 同一スレッドに応答 | 空リストが返る |
| ボット自身のメッセージ | ボットが投稿 | 空リストが返る |

---

## 設計上の考慮事項

### パフォーマンス

- チャンネル一覧はキャッシュ可能（数分間有効）
- 大量のメッセージがある場合は limit で制限
- 新しいメッセージを優先して処理する

### エラーハンドリング

- API エラー時は空リストを返す（次回リトライ）
- 個別チャンネルのエラーは他チャンネルに影響しない

---

## 完了基準

- [ ] ChannelMonitor Protocol が定義されている
- [ ] SlackChannelMonitor が実装されている
- [ ] ボットが参加しているチャンネルを取得できる
- [ ] 未応答メッセージを正しく検出できる
- [ ] 全テストケースが通過する
