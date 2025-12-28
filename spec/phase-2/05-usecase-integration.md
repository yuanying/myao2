# 05: ユースケース統合

## 目的

全コンポーネントを統合し、コンテキスト管理機能を完成させる。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/use_cases/reply_to_mention.py` | ユースケース修正 |
| `src/myao2/__main__.py` | エントリポイント修正 |
| `tests/application/use_cases/test_reply_to_mention.py` | テスト追加 |

---

## 依存関係

- タスク 02（メッセージリポジトリ実装）
- タスク 03（Slack履歴取得）
- タスク 03a（Context ドメインモデル）
- タスク 04（コンテキスト付き応答生成）

---

## インターフェース設計

### `src/myao2/application/use_cases/reply_to_mention.py`（修正）

#### ReplyToMentionUseCase

```
class ReplyToMentionUseCase:
    """メンションへの応答ユースケース

    ボットがメンションされた際に、会話履歴を考慮した応答を生成する。
    """

    def __init__(
        self,
        messaging_service: MessagingService,
        response_generator: ResponseGenerator,
        message_repository: MessageRepository,  # 追加
        conversation_history_service: ConversationHistoryService,  # 追加
        persona: PersonaConfig,
        bot_user_id: str,
    ) -> None:
        """初期化

        Args:
            messaging_service: メッセージ送信サービス
            response_generator: 応答生成サービス
            message_repository: メッセージリポジトリ
            conversation_history_service: 会話履歴取得サービス
            persona: ペルソナ設定
            bot_user_id: ボットのユーザー ID
        """

    def execute(self, message: Message) -> None:
        """ユースケースを実行する

        処理フロー:
        1. ボット自身のメッセージは無視
        2. メンションがなければ無視
        3. 受信メッセージを保存
        4. 会話履歴を取得（スレッド or チャンネル）
        5. Context を構築
        6. コンテキスト付きで応答を生成
        7. 応答を送信
        8. 応答メッセージを保存

        Args:
            message: 受信したメッセージ
        """

    def _get_conversation_history(self, message: Message) -> list[Message]:
        """会話履歴を取得する

        スレッド内の場合はスレッド履歴を、
        チャンネル直下の場合はチャンネル履歴を取得する。

        Args:
            message: 受信したメッセージ

        Returns:
            会話履歴（古い順）
        """

    def _build_context(self, conversation_history: list[Message]) -> Context:
        """Context を構築する

        Args:
            conversation_history: 会話履歴

        Returns:
            Context インスタンス
        """

    def _create_bot_message(
        self,
        response_text: str,
        original_message: Message,
    ) -> Message:
        """ボットの応答メッセージを作成する

        Args:
            response_text: 応答テキスト
            original_message: 元のメッセージ

        Returns:
            ボットの応答 Message
        """
```

---

## 実装の詳細

### execute メソッド

```python
def execute(self, message: Message) -> None:
    # 1. ボット自身のメッセージは無視
    if message.user.id == self._bot_user_id:
        return

    # 2. メンションがなければ無視
    if not message.mentions_user(self._bot_user_id):
        return

    # 3. 受信メッセージを保存
    self._message_repository.save(message)

    # 4. 会話履歴を取得
    conversation_history = self._get_conversation_history(message)

    # 5. Context を構築
    context = self._build_context(conversation_history)

    # 6. コンテキスト付きで応答を生成
    response_text = self._response_generator.generate(
        user_message=message,
        context=context,
    )

    # 7. 応答を送信
    self._messaging_service.send_message(
        channel_id=message.channel.id,
        text=response_text,
        thread_ts=message.thread_ts,
    )

    # 8. 応答メッセージを保存
    bot_message = self._create_bot_message(response_text, message)
    self._message_repository.save(bot_message)
```

### _get_conversation_history メソッド

```python
def _get_conversation_history(self, message: Message) -> list[Message]:
    if message.is_in_thread():
        # スレッド内の場合はスレッド履歴を取得
        return self._conversation_history_service.fetch_thread_history(
            channel_id=message.channel.id,
            thread_ts=message.thread_ts,
            limit=20,
        )
    else:
        # チャンネル直下の場合はチャンネル履歴を取得
        return self._conversation_history_service.fetch_channel_history(
            channel_id=message.channel.id,
            limit=20,
        )
```

### _build_context メソッド

```python
def _build_context(self, conversation_history: list[Message]) -> Context:
    return Context(
        persona=self._persona,
        conversation_history=conversation_history,
    )
```

### _create_bot_message メソッド

```python
def _create_bot_message(
    self,
    response_text: str,
    original_message: Message,
) -> Message:
    return Message(
        id=str(datetime.now(timezone.utc).timestamp()),  # 仮の ID
        channel=original_message.channel,
        user=User(
            id=self._bot_user_id,
            name=self._persona.name,
            is_bot=True,
        ),
        text=response_text,
        timestamp=datetime.now(timezone.utc),
        thread_ts=original_message.thread_ts,
        mentions=[],
    )
