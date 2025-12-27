# 02: メッセージリポジトリ実装

## 目的

MessageRepository の SQLite 実装を作成する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/persistence/message_repository.py` | SQLiteMessageRepository |
| `tests/infrastructure/persistence/test_message_repository.py` | リポジトリのテスト |

---

## 依存関係

- タスク 01（SQLite永続化基盤）の完了が前提

---

## インターフェース設計

### `src/myao2/infrastructure/persistence/message_repository.py`

#### SQLiteMessageRepository

```
class SQLiteMessageRepository:
    """SQLite 版 MessageRepository 実装

    メッセージの CRUD 操作を SQLite データベースに対して行う。
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """初期化

        Args:
            session_factory: セッション生成関数
        """

    def save(self, message: Message) -> None:
        """メッセージを保存する（upsert）

        既存のメッセージが存在する場合は更新する。

        Args:
            message: 保存するメッセージ
        """

    def find_by_channel(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルのメッセージを取得する

        スレッドに属さないメッセージ（thread_ts が None）のみを取得。
        新しい順（timestamp DESC）で返す。

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """

    def find_by_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドのメッセージを取得する

        指定したスレッドに属するメッセージを取得。
        新しい順（timestamp DESC）で返す。

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """

    def find_by_id(self, message_id: str, channel_id: str) -> Message | None:
        """ID でメッセージを検索する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID

        Returns:
            メッセージ（存在しない場合は None）
        """

    def _to_entity(self, model: MessageModel) -> Message:
        """モデルをエンティティに変換する

        Args:
            model: MessageModel インスタンス

        Returns:
            Message エンティティ
        """

    def _to_model(self, entity: Message) -> MessageModel:
        """エンティティをモデルに変換する

        Args:
            entity: Message エンティティ

        Returns:
            MessageModel インスタンス
        """
```

---

## 実装の詳細

### Upsert の実装

SQLite では `INSERT ... ON CONFLICT ... DO UPDATE` を使用:

```python
def save(self, message: Message) -> None:
    with self._session_factory() as session:
        # 既存レコードを検索
        existing = session.exec(
            select(MessageModel).where(
                MessageModel.message_id == message.id,
                MessageModel.channel_id == message.channel.id,
            )
        ).first()

        if existing:
            # 更新
            existing.text = message.text
            existing.mentions = json.dumps(message.mentions)
            # ... その他のフィールド
            session.add(existing)
        else:
            # 新規作成
            model = self._to_model(message)
            session.add(model)

        session.commit()
```

### エンティティ変換

```python
def _to_entity(self, model: MessageModel) -> Message:
    user = User(
        id=model.user_id,
        name=model.user_name,
        is_bot=model.user_is_bot,
    )
    channel = Channel(
        id=model.channel_id,
        name="",  # 名前は永続化しない
    )
    mentions = json.loads(model.mentions) if model.mentions else []

    return Message(
        id=model.message_id,
        channel=channel,
        user=user,
        text=model.text,
        timestamp=model.timestamp,
        thread_ts=model.thread_ts,
        mentions=mentions,
    )


def _to_model(self, entity: Message) -> MessageModel:
    return MessageModel(
        message_id=entity.id,
        channel_id=entity.channel.id,
        user_id=entity.user.id,
        user_name=entity.user.name,
        user_is_bot=entity.user.is_bot,
        text=entity.text,
        timestamp=entity.timestamp,
        thread_ts=entity.thread_ts,
        mentions=json.dumps(entity.mentions),
    )
```

---

## テストケース

### test_message_repository.py

#### save

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規保存 | 新規メッセージ | データベースに保存される |
| 更新 | 既存メッセージ（同一 ID） | データが更新される |
| 複数保存 | 異なるメッセージを連続保存 | すべて保存される |

#### find_by_channel

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数メッセージ | チャンネルに5件 | 新しい順で取得 |
| limit 指定 | 5件中3件取得 | 3件のみ返る |
| スレッド除外 | スレッド内メッセージあり | スレッドは含まれない |
| 空チャンネル | メッセージなし | 空リストが返る |
| 別チャンネル | 他チャンネルのメッセージ | 含まれない |

#### find_by_thread

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッドメッセージ | スレッドに3件 | 新しい順で取得 |
| limit 指定 | 5件中2件取得 | 2件のみ返る |
| 別スレッド | 他スレッドのメッセージ | 含まれない |
| 空スレッド | メッセージなし | 空リストが返る |

#### find_by_id

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 存在する ID | 有効な message_id | Message が返る |
| 存在しない ID | 無効な message_id | None が返る |
| 別チャンネル | 同じ ID だが別チャンネル | None が返る |

#### 変換テスト

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| モデル→エンティティ | MessageModel | 正しい Message |
| エンティティ→モデル | Message | 正しい MessageModel |
| メンションあり | mentions: ["U1", "U2"] | 正しく変換 |
| メンションなし | mentions: [] | 空リストで変換 |

---

## テストフィクスチャ

### インメモリデータベース

```python
@pytest.fixture
def session_factory():
    """インメモリ SQLite のセッションファクトリ"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    def factory():
        return Session(engine)

    return factory


@pytest.fixture
def repository(session_factory):
    """テスト用リポジトリ"""
    return SQLiteMessageRepository(session_factory)
```

### テストデータファクトリ

```python
def create_test_message(
    id: str = "1234567890.123456",
    channel_id: str = "C123456",
    user_id: str = "U123456",
    user_name: str = "testuser",
    text: str = "Hello, world!",
    thread_ts: str | None = None,
    mentions: list[str] | None = None,
) -> Message:
    """テスト用 Message を生成"""
    return Message(
        id=id,
        channel=Channel(id=channel_id, name="general"),
        user=User(id=user_id, name=user_name, is_bot=False),
        text=text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=thread_ts,
        mentions=mentions or [],
    )
```

---

## 設計上の考慮事項

### チャンネル名の扱い

- チャンネル名は永続化しない
- 取得時は空文字列を設定
- チャンネル名が必要な場合は Slack API から再取得

### タイムゾーン

- すべて UTC で保存・取得
- 表示時にローカルタイムゾーンに変換（Presentation層の責務）

### トランザクション

- 各操作は独立したトランザクション
- セッションファクトリパターンで柔軟に管理

---

## 完了基準

- [ ] SQLiteMessageRepository が実装されている
- [ ] save で新規保存・更新が正しく動作する
- [ ] find_by_channel でスレッド外メッセージのみ取得できる
- [ ] find_by_thread で指定スレッドのメッセージを取得できる
- [ ] find_by_id で単一メッセージを取得できる
- [ ] エンティティとモデルの相互変換ができる
- [ ] 全テストケースが通過する
