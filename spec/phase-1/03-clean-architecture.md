# 03: クリーンアーキテクチャ基本構造

## 目的

各層の基本インターフェースとエンティティを定義する。

---

## レイヤー構成

```
┌─────────────────────────────────────────┐
│           Presentation層                 │
│         (Slackイベントハンドラ)           │
└─────────────────┬───────────────────────┘
                  │ 依存
┌─────────────────▼───────────────────────┐
│           Application層                  │
│            (ユースケース)                 │
└─────────────────┬───────────────────────┘
                  │ 依存
┌─────────────────▼───────────────────────┐
│            Domain層                      │
│     (エンティティ, Protocol)              │
└─────────────────────────────────────────┘
                  ▲
                  │ 実装
┌─────────────────┴───────────────────────┐
│         Infrastructure層                 │
│       (Slack, LLM, 永続化)               │
└─────────────────────────────────────────┘
```

**依存ルール**:
- Domain層は他の層に依存しない
- Application層はDomain層にのみ依存
- Infrastructure層はDomain層のProtocolを実装
- Presentation層はApplication層に依存

---

## 実装するファイル

### Domain層

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/message.py` | Message エンティティ |
| `src/myao2/domain/entities/user.py` | User エンティティ |
| `src/myao2/domain/entities/channel.py` | Channel エンティティ |
| `src/myao2/domain/services/protocols.py` | サービスインターフェース |

### Application層

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/use_cases/reply_to_mention.py` | メンション応答ユースケース |

### テスト

| ファイル | 説明 |
|---------|------|
| `tests/domain/entities/test_message.py` | Message のテスト |
| `tests/application/use_cases/test_reply_to_mention.py` | ユースケースのテスト |

---

## インターフェース設計

### Domain層 - エンティティ

#### User

```
@dataclass(frozen=True)
class User:
    """ユーザーエンティティ（プラットフォーム非依存）"""
    id: str           # プラットフォーム固有のID
    name: str         # 表示名
    is_bot: bool = False
```

#### Channel

```
@dataclass(frozen=True)
class Channel:
    """チャンネルエンティティ"""
    id: str
    name: str
```

#### Message

```
@dataclass(frozen=True)
class Message:
    """メッセージエンティティ"""
    id: str
    channel: Channel
    user: User
    text: str
    timestamp: datetime
    thread_ts: str | None = None  # スレッドの親メッセージ
    mentions: list[str] = field(default_factory=list)  # メンションされたユーザーID

    def is_in_thread(self) -> bool:
        """スレッド内のメッセージかどうか"""
        ...

    def mentions_user(self, user_id: str) -> bool:
        """指定ユーザーがメンションされているか"""
        ...
```

### Domain層 - Protocol

#### MessagingService

```
class MessagingService(Protocol):
    """メッセージング抽象（プラットフォーム非依存）"""

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None
    ) -> None:
        """メッセージを送信する"""
        ...
```

#### ResponseGenerator

```
class ResponseGenerator(Protocol):
    """応答生成抽象"""

    def generate(
        self,
        user_message: str,
        system_prompt: str
    ) -> str:
        """応答を生成する"""
        ...
```

### Application層 - ユースケース

#### ReplyToMentionUseCase

```
class ReplyToMentionUseCase:
    """メンションへの応答ユースケース"""

    def __init__(
        self,
        messaging_service: MessagingService,
        response_generator: ResponseGenerator,
        persona: PersonaConfig,
        bot_user_id: str
    ) -> None:
        """
        Args:
            messaging_service: メッセージ送信サービス
            response_generator: 応答生成サービス
            persona: ペルソナ設定
            bot_user_id: ボット自身のユーザーID
        """
        ...

    def execute(self, message: Message) -> None:
        """メンションに応答する

        Args:
            message: 受信したメッセージ

        Note:
            - ボット自身へのメンションが含まれている場合のみ応答
            - スレッドがある場合はスレッドに返信
        """
        ...
```

---

## テストケース

### test_message.py

#### Messageエンティティ

| テスト | 入力 | 期待結果 |
|--------|-----|---------|
| 基本的な生成 | 必須フィールド | Messageオブジェクトが生成される |
| is_in_thread（スレッド内） | thread_ts="xxx" | True |
| is_in_thread（チャンネル直下） | thread_ts=None | False |
| mentions_user（メンションあり） | mentions=["U123"], user_id="U123" | True |
| mentions_user（メンションなし） | mentions=["U123"], user_id="U456" | False |

### test_reply_to_mention.py

#### ReplyToMentionUseCase

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| メンションあり・チャンネル | ボットがメンションされた | チャンネルにメッセージ送信 |
| メンションあり・スレッド | スレッド内でメンション | スレッドに返信 |
| メンションなし | 他ユーザーのみメンション | 何もしない |
| ボット自身のメッセージ | ボットが送信者 | 何もしない |

---

## 設計上の考慮事項

### プラットフォーム非依存

- Domainエンティティは Slack 固有の概念を持たない
- `Message.id` はプラットフォーム固有のIDを受け入れる
- 将来 Discord 等に対応する際も Domain層は変更不要

### イミュータブル設計

- エンティティは `frozen=True` で不変
- 状態変更が必要な場合は新しいインスタンスを生成

### Protocol の使用

- Python 3.8+ の `typing.Protocol` を使用
- 構造的部分型によるダックタイピング
- テスト時のモック作成が容易

---

## 完了基準

- [ ] Message, User, Channel エンティティが実装されている
- [ ] MessagingService, ResponseGenerator Protocol が定義されている
- [ ] ReplyToMentionUseCase が実装されている
- [ ] エンティティの各メソッドがテストされている
- [ ] ユースケースがモックを使ってテストされている