```

---

## エントリポイント修正

### `src/myao2/__main__.py`

```python
def main() -> None:
    # 設定読み込み
    config = load_config("config.yaml")

    # Slack アプリ初期化
    app = App(
        token=config.slack.bot_token,
        # ...
    )
    bot_user_id = app.client.auth_test()["user_id"]

    # データベース初期化
    db_manager = DatabaseManager(config.memory.database_path)
    db_manager.create_tables()

    # 依存性の構築
    messaging_service = SlackMessagingService(app.client)
    event_adapter = SlackEventAdapter(app.client)
    llm_client = LLMClient(config.llm["default"])
    response_generator = LiteLLMResponseGenerator(llm_client)
    message_repository = SQLiteMessageRepository(db_manager.get_session)
    conversation_history_service = SlackConversationHistoryService(app.client)

    # ユースケース初期化
    reply_use_case = ReplyToMentionUseCase(
        messaging_service=messaging_service,
        response_generator=response_generator,
        message_repository=message_repository,
        conversation_history_service=conversation_history_service,
        persona=config.persona,
        bot_user_id=bot_user_id,
    )

    # ハンドラ登録
    register_handlers(app, reply_use_case, event_adapter, bot_user_id)

    # 起動
    runner = SlackAppRunner(app, config.slack.app_token)
    runner.start()
```

---

## テストケース

### test_reply_to_mention.py（追加）

#### メッセージ保存

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 受信メッセージ保存 | メンション受信 | repository.save が呼ばれる |
| 応答メッセージ保存 | 応答送信後 | 2回目の save が呼ばれる |

#### 会話履歴取得

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スレッド内 | thread_ts あり | fetch_thread_history が呼ばれる |
| チャンネル直下 | thread_ts なし | fetch_channel_history が呼ばれる |

#### Context 構築

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| Context 生成 | 履歴3件 | Context が正しく構築される |
| Context のペルソナ | persona 設定 | persona が正しく設定される |

#### コンテキスト付き生成

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| generate 呼び出し | Context 付き | generate(message, context) が呼ばれる |
| 履歴空 | 履歴なし | 空の conversation_history で動作 |

#### 既存テストの維持

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| メンション時の応答 | メンションあり | メッセージが送信される |
| スレッド返信 | スレッド内メンション | スレッドに返信 |
| メンションなし | メンションなし | 何もしない |
| ボット自身 | ボットのメッセージ | 何もしない |

---

## テストフィクスチャ

### モックオブジェクト

```python
@pytest.fixture
def mock_repository():
    """モック MessageRepository"""
    return Mock(spec=["save", "find_by_channel", "find_by_thread", "find_by_id"])


@pytest.fixture
def mock_history_service():
    """モック ConversationHistoryService"""
    service = Mock(spec=["fetch_thread_history", "fetch_channel_history"])
    service.fetch_thread_history.return_value = []
    service.fetch_channel_history.return_value = []
    return service


@pytest.fixture
def use_case(
    mock_messaging_service,
    mock_response_generator,
    mock_repository,
    mock_history_service,
    persona_config,
):
    """テスト用ユースケース"""
    return ReplyToMentionUseCase(
        messaging_service=mock_messaging_service,
        response_generator=mock_response_generator,
        message_repository=mock_repository,
        conversation_history_service=mock_history_service,
        persona=persona_config,
        bot_user_id="B123456",
    )
```

---

## シーケンス図

### メンション応答フロー

```
User                Slack           UseCase         Repository      HistoryService    LLM
 |                   |                |                |                |              |
 |-- @myao hello --->|                |                |                |              |
 |                   |-- message ---->|                |                |              |
 |                   |                |-- save() ----->|                |              |
 |                   |                |<-- ok ---------|                |              |
 |                   |                |                |                |              |
 |                   |                |-- fetch_*() ------------------>|              |
 |                   |                |<-- history --------------------|              |
 |                   |                |                |                |              |
 |                   |                |-- build_context()              |              |
 |                   |                |<-- Context                     |              |
 |                   |                |                |                |              |
 |                   |                |-- generate(message, context) ------------>|
 |                   |                |<-- response --------------------------------|
 |                   |                |                |                |              |
 |                   |<-- send() -----|                |                |              |
 |<-- response ------|                |                |                |              |
 |                   |                |                |                |              |
 |                   |                |-- save(bot_msg)|                |              |
 |                   |                |<-- ok ---------|                |              |
```

---

## 設計上の考慮事項

### 応答メッセージの ID

- Slack API からは送信後に ts（メッセージ ID）が返る
- Phase 2 では仮の ID（現在時刻）を使用
- 将来的には send_message の戻り値から取得する形に改善可能

### エラーハンドリング

- LLM エラー: ログに記録し、処理を中断
- Slack API エラー: ログに記録し、処理を中断
- DB エラー: ログに記録し、応答は試みる

### 履歴の件数

- デフォルト 20 件
- LLM のコンテキスト長を考慮して調整可能
- 将来的には設定ファイルで指定可能に

### 既存テストへの影響

- 新しい依存（repository, history_service）はモックで注入
- 既存のテストシナリオは変更なしで通過すべき

### Context の活用

- Context はユースケース内で構築
- ResponseGenerator は Context を受け取るだけ
- 将来の拡張（長期・短期記憶）に対応しやすい設計

---

## 完了基準

- [x] ReplyToMentionUseCase が MessageRepository を使用している
- [x] ReplyToMentionUseCase が ConversationHistoryService を使用している
- [x] Context が正しく構築される
- [x] 受信メッセージがリポジトリに保存される
- [x] 応答メッセージがリポジトリに保存される
- [x] スレッド内ではスレッド履歴が使用される
- [x] チャンネル直下ではチャンネル履歴が使用される
- [x] Context 付きで応答が生成される
- [x] エントリポイントで依存性が正しく注入されている
- [x] 既存のテストが引き続き通過する
- [x] 新規テストケースが通過する
