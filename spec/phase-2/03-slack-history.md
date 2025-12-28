# 03: Slack履歴取得

## 目的

Slack API を使ってチャンネル/スレッドの履歴を取得する機能を実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/services/protocols.py` | ConversationHistoryService Protocol 追加（修正） |
| `src/myao2/infrastructure/slack/history.py` | SlackConversationHistoryService |
| `tests/infrastructure/slack/test_history.py` | 履歴取得のテスト |

---

## Slack API

### 使用する API

| API | 用途 |
|-----|------|
| `conversations.history` | チャンネルのメッセージ履歴を取得 |
| `conversations.replies` | スレッドのメッセージ履歴を取得 |
| `users.info` | ユーザー情報を取得（既存の event_adapter と共有） |

### 必要なスコープ

- `channels:history` - パブリックチャンネルの履歴
- `groups:history` - プライベートチャンネルの履歴（必要に応じて）
- `users:read` - ユーザー情報（Phase 1 で設定済み）

---

## インターフェース設計

### `src/myao2/domain/services/protocols.py`（修正）

#### ConversationHistoryService Protocol 追加

```
class ConversationHistoryService(Protocol):
    """会話履歴取得の抽象インターフェース

    プラットフォーム非依存の会話履歴取得を定義する。
    """

    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドの履歴を取得する

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """
        ...

    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルの履歴を取得する

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """
        ...
```

### `src/myao2/infrastructure/slack/history.py`

#### SlackConversationHistoryService

```
class SlackConversationHistoryService:
    """Slack 版 ConversationHistoryService 実装

    Slack API を使って会話履歴を取得する。
    """

    def __init__(self, client: WebClient) -> None:
        """初期化

        Args:
            client: Slack WebClient
        """

    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドの履歴を取得する

        conversations.replies API を使用。
        親メッセージを含む全メッセージを取得。

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """

    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルの履歴を取得する

        conversations.history API を使用。

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（古い順）
        """

    def _to_message(
        self,
        msg: dict,
        channel_id: str,
    ) -> Message:
        """Slack API レスポンスを Message エンティティに変換

        Args:
            msg: Slack API のメッセージオブジェクト
            channel_id: チャンネル ID

        Returns:
            Message エンティティ
        """

    def _get_user_info(self, user_id: str) -> User:
        """ユーザー情報を取得する

        Args:
            user_id: ユーザー ID

        Returns:
            User エンティティ
        """

    def _extract_mentions(self, text: str) -> list[str]:
        """テキストからメンションを抽出する

        Args:
            text: メッセージテキスト

        Returns:
            メンションされたユーザー ID のリスト
        """
```

---

## 実装の詳細

### conversations.replies の呼び出し

```python
def fetch_thread_history(
    self,
    channel_id: str,
    thread_ts: str,
    limit: int = 20,
) -> list[Message]:
    response = self._client.conversations_replies(
        channel=channel_id,
        ts=thread_ts,
        limit=limit,
    )

    messages = []
    for msg in response.get("messages", []):
        # bot_message や message_changed などのサブタイプは除外
        if msg.get("subtype") in ["bot_message", "message_changed", "message_deleted"]:
            continue
        messages.append(self._to_message(msg, channel_id))

    return messages  # すでに古い順
```

### conversations.history の呼び出し

```python
def fetch_channel_history(
    self,
    channel_id: str,
    limit: int = 20,
) -> list[Message]:
    response = self._client.conversations_history(
        channel=channel_id,
        limit=limit,
    )

    messages = []
    for msg in response.get("messages", []):
        if msg.get("subtype") in ["bot_message", "message_changed", "message_deleted"]:
            continue
        messages.append(self._to_message(msg, channel_id))

    # API は新しい順で返すので、古い順に並び替え
    return list(reversed(messages))
