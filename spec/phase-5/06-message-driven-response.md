# 06: メッセージ駆動型応答アーキテクチャ

## 概要

現在の定期実行による自律応答チェック（AUTONOMOUS_CHECK）を廃止し、全てのSlackメッセージイベントを起点とするイベント駆動アーキテクチャに移行する。メッセージ受信時にjudgmentを実行し、LLMが決定した遅延時間に基づいてスケジュールされた応答を行う。

## 目的

- **リアルタイム性向上**: メッセージ受信時に即座にイベントを発行し、最適なタイミングで応答
- **LLM呼び出し最適化**: 重複排除により不要なjudgment呼び出しを削減
- **柔軟な応答タイミング**: LLMが会話の文脈に基づいて遅延秒数を決定
- **アーキテクチャ簡素化**: AUTONOMOUS_CHECK関連コンポーネントを廃止し、イベント駆動に統一

---

## アーキテクチャ変更

### 現在のアーキテクチャ

```
Slack Event → slack_handlers.py → [メンションのみ] → MESSAGE Event → MessageEventHandler → 応答生成
                                                                                          ↘ DB保存

定期実行 (1分間隔) → EventScheduler → AUTONOMOUS_CHECK Event → AutonomousCheckEventHandler
                                                                      ↓
                                                              AutonomousResponseUseCase
                                                                      ↓
                                                    全チャンネルの未応答スレッドを検出
                                                                      ↓
                                                    judgment実行 → 応答生成 → 送信
```

### 新アーキテクチャ

#### メンションの場合

```
Slackメッセージ受信 → DB保存 → MESSAGEイベント即座enqueue → 応答生成・送信
```

- judgmentスキップ
- 常に即座に応答

#### 非メンションの場合

```
Slackメッセージ受信 → DB保存 → JUDGMENTイベントを遅延enqueue (min_wait_seconds + jitter)
                                    ↓
                              [同一スレッドに新メッセージ] → キャンセル → 最初から再スケジュール
                                    ↓
                              JUDGMENTハンドラでjudgment実行
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
            should_respond=false              should_respond=true
                    ↓                               ↓
                (何もしない)                 MESSAGEイベントを遅延enqueue (delay_seconds)
                                                    ↓
                                          [同一スレッドに新メッセージ] → キャンセル → 最初から再スケジュール
                                                    ↓
                                          MESSAGEハンドラで応答生成・送信
```

---

## ドメイン層の変更

### JudgmentResult エンティティの拡張

**ファイル**: `src/myao2/domain/entities/judgment_result.py`

```python
@dataclass(frozen=True)
class JudgmentResult:
    """Response judgment result.

    Attributes:
        should_respond: Whether the bot should respond.
        reason: The reason for the judgment (for debugging/logging).
        confidence: Confidence level (0.0 - 1.0, optional).
        delay_seconds: Response delay in seconds.
        metrics: LLM invocation metrics (optional).
    """

    should_respond: bool
    reason: str
    confidence: float = 1.0
    delay_seconds: int | None = None  # 新規追加
    metrics: LLMMetrics | None = None
```

#### delay_seconds の意味

| should_respond | delay_seconds | 動作 |
|---------------|---------------|------|
| `true` | `0` | 即座に応答 |
| `true` | `>0` | N秒後に応答 |
| `true` | `None` | 即座に応答（デフォルト） |
| `false` | (無視) | 応答しない |

### EventType の変更

**ファイル**: `src/myao2/domain/entities/event.py`

```python
class EventType(Enum):
    """Event types for the event-driven system."""

    MESSAGE = "message"
    JUDGMENT = "judgment"  # 新規追加
    SUMMARY = "summary"
    # AUTONOMOUS_CHECK = "autonomous_check"  # 削除
    CHANNEL_SYNC = "channel_sync"
```

### Event エンティティの identity_key 更新

