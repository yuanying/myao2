# extra01: DBベースの履歴取得

## 目的

メッセージ履歴取得を Slack API ベースから DB ベースに変更し、
API 呼び出しを最小化してパフォーマンスを向上させる。

---

## 背景

### 現状の問題点

1. **SlackConversationHistoryService** - 毎回 `conversations_history`, `conversations_replies` API を呼び出し
2. **SlackChannelMonitor** - 毎回 `conversations_history`, `conversations_replies` API を呼び出し
3. **SlackEventAdapter** - 毎回 `users_info` API を呼び出し（ユーザーキャッシュなし）

### API 呼び出し頻度の問題

- メンション応答時に毎回履歴を API から取得
- チャンネル監視時に毎回メッセージを API から取得
- ユーザー情報を毎回 API から取得（キャッシュなし）
- API レート制限のリスク

---

## 設計方針

- **DB のみを使用**: DB に保存済みのメッセージのみを使用し、過去履歴は Slack API から取得しない
- **ユーザー情報キャッシュ**: ユーザー情報を DB にキャッシュして `users_info` API 呼び出しを削減
- **チャンネル情報も DB 管理**: メッセージ受信時にチャンネル情報を DB に保存し、`get_channels()` は DB から取得
- **Slack API 依存最小化**: イベント受信とメッセージ送信のみ Slack API 使用

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/repositories/user_repository.py` | UserRepository Protocol |
| `src/myao2/domain/repositories/channel_repository.py` | ChannelRepository Protocol |
| `src/myao2/infrastructure/persistence/models.py` | UserModel, ChannelModel 追加 |
| `src/myao2/infrastructure/persistence/user_repository.py` | SQLiteUserRepository |
| `src/myao2/infrastructure/persistence/channel_repository.py` | SQLiteChannelRepository |
| `src/myao2/infrastructure/persistence/conversation_history.py` | DBConversationHistoryService |
| `src/myao2/infrastructure/persistence/channel_monitor.py` | DBChannelMonitor |
| `src/myao2/infrastructure/slack/event_adapter.py` | ユーザー/チャンネルキャッシュ追加 |
| `src/myao2/__main__.py` | DI 設定変更 |
| `tests/infrastructure/persistence/test_user_repository.py` | テスト |
| `tests/infrastructure/persistence/test_channel_repository.py` | テスト |
| `tests/infrastructure/persistence/test_conversation_history.py` | テスト |
| `tests/infrastructure/persistence/test_channel_monitor.py` | テスト |

---

## 依存関係

- タスク phase-2/02（MessageRepository）を拡張
- タスク phase-2/03（SlackConversationHistoryService）の DB 実装を追加
- タスク phase-3/02（SlackChannelMonitor）の DB 実装を追加

---

## インターフェース設計

### UserRepository Protocol

```python
class UserRepository(Protocol):
    """ユーザー情報リポジトリ"""

    async def save(self, user: User) -> None:
        """ユーザー情報を保存（upsert）"""
        ...

    async def find_by_id(self, user_id: str) -> User | None:
        """ID でユーザーを検索"""
        ...
```

### ChannelRepository Protocol

```python
class ChannelRepository(Protocol):
    """チャンネル情報リポジトリ"""

    async def save(self, channel: Channel) -> None:
        """チャンネル情報を保存（upsert）"""
        ...

    async def find_all(self) -> list[Channel]:
        """全チャンネルを取得"""
        ...

    async def find_by_id(self, channel_id: str) -> Channel | None:
        """ID でチャンネルを検索"""
        ...
```

### MessageRepository 拡張

```python
class MessageRepository(Protocol):
    # 既存メソッドに加えて:

    async def find_by_channel_since(
        self,
        channel_id: str,
        since: datetime,
        limit: int = 20,
    ) -> list[Message]:
        """指定時刻以降のチャンネルメッセージを取得（新しい順）"""
        ...
```

### DBConversationHistoryService

```python
class DBConversationHistoryService:
    """DB 実装の ConversationHistoryService"""

    def __init__(self, message_repository: MessageRepository) -> None:
        self._message_repository = message_repository

    async def fetch_thread_history(
        self, channel_id: str, thread_ts: str, limit: int = 20
    ) -> list[Message]:
        """スレッド履歴を DB から取得（古い順）"""
        messages = await self._message_repository.find_by_thread(
            channel_id, thread_ts, limit
        )
        return list(reversed(messages))

    async def fetch_channel_history(
        self, channel_id: str, limit: int = 20
    ) -> list[Message]:
        """チャンネル履歴を DB から取得（古い順）"""
        messages = await self._message_repository.find_by_channel(
            channel_id, limit
        )
        return list(reversed(messages))