```

### メッセージ変換

```python
def _to_message(self, msg: dict, channel_id: str) -> Message:
    user_id = msg.get("user", "")
    user = self._get_user_info(user_id) if user_id else User(
        id="",
        name="Unknown",
        is_bot=True,
    )

    # タイムスタンプ変換（Slack の ts は Unix timestamp 文字列）
    ts = float(msg["ts"])
    timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)

    return Message(
        id=msg["ts"],
        channel=Channel(id=channel_id, name=""),
        user=user,
        text=msg.get("text", ""),
        timestamp=timestamp,
        thread_ts=msg.get("thread_ts"),
        mentions=self._extract_mentions(msg.get("text", "")),
    )
```

---

## テストケース

### test_history.py

#### fetch_thread_history

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常取得 | スレッドに3件 | 3件のメッセージ（古い順） |
| 空スレッド | メッセージなし | 空リスト |
| limit 指定 | 5件中2件 | 2件のみ返る |
| サブタイプ除外 | bot_message 含む | 通常メッセージのみ |

#### fetch_channel_history

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常取得 | チャンネルに5件 | 5件のメッセージ（古い順） |
| 空チャンネル | メッセージなし | 空リスト |
| limit 指定 | 10件中3件 | 3件のみ返る |
| サブタイプ除外 | message_changed 含む | 通常メッセージのみ |

#### _to_message

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 通常メッセージ | 標準的なメッセージ | 正しい Message |
| スレッドメッセージ | thread_ts あり | thread_ts が設定される |
| メンションあり | `<@U123>` 含む | mentions に U123 |
| メンション複数 | `<@U1> <@U2>` | mentions に U1, U2 |

#### エラーハンドリング

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| API エラー | SlackApiError | 例外がそのまま伝播 |
| チャンネル不在 | channel_not_found | SlackApiError |

---

## テストフィクスチャ

### モック WebClient

```python
@pytest.fixture
def mock_client():
    """モック Slack WebClient"""
    client = Mock(spec=WebClient)
    return client


@pytest.fixture
def history_service(mock_client):
    """テスト用履歴サービス"""
    return SlackConversationHistoryService(mock_client)
```

### Slack API レスポンスのモック

```python
def mock_conversations_replies_response(messages: list[dict]) -> dict:
    """conversations.replies のモックレスポンス"""
    return {
        "ok": True,
        "messages": messages,
    }


def mock_conversations_history_response(messages: list[dict]) -> dict:
    """conversations.history のモックレスポンス"""
    return {
        "ok": True,
        "messages": messages,
    }


def create_slack_message(
    ts: str = "1234567890.123456",
    user: str = "U123456",
    text: str = "Hello",
    thread_ts: str | None = None,
) -> dict:
    """Slack API 形式のメッセージを生成"""
    msg = {
        "type": "message",
        "ts": ts,
        "user": user,
        "text": text,
    }
    if thread_ts:
        msg["thread_ts"] = thread_ts
    return msg
```

---

## 設計上の考慮事項

### 順序の統一

- すべての履歴取得メソッドは **古い順** で返す
- LLM に渡す会話履歴は時系列順が自然
- Slack API は新しい順で返すため、チャンネル履歴は reversed() する

### サブタイプの除外

以下のサブタイプは除外する：
- `bot_message` - ボットからのメッセージ（別途処理）
- `message_changed` - 編集通知
- `message_deleted` - 削除通知
- `channel_join` - 参加通知
- `channel_leave` - 退出通知

### ユーザー情報の取得

- 既存の SlackEventAdapter と同様のロジックを使用
- 将来的にはキャッシュを導入予定（Phase 2 ではシンプルさ優先）

### エラーハンドリング

- Slack API エラーはそのまま伝播
- 呼び出し元（ユースケース）で適切に処理

---

## 完了基準

- [x] ConversationHistoryService Protocol が定義されている
- [x] SlackConversationHistoryService が実装されている
- [x] conversations.replies でスレッド履歴が取得できる
- [x] conversations.history でチャンネル履歴が取得できる
- [x] サブタイプ（bot_message 等）が除外される
- [x] 履歴は古い順で返される
- [x] 全テストケースが通過する