```python
def get_identity_key(self) -> str:
    """重複判定用の識別キーを返す"""
    if self.type == EventType.MESSAGE:
        channel_id = self.payload.get("channel_id", "")
        thread_ts = self.payload.get("thread_ts") or ""
        return f"message:{channel_id}:{thread_ts}"
    elif self.type == EventType.JUDGMENT:
        channel_id = self.payload.get("channel_id", "")
        thread_ts = self.payload.get("thread_ts") or ""
        return f"judgment:{channel_id}:{thread_ts}"
    # ...
```

---

## インフラ層の変更

### JudgmentOutput モデルの更新

**ファイル**: `src/myao2/infrastructure/llm/strands/models.py`

```python
class JudgmentOutput(BaseModel):
    """Output model for response judgment."""

    should_respond: bool = Field(description="Whether to respond")
    reason: str = Field(description="Reason for the judgment")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level (0.0-1.0)",
    )
    delay_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Response delay in seconds (0 for immediate, None or positive for delayed)",
    )
```

### StrandsResponseJudgment の更新

**ファイル**: `src/myao2/infrastructure/llm/strands/response_judgment.py`

`judge()` メソッドで `delay_seconds` を `JudgmentResult` に含める:

```python
return JudgmentResult(
    should_respond=output.should_respond,
    reason=output.reason,
    confidence=output.confidence,
    delay_seconds=output.delay_seconds,  # 新規追加
    metrics=metrics,
)
```

### judgment_system.j2 テンプレートの更新

**ファイル**: `src/myao2/infrastructure/llm/templates/judgment_system.j2`

```jinja2
{{ persona.system_prompt }}
{% if agent_system_prompt %}

{{ agent_system_prompt }}
{% endif %}

あなたは会話への参加判断を行います。

## 判断基準

1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）
6. 会話が終了しているか（挨拶やお礼で終わっている場合は応答不要）

## 応答しない条件

- 明らかな独り言
- 活発な会話に無理に割り込む場合
- 既に会話が終了している場合（「ありがとう」「了解」等の締めくくり）
- 自分（{{ persona.name }}）が最後に発言している場合

## 出力フィールド

あなたの判断は以下の4つのフィールドで構成されます。

### should_respond (boolean)
- `true`: 応答すべき
- `false`: 応答すべきでない

### reason (string)
判断の理由を簡潔に説明してください。以下を含めること：
- 判断の根拠となった会話の状況
- 応答する/しない理由
- 例: 「ユーザーが質問しており、まだ誰も回答していないため」
- 例: 「活発な会話が続いており、割り込む必要がないため」

### confidence (float: 0.0-1.0)
判断の確信度を数値で示してください：
- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）

### delay_seconds (integer | null)
応答するまでの遅延秒数を指定してください（should_respond=trueの場合のみ有効）：

**遅延ガイドライン**:
- `0`: 即座の応答が必要な場合（困っている人がいる、緊急性がある）
- `30-120`: 会話を見守りたい場合（他の人が反応するかもしれない）
- `180-600`: 会話の流れを妨げたくない場合、様子を見る場合
- `null` または省略: 即座に応答（should_respond=falseの場合は無視される）

**考慮事項**:
- 会話が活発な場合は遅延を長めに
- 困っている人がいる場合は短めに
- メッセージから経過時間が長い場合は短めに（既に待たせている）
```

### EventScheduler の変更

**ファイル**: `src/myao2/infrastructure/events/scheduler.py`

AUTONOMOUS_CHECK関連を削除し、SUMMARYとCHANNEL_SYNCのみを残す。

---

## プレゼンテーション層の変更

### slack_handlers.py の変更

**ファイル**: `src/myao2/presentation/slack_handlers.py`

**変更点**:
1. メンション → MESSAGEイベント即座enqueue
2. 非メンション → JUDGMENTイベント遅延enqueue

