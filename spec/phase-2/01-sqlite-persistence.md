# 01: SQLite永続化基盤

## 目的

SQLModel を使ったデータベース基盤を構築する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/repositories/__init__.py` | リポジトリモジュール |
| `src/myao2/domain/repositories/message_repository.py` | MessageRepository Protocol |
| `src/myao2/infrastructure/persistence/__init__.py` | 永続化モジュール |
| `src/myao2/infrastructure/persistence/models.py` | SQLModel テーブル定義 |
| `src/myao2/infrastructure/persistence/database.py` | DatabaseManager |
| `src/myao2/config/models.py` | MemoryConfig 追加（修正） |
| `tests/infrastructure/persistence/test_database.py` | DatabaseManager のテスト |

---

## テーブル設計

### messages テーブル

| カラム | 型 | 説明 | インデックス |
|--------|-----|------|-------------|
| id | INTEGER | 主キー（自動採番） | PK |
| message_id | VARCHAR | Slack の ts | Yes |
| channel_id | VARCHAR | チャンネル ID | Yes |
| user_id | VARCHAR | ユーザー ID | - |
| user_name | VARCHAR | ユーザー表示名 | - |
| user_is_bot | BOOLEAN | ボットかどうか | - |
| text | TEXT | メッセージ本文 | - |
| timestamp | DATETIME | メッセージ投稿時刻 | - |
| thread_ts | VARCHAR | スレッド親の ts（nullable） | Yes |
| mentions | TEXT | メンションユーザー ID（JSON配列） | - |
| created_at | DATETIME | レコード作成時刻 | - |

**複合ユニーク制約**: `(message_id, channel_id)`

---

## インターフェース設計

### `src/myao2/domain/repositories/message_repository.py`

#### MessageRepository Protocol

```
class MessageRepository(Protocol):
    """会話履歴リポジトリの抽象インターフェース

    メッセージの保存・取得を抽象化し、
    永続化層の実装詳細を隠蔽する。
    """

    def save(self, message: Message) -> None:
        """メッセージを保存する

        既存のメッセージ（同一の message_id, channel_id）が存在する場合は更新する。

        Args:
            message: 保存するメッセージ
        """
        ...

    def find_by_channel(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """チャンネルのメッセージ履歴を取得する

        スレッドに属さないメッセージのみを取得する。

        Args:
            channel_id: チャンネル ID
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    def find_by_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 20,
    ) -> list[Message]:
        """スレッドのメッセージ履歴を取得する

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親タイムスタンプ
            limit: 取得する最大件数

        Returns:
            メッセージリスト（新しい順）
        """
        ...

    def find_by_id(self, message_id: str, channel_id: str) -> Message | None:
        """ID でメッセージを検索する

        Args:
            message_id: メッセージ ID（Slack の ts）
            channel_id: チャンネル ID

        Returns:
            メッセージ（存在しない場合は None）
        """
        ...
```

### `src/myao2/infrastructure/persistence/models.py`

#### MessageModel

```
class MessageModel(SQLModel, table=True):
    """メッセージテーブル"""

    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(index=True)
    channel_id: str = Field(index=True)
    user_id: str
    user_name: str
    user_is_bot: bool = False
    text: str
    timestamp: datetime
    thread_ts: str | None = Field(default=None, index=True)
    mentions: str = ""  # JSON 形式: ["U123", "U456"]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("message_id", "channel_id", name="uq_message_channel"),
    )
```

### `src/myao2/infrastructure/persistence/database.py`

#### DatabaseManager

```
class DatabaseManager:
    """データベース管理

    SQLite データベースの初期化、エンジン生成、セッション管理を行う。
    """

    def __init__(self, database_path: str) -> None:
        """初期化

        Args:
            database_path: SQLite データベースファイルのパス
        """

    def get_engine(self) -> Engine:
        """SQLAlchemy エンジンを取得する

        Returns:
            Engine インスタンス
        """

    def create_tables(self) -> None:
        """テーブルを作成する

        既存のテーブルがある場合は何もしない。
        """

    def get_session(self) -> Session:
        """セッションを取得する

        Returns:
            Session インスタンス
        """
```

### `src/myao2/config/models.py`（修正）

#### MemoryConfig 追加

```
@dataclass
class MemoryConfig:
    """記憶設定"""

    database_path: str
    long_term_update_interval_seconds: int = 3600


@dataclass
class Config:
    """アプリケーション設定"""

    slack: SlackConfig
    llm: dict[str, LLMConfig]
    persona: PersonaConfig
    memory: MemoryConfig  # 追加
```

---

## 例外クラス

```
class PersistenceError(Exception):
    """永続化関連の基底例外"""


class DatabaseError(PersistenceError):
    """データベース操作エラー"""
```

---

## テストケース

### test_database.py

#### DatabaseManager

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| エンジン生成 | 有効なパス | Engine が生成される |
| エンジン生成（ディレクトリなし） | 親ディレクトリ未作成 | ディレクトリが作成される |
| テーブル作成 | 初回実行 | messages テーブルが作成される |
| テーブル作成（既存） | 2回目実行 | エラーなく完了 |
| セッション取得 | 正常なエンジン | Session が取得できる |
| インメモリDB | `:memory:` | 正常に動作 |

---

## 設計上の考慮事項

### SQLModel の選択理由

- SQLAlchemy のパワーと Pydantic の型安全性を兼ね備える
- FastAPI との親和性（将来の拡張を考慮）
- シンプルな API でボイラープレートを削減

### メンションの保存形式

- JSON 文字列として保存: `["U123", "U456"]`
- シンプルで十分な柔軟性
- 将来的に JSON カラム型に変更可能

### タイムスタンプの扱い

- すべて UTC で保存
- Python の `datetime` オブジェクトを使用
- Slack の ts（Unix timestamp 文字列）は `message_id` として保存

### ディレクトリ自動作成

- データベースファイルの親ディレクトリが存在しない場合は自動作成
- `./data/memory.db` のようなパスでも問題なく動作

---

## 完了基準

- [ ] MessageRepository Protocol が定義されている
- [ ] MessageModel が SQLModel で定義されている
- [ ] DatabaseManager が実装されている
- [ ] MemoryConfig が Config に追加されている
- [ ] データベースファイルの親ディレクトリが自動作成される
- [ ] 全テストケースが通過する
