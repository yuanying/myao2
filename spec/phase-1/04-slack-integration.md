# 04: Slack連携

## 目的

Slack Bolt を使ったメッセージ受信・送信を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/slack/client.py` | Bolt アプリケーション設定 |
| `src/myao2/infrastructure/slack/messaging.py` | MessagingService 実装 |
| `src/myao2/infrastructure/slack/event_adapter.py` | Slackイベント→Domainエンティティ変換 |
| `src/myao2/presentation/slack_handlers.py` | イベントハンドラ |
| `tests/infrastructure/slack/test_messaging.py` | メッセージングのテスト |
| `tests/infrastructure/slack/test_event_adapter.py` | アダプターのテスト |

---

## Slack Bolt の設定

### Socket Mode

- WebSocket による接続（HTTPエンドポイント不要）
- App-Level Token（`xapp-...`）を使用
- 開発環境でもローカルで動作可能

### 必要なスコープ

| スコープ | 用途 |
|---------|------|
| `app_mentions:read` | メンションイベントの受信 |
| `chat:write` | メッセージの送信 |
| `channels:history` | チャンネル履歴の読み取り（Phase 2以降で使用） |
| `users:read` | ユーザー情報の取得 |

### イベント購読

| イベント | 用途 |
|---------|------|
| `app_mention` | ボットがメンションされた時 |

---

## インターフェース設計

### `src/myao2/infrastructure/slack/client.py`

#### create_slack_app

```
def create_slack_app(config: SlackConfig) -> App:
    """Slack Bolt アプリケーションを生成する

    Args:
        config: Slack接続設定

    Returns:
        設定済みの Bolt App インスタンス
    """
```

#### SlackAppRunner

```
class SlackAppRunner:
    """Slack アプリケーションの実行管理"""

    def __init__(self, app: App, app_token: str) -> None:
        """
        Args:
            app: Bolt App インスタンス
            app_token: App-Level Token
        """
        ...

    def start(self) -> None:
        """Socket Mode でアプリを起動する（ブロッキング）"""
        ...

    def stop(self) -> None:
        """アプリを停止する"""
        ...
```

### `src/myao2/infrastructure/slack/messaging.py`

#### SlackMessagingService

```
class SlackMessagingService:
    """Slack用 MessagingService 実装"""

    def __init__(self, client: WebClient) -> None:
        """
        Args:
            client: Slack WebClient
        """
        ...

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None
    ) -> None:
        """メッセージを送信する

        Args:
            channel_id: 送信先チャンネルID
            text: メッセージ本文
            thread_ts: スレッドの親タイムスタンプ（スレッド返信時）

        Raises:
            SlackApiError: Slack API エラー
        """
        ...

    def get_bot_user_id(self) -> str:
        """ボット自身のユーザーIDを取得する"""
        ...
```

### `src/myao2/infrastructure/slack/event_adapter.py`

#### SlackEventAdapter

```
class SlackEventAdapter:
    """Slackイベントを Domain エンティティに変換"""

    def __init__(self, client: WebClient) -> None:
        """
        Args:
            client: ユーザー情報取得用 WebClient
        """
        ...

    def to_message(self, event: dict) -> Message:
        """Slackイベントを Message エンティティに変換

        Args:
            event: Slack の app_mention イベント

        Returns:
            Message エンティティ
        """
        ...

    def extract_mentions(self, text: str) -> list[str]:
        """テキストからメンションを抽出

        Args:
            text: メッセージ本文

        Returns:
            メンションされたユーザーIDのリスト
        """
        ...
```

### `src/myao2/presentation/slack_handlers.py`

#### register_handlers

```
def register_handlers(
    app: App,
    reply_use_case: ReplyToMentionUseCase,
    event_adapter: SlackEventAdapter
) -> None:
    """Slack イベントハンドラを登録する

    Args:
        app: Bolt App
        reply_use_case: メンション応答ユースケース
        event_adapter: イベント変換アダプター
    """
```

---

## Slackイベント形式

### app_mention イベント

```json
{
    "type": "app_mention",
    "user": "U123456",
    "text": "<@U_BOT_ID> こんにちは",
    "ts": "1234567890.123456",
    "channel": "C123456",
    "thread_ts": "1234567890.000000"  // スレッドの場合
}
```

### メンション形式

- `<@U123456>` - ユーザーメンション
- 正規表現: `<@([A-Z0-9]+)>`

---

## テストケース

### test_messaging.py

#### SlackMessagingService

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| チャンネルへの送信 | thread_ts=None | chat.postMessage が呼ばれる |
| スレッドへの送信 | thread_ts指定 | thread_ts付きで送信 |
| API エラー | SlackApiError発生 | 例外が伝播する |

### test_event_adapter.py

#### SlackEventAdapter

| テスト | 入力 | 期待結果 |
|--------|-----|---------|
| 基本的な変換 | app_mentionイベント | Messageエンティティ |
| スレッド内メッセージ | thread_ts付きイベント | thread_tsが設定される |
| メンション抽出 | `<@U123> <@U456>` | ["U123", "U456"] |
| メンションなし | `hello` | [] |

---

## 設計上の考慮事項

### エラーハンドリング

- Slack API エラーはログに記録
- 一時的なエラー（Rate Limit等）は再試行を検討（Phase 1では基本実装のみ）

### ユーザー情報のキャッシュ

- Phase 1 では都度 API を呼び出す
- Phase 2 以降でキャッシュを検討

### ボットの自己認識

- `auth.test` API でボット自身のユーザーIDを取得
- 起動時に一度だけ取得してキャッシュ

---

## 完了基準

- [x] Socket Mode でアプリが起動できる
- [x] app_mention イベントを受信できる
- [x] Slackイベントが Message エンティティに変換される
- [x] メッセージを送信できる
- [x] スレッドへの返信ができる
- [x] 全テストケースが通過する