```python
def register_handlers(
    app: AsyncApp,
    event_queue: EventQueue,
    event_adapter: SlackEventAdapter,
    bot_user_id: str,
    message_repository: MessageRepository,
    channel_repository: ChannelRepository,
    config: Config,  # 新規追加（min_wait_seconds, jitter_ratio用）
) -> None:
    """Register Slack event handlers."""

    @app.event("message")
    async def handle_message(event: dict) -> None:
        # ... 既存のDB保存処理 ...

        # ボット自身のメッセージはDB保存のみ
        if message.user.id == bot_user_id:
            logger.debug("Skipping bot's own message")
            return

        # メンション判定
        text = event.get("text", "")
        is_mention = f"<@{bot_user_id}>" in text

        if is_mention:
            # メンションは即座にMESSAGEイベントをenqueue
            message_event = Event(
                type=EventType.MESSAGE,
                payload={
                    "channel_id": channel_id,
                    "thread_ts": message.thread_ts,
                    "message": message,
                },
            )
            await event_queue.enqueue(message_event)
            logger.info("Enqueued MESSAGE event (mention): %s", event.get("ts"))
        else:
            # 非メンションはJUDGMENTイベントを遅延enqueue
            delay = calculate_wait_with_jitter(
                config.response.min_wait_seconds,
                config.response.jitter_ratio,
            )
            judgment_event = Event(
                type=EventType.JUDGMENT,
                payload={
                    "channel_id": channel_id,
                    "thread_ts": message.thread_ts,
                    "message": message,
                },
            )
            await event_queue.enqueue(judgment_event, delay=delay)
            logger.info(
                "Enqueued JUDGMENT event with delay=%ds: %s",
                delay,
                event.get("ts"),
            )
```

---

## アプリケーション層の変更

### JudgmentEventHandler（新規作成）

**ファイル**: `src/myao2/application/handlers/judgment_handler.py`

```python
"""Handler for JUDGMENT events."""

import logging

from myao2.application.use_cases.helpers import (
    build_context_with_memory,
    log_llm_metrics,
)
from myao2.config import PersonaConfig
from myao2.domain.entities import Event, Message
from myao2.domain.entities.event import EventType
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.domain.repositories.memo_repository import MemoRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.services.response_judgment import ResponseJudgment
from myao2.infrastructure.events.dispatcher import event_handler
from myao2.infrastructure.events.queue import EventQueue

logger = logging.getLogger(__name__)


class JudgmentEventHandler:
    """Handler for JUDGMENT events.

    Executes judgment and enqueues MESSAGE event if should_respond is true.
    """

    def __init__(
        self,
        event_queue: EventQueue,
        response_judgment: ResponseJudgment,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        memory_repository: MemoryRepository,
        persona: PersonaConfig,
        memo_repository: MemoRepository | None = None,
    ) -> None:
        """Initialize the handler."""
        self._event_queue = event_queue
        self._response_judgment = response_judgment
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._memory_repository = memory_repository
        self._persona = persona
        self._memo_repository = memo_repository

    @event_handler(EventType.JUDGMENT)
    async def handle(self, event: Event) -> None:
        """Handle JUDGMENT event.

        Processing flow:
        1. Build context with memory
        2. Execute judgment
        3. If should_respond=true, enqueue MESSAGE event with delay_seconds

        Args:
            event: The JUDGMENT event.
        """
        message: Message = event.payload["message"]
        channel_id = event.payload["channel_id"]
        thread_ts = event.payload.get("thread_ts")

        logger.info(
            "Handling JUDGMENT event: channel=%s, thread_ts=%s",
            channel_id,
            thread_ts,
        )

        # 1. Get channel
        channel = await self._channel_repository.find_by_id(channel_id)
        if channel is None:
            logger.warning("Channel not found: %s", channel_id)
            return

        # 2. Build context with memory
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=channel,
            persona=self._persona,
            target_thread_ts=thread_ts,
            memo_repository=self._memo_repository,
        )

        # 3. Execute judgment
        try:
            judgment_result = await self._response_judgment.judge(context=context)
            log_llm_metrics("judge", judgment_result.metrics)
            logger.info(
                "Judgment result: should_respond=%s, delay_seconds=%s, reason=%s",
                judgment_result.should_respond,
                judgment_result.delay_seconds,
                judgment_result.reason,
            )
        except Exception:
            logger.exception("Error executing judgment")
            return

        # 4. If should_respond=true, enqueue MESSAGE event
        if not judgment_result.should_respond:
            logger.debug("Not responding to message (judgment: should_respond=false)")
            return

        delay_seconds = judgment_result.delay_seconds or 0
        message_event = Event(
            type=EventType.MESSAGE,
            payload={
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message": message,
            },
        )
        await self._event_queue.enqueue(message_event, delay=delay_seconds)
        logger.info(
            "Enqueued MESSAGE event with delay=%ds after judgment",
            delay_seconds,
        )
```