```

### DBChannelMonitor

```python
class DBChannelMonitor:
    """DB 実装の ChannelMonitor"""

    def __init__(
        self,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        bot_user_id: str,
    ) -> None:
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._bot_user_id = bot_user_id

    async def get_channels(self) -> list[Channel]:
        """DB からチャンネル一覧を取得"""
        return await self._channel_repository.find_all()

    async def get_recent_messages(
        self,
        channel_id: str,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """DB から最近のメッセージを取得（新しい順）"""
        if since:
            return await self._message_repository.find_by_channel_since(
                channel_id, since, limit
            )
        return await self._message_repository.find_by_channel(
            channel_id, limit
        )

    async def get_unreplied_messages(
        self,
        channel_id: str,
        min_wait_seconds: int,
    ) -> list[Message]:
        """未応答メッセージを DB から取得"""
        # 実装は DB ベースの未応答判定ロジック
        ...
```

---

## データモデル

### UserModel

```python
class UserModel(SQLModel, table=True):
    """ユーザーテーブル"""
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(unique=True, index=True)
    name: str
    is_bot: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### ChannelModel

```python
class ChannelModel(SQLModel, table=True):
    """チャンネルテーブル"""
    __tablename__ = "channels"

    id: int | None = Field(default=None, primary_key=True)
    channel_id: str = Field(unique=True, index=True)
    name: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 処理フロー

### SlackEventAdapter の変更

1. イベント受信時にユーザー情報を取得
   - まず DB (UserRepository) を検索
   - 存在しなければ Slack API から取得して DB に保存
2. チャンネル情報を DB (ChannelRepository) に保存

### DBConversationHistoryService の処理

1. MessageRepository から履歴を取得
2. 新しい順から古い順に並べ替えて返却

### DBChannelMonitor の処理

1. get_channels: ChannelRepository から全チャンネル取得
2. get_recent_messages: MessageRepository から取得
3. get_unreplied_messages: DB ベースで未応答判定

---

## テストケース

### UserRepository

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| save | 新規ユーザー | ユーザーが保存される |
| save | 既存ユーザー | ユーザーが更新される |
| find_by_id | 存在するユーザー | ユーザーが返る |
| find_by_id | 存在しないユーザー | None が返る |

### ChannelRepository

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| save | 新規チャンネル | チャンネルが保存される |
| save | 既存チャンネル | チャンネルが更新される |
| find_all | チャンネルあり | チャンネルリストが返る |
| find_all | チャンネルなし | 空リストが返る |
| find_by_id | 存在するチャンネル | チャンネルが返る |
| find_by_id | 存在しないチャンネル | None が返る |

### DBConversationHistoryService

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| fetch_thread_history | スレッドあり | メッセージが古い順で返る |
| fetch_thread_history | スレッドなし | 空リストが返る |
| fetch_channel_history | メッセージあり | メッセージが古い順で返る |
| fetch_channel_history | メッセージなし | 空リストが返る |

### DBChannelMonitor

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| get_channels | チャンネルあり | チャンネルリストが返る |
| get_recent_messages | メッセージあり | メッセージが新しい順で返る |
| get_recent_messages | since 指定 | since 以降のメッセージのみ返る |
| get_unreplied_messages | 未応答あり | 未応答メッセージが返る |
| get_unreplied_messages | 応答済み | 空リストが返る |

---

## アーキテクチャ変更

```
Before:
SlackEventAdapter ──────────[users_info]──────────> Slack API
SlackConversationHistoryService ──[conversations_*]──> Slack API
SlackChannelMonitor ──────[conversations_*, users_info]──> Slack API

After:
SlackEventAdapter ─┬─[users_info]─> Slack API ─> UserRepository(cache)
                   ├─> ChannelRepository (save)
                   └─> MessageRepository (save)

DBConversationHistoryService ──> MessageRepository (read)

DBChannelMonitor ─┬─> MessageRepository (read)
                  └─> ChannelRepository (read)
```

---

## 設計上の考慮事項

### パフォーマンス

- ユーザー情報は DB にキャッシュされ、次回以降は API 呼び出し不要
- チャンネル情報はメッセージ受信時に DB に保存
- メッセージ履歴は DB から直接取得（API 呼び出しなし）

### データ整合性

- ボット起動前のメッセージは DB に存在しない（設計上許容）
- ユーザー名変更は次回のイベント受信時に更新される

### 後方互換性

- SlackConversationHistoryService と SlackChannelMonitor は削除せず残存可能
- 設定で実装を切り替えることも将来的に可能

---

## 完了基準

- [ ] UserRepository Protocol が定義されている
- [ ] SQLiteUserRepository が実装されている
- [ ] ChannelRepository Protocol が定義されている
- [ ] SQLiteChannelRepository が実装されている
- [ ] MessageRepository に find_by_channel_since が追加されている
- [ ] DBConversationHistoryService が実装されている
- [ ] DBChannelMonitor が実装されている
- [ ] SlackEventAdapter がユーザー/チャンネルキャッシュを使用している
- [ ] __main__.py が DB 実装を使用している
- [ ] 全テストケースが通過する