### MessageEventHandler の簡素化

**ファイル**: `src/myao2/application/handlers/message_handler.py`

**変更点**:
- JudgmentCache関連のロジックを削除
- 応答生成・送信に専念

```python
class MessageEventHandler:
    """Handler for MESSAGE events.

    Generates and sends responses. Does not perform judgment.
    """

    def __init__(
        self,
        messaging_service: MessagingService,
        response_generator: ResponseGenerator,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        memory_repository: MemoryRepository,
        persona: PersonaConfig,
        bot_user_id: str,
        memo_repository: MemoRepository | None = None,
    ) -> None:
        """Initialize the handler."""
        # ... JudgmentCacheRepository を削除 ...

    @event_handler(EventType.MESSAGE)
    async def handle(self, event: Event) -> None:
        """Handle MESSAGE event.

        Processing flow:
        1. Build context with memory (re-fetch for latest state)
        2. Generate response
        3. Send response
        4. Save response message

        Args:
            event: The MESSAGE event.
        """
        # ... 既存の応答生成・送信ロジック ...
        # JudgmentCache作成ロジックを削除
```

---

## 廃止するコンポーネント

| コンポーネント | ファイル | 理由 |
|---------------|---------|------|
| AutonomousCheckEventHandler | `application/handlers/autonomous_check_handler.py` | メッセージ駆動化により不要 |
| AutonomousResponseUseCase | `application/use_cases/autonomous_response.py` | メッセージ駆動化により不要 |
| JudgmentCache | `domain/entities/judgment_cache.py` | EventQueue重複制御に統一 |
| JudgmentCacheRepository | `domain/repositories/judgment_cache_repository.py` | JudgmentCache廃止に伴い不要 |
| SQLiteJudgmentCacheRepository | `infrastructure/persistence/judgment_cache_repository.py` | JudgmentCache廃止に伴い不要 |
| EventTypeのAUTONOMOUS_CHECK | `domain/entities/event.py` | イベント種別の廃止 |
| EventSchedulerのAUTONOMOUS_CHECK部分 | `infrastructure/events/scheduler.py` | 定期チェックの廃止 |

---

## 設定変更

既存の設定項目を再利用:

```yaml
response:
  min_wait_seconds: 300    # judgment遅延の基準値（秒）
  jitter_ratio: 0.3        # ±30%のばらつき
  # check_interval_seconds は不要になる（参照しなくなる）
```

---

## ディレクトリ構成（変更後）

```
src/myao2/
├── domain/
│   ├── entities/
│   │   ├── event.py              # JUDGMENT追加、AUTONOMOUS_CHECK削除
│   │   ├── judgment_result.py    # delay_seconds追加
│   │   # judgment_cache.py 削除
│   │   └── ...
│   └── repositories/
│       # judgment_cache_repository.py 削除
│       └── ...
├── application/
│   ├── handlers/
│   │   ├── __init__.py           # JudgmentEventHandler追加、AutonomousCheckEventHandler削除
│   │   ├── judgment_handler.py   # 新規
│   │   ├── message_handler.py    # 簡素化
│   │   ├── summary_handler.py
│   │   └── channel_sync_handler.py
│   ├── use_cases/
│   │   ├── generate_memory.py
│   │   └── helpers.py
│   │   # autonomous_response.py 削除
│   └── ...
├── infrastructure/
│   ├── events/
│   │   ├── queue.py
│   │   ├── dispatcher.py
│   │   ├── loop.py
│   │   └── scheduler.py          # AUTONOMOUS_CHECK削除
│   ├── llm/
│   │   ├── strands/
│   │   │   ├── models.py         # delay_seconds追加
│   │   │   ├── response_judgment.py
│   │   │   └── ...
│   │   └── templates/
│   │       ├── judgment_system.j2    # delay_secondsガイドライン追加
│   │       └── ...
│   └── persistence/
│       # judgment_cache_repository.py 削除
│       └── ...
├── presentation/
│   └── slack_handlers.py         # 2フロー実装
└── __main__.py                   # 依存関係変更
```

---

## 実装タスク

### Phase 1: ドメイン層

- [ ] `src/myao2/domain/entities/judgment_result.py` に `delay_seconds` フィールド追加
- [ ] `src/myao2/domain/entities/event.py` に `JUDGMENT` 追加、`AUTONOMOUS_CHECK` 削除
- [ ] `src/myao2/domain/entities/__init__.py` 更新
- [ ] `tests/domain/entities/test_judgment_result.py` 更新
- [ ] `tests/domain/entities/test_event.py` 更新

### Phase 2: インフラ層

- [ ] `src/myao2/infrastructure/llm/strands/models.py` の `JudgmentOutput` に `delay_seconds` 追加
- [ ] `src/myao2/infrastructure/llm/strands/response_judgment.py` の `judge()` 更新
- [ ] `src/myao2/infrastructure/llm/templates/judgment_system.j2` 更新
- [ ] `src/myao2/infrastructure/events/scheduler.py` から AUTONOMOUS_CHECK 削除
- [ ] `tests/infrastructure/llm/` 配下のテスト更新
- [ ] `tests/infrastructure/events/test_scheduler.py` 更新

### Phase 3: アプリケーション層

- [ ] `src/myao2/application/handlers/judgment_handler.py` 新規作成
- [ ] `src/myao2/application/handlers/message_handler.py` 簡素化（JudgmentCache削除）
- [ ] `src/myao2/application/handlers/__init__.py` 更新
- [ ] `tests/application/handlers/test_judgment_handler.py` 新規作成
- [ ] `tests/application/handlers/test_message_handler.py` 更新

### Phase 4: プレゼンテーション層

- [ ] `src/myao2/presentation/slack_handlers.py` 2フロー実装
- [ ] `tests/presentation/test_slack_handlers.py` 更新

### Phase 5: エントリポイント

- [ ] `src/myao2/__main__.py` 依存関係変更

### Phase 6: クリーンアップ

- [ ] `src/myao2/application/handlers/autonomous_check_handler.py` 削除
- [ ] `src/myao2/application/use_cases/autonomous_response.py` 削除
- [ ] `src/myao2/domain/entities/judgment_cache.py` 削除
- [ ] `src/myao2/domain/repositories/judgment_cache_repository.py` 削除
- [ ] `src/myao2/infrastructure/persistence/judgment_cache_repository.py` 削除
- [ ] 関連テストの削除
- [ ] `__init__.py` ファイルの更新

---

## 検証方法

```bash
# テスト実行
uv run pytest

# Linter
uv run ruff check .
uv run ruff format .

# 型チェック
uv run ty check
```

### 手動検証

1. **メンション** → 即座に応答
2. **非メンション（should_respond=true, delay_seconds=0）** → min_wait_seconds+jitter後に応答
3. **非メンション（should_respond=true, delay_seconds>0）** → min_wait_seconds+jitter+delay_seconds後に応答
4. **非メンション（should_respond=false）** → 応答なし
5. **連続メッセージ** → 古いイベントがキャンセルされ、最初から再スケジュール

---

## 考慮事項

### パフォーマンス

- 非メンションメッセージでは遅延後にjudgmentを実行するため、連続メッセージの場合は重複排除によりLLM呼び出しが1回に削減される
- メンションの場合はjudgmentをスキップするため、高速な応答が可能

### エラーハンドリング

- judgment失敗時は応答しない（ログ出力のみ）
- メンションの場合はjudgmentをスキップするため、失敗の影響を受けない

### 既存機能との互換性

- EventQueueの重複制御機能を活用（JudgmentCacheを廃止）
- 起動時の未応答スレッドは対応しない（新規メッセージのみ）

### 将来の拡張

- メッセージ種別による判断ロジックの追加
- ユーザー単位の応答頻度制御
- チャンネル単位の応答ポリシー設定
