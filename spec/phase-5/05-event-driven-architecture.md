# 05: イベント駆動アーキテクチャ

## 概要

現在の直接呼び出し方式のアーキテクチャをイベント駆動アーキテクチャに書き換える。Slackイベント処理と定期実行処理を統一的なイベントシステムで扱い、柔軟な拡張性と重複制御を実現する。

## 目的

- **統一的なイベント処理**: Slackメッセージ、定期実行タスクを同一のイベントシステムで処理
- **重複イベント制御**: 同一イベントの重複発火を防止し、最新のイベントを優先
- **遅延発火機能**: `delay` パラメータによる遅延enqueueのサポート
- **疎結合化**: Slack連携層とビジネスロジックの分離を強化

---

## アーキテクチャ変更

### 現在のアーキテクチャ

```
Slack Event → slack_handlers.py → ReplyToMentionUseCase → 応答生成
                                                        ↘ DB保存

定期実行 → PeriodicChecker → AutonomousResponseUseCase → 応答生成
                           → チャンネル同期
         → BackgroundMemory → GenerateMemoryUseCase → サマリー生成
```

### 新アーキテクチャ

```
Slack Event → slack_handlers.py → EventQueue ─┐
                                              │
定期実行 → EventScheduler ────────────────────┤
                                              ↓
                                         EventLoop → EventDispatcher
                                                          │
                          ┌───────────────────┬───────────┼───────────┬──────────────────┐
                          ↓                   ↓           ↓           ↓                  ↓
                  MessageHandler      SummaryHandler    AutonomousCheckHandler    ChannelSyncHandler
                          │                   │           │                             │
                          ↓                   ↓           ↓                             ↓
                  応答生成・送信       GenerateMemoryUC  AutonomousResponseUC     チャンネル同期
```

---

## ドメイン層

### Event エンティティ

**ファイル**: `src/myao2/domain/entities/event.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(Enum):
    """イベント種別"""
    MESSAGE = "message"                    # メッセージ受信（mention）
    SUMMARY = "summary"                    # サマリー生成
    AUTONOMOUS_CHECK = "autonomous_check"  # 自律応答チェック
    CHANNEL_SYNC = "channel_sync"          # チャンネル同期


@dataclass(frozen=True)
class Event:
    """ドメインイベント

    Attributes:
        type: イベント種別
        payload: イベント固有のデータ
        created_at: イベント作成時刻
    """
    type: EventType
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_identity_key(self) -> str:
        """重複判定用の識別キーを返す"""
        if self.type == EventType.MESSAGE:
            channel_id = self.payload.get("channel_id", "")
            thread_ts = self.payload.get("thread_ts") or ""
            return f"message:{channel_id}:{thread_ts}"
        elif self.type == EventType.SUMMARY:
            return "summary:workspace"
        elif self.type == EventType.AUTONOMOUS_CHECK:
            return "autonomous_check:workspace"
        elif self.type == EventType.CHANNEL_SYNC:
            return "channel_sync:workspace"
        return f"{self.type.value}:unknown"
```

### イベント種別ごとのペイロード仕様

| イベント種別 | ペイロード | 識別キー |
|-------------|-----------|---------|
| MESSAGE | `channel_id`, `thread_ts`, `message`, `is_mention` | `message:{channel_id}:{thread_ts}` |
| SUMMARY | なし | `summary:workspace` |
| AUTONOMOUS_CHECK | なし | `autonomous_check:workspace` |
| CHANNEL_SYNC | なし | `channel_sync:workspace` |

---

## インフラ層

### EventQueue（イベントキュー）

**ファイル**: `src/myao2/infrastructure/events/queue.py`

インメモリのイベントキュー。重複イベント制御と遅延enqueueを担当。

#### 主要機能

- `enqueue(event, delay=None)`: イベントをキューに追加
  - `delay` が指定された場合、その秒数後にキューに追加
  - 同一 `identity_key` のイベントが既に保留中の場合、古いイベントをキャンセルして新しいイベントを登録
- `dequeue()`: キューからイベントを取得（ブロッキング）
- `mark_done(event)`: イベント処理完了をマーク

#### 重複イベント制御

```python
# 同一identity_keyのイベントが発火された場合の動作
#
# ケース1: キュー内に同一identity_keyのイベントが存在
#   → 古いイベントをキューから削除し、新しいイベントを追加
#
# ケース2: 同一identity_keyのイベントが処理中
#   → 新しいイベントをキューに追加（処理完了後に実行される）
#
# ケース3: 遅延enqueue中に新しい同一イベントが来た
#   → 遅延タイマーをキャンセルし、新しいイベントを優先

# 例: 連続したSlackメッセージ
# 1. Event A (identity_key="message:C123:T456") がキューに追加される
# 2. Event B (identity_key="message:C123:T456") がキューに追加される
# 3. Event A はキューから削除され、Event B のみが処理される
```

#### 遅延enqueue

```python
# 遅延enqueueの例
await queue.enqueue(event, delay=30)  # 30秒後にキューに追加

# 遅延中に同じidentity_keyのイベントが来た場合
# → 遅延タイマーをキャンセルし、新しいイベントを即座にenqueue（または新しい遅延で）
```

### EventDispatcher（イベントディスパッチャー）

**ファイル**: `src/myao2/infrastructure/events/dispatcher.py`

イベントハンドラの登録とディスパッチを担当。

#### デコレータによるハンドラ登録

```python
from myao2.infrastructure.events.dispatcher import event_handler
from myao2.domain.entities.event import Event, EventType

@event_handler(EventType.MESSAGE)
async def handle_message(event: Event) -> None:
    """メッセージイベントを処理"""
    ...
```

#### 登録と実行

```python
dispatcher = EventDispatcher()
dispatcher.register_handler(handler.handle)  # デコレータ付きメソッドを登録
await dispatcher.dispatch(event)             # イベントを適切なハンドラに配信
```

### EventLoop（イベントループ）

**ファイル**: `src/myao2/infrastructure/events/loop.py`

キューからイベントを取り出し、ディスパッチャーに渡す非同期ループ。

**処理方式**: 逐次処理（1イベントずつ順番に処理）

```python
event_loop = EventLoop(queue, dispatcher)
await event_loop.start()  # イベント処理を開始
await event_loop.stop()   # Graceful shutdown
```

### EventScheduler（イベントスケジューラー）

**ファイル**: `src/myao2/infrastructure/events/scheduler.py`

定期実行イベントをスケジュール。

| イベント | 発火間隔 | 設定項目 |
|---------|---------|---------|
| AUTONOMOUS_CHECK | `check_interval_seconds` | `config.response.check_interval_seconds` |
| SUMMARY | `long_term_update_interval_seconds` | `config.memory.long_term_update_interval_seconds` |
| CHANNEL_SYNC | `channel_sync_interval_seconds` | `config.response.channel_sync_interval_seconds`（新規） |

---

## アプリケーション層

### イベントハンドラ

**ディレクトリ**: `src/myao2/application/handlers/`

#### MessageEventHandler

**ファイル**: `src/myao2/application/handlers/message_handler.py`

`ReplyToMentionUseCase` の機能を引き継ぐ。メンションメッセージを受信した際に応答を生成・送信。

**処理フロー**:
1. botからのメッセージかチェック（無視）
2. メンションかチェック（非メンションは無視）
3. コンテキスト構築（メモリ、メモ含む）
4. LLMで応答生成
5. Slackに投稿
6. 応答メッセージをDB保存
7. 判定キャッシュ作成（重複応答防止）

**将来の拡張**: 全メッセージイベント化時は、ここでjudgement結果に基づいて処理を分岐。

#### SummaryEventHandler

**ファイル**: `src/myao2/application/handlers/summary_handler.py`

`GenerateMemoryUseCase` を呼び出してサマリーを生成。

#### AutonomousCheckEventHandler

**ファイル**: `src/myao2/application/handlers/autonomous_check_handler.py`

`AutonomousResponseUseCase` を呼び出して自律応答チェックを実行。

**将来の変更**: 全メッセージイベント化により廃止予定。

#### ChannelSyncEventHandler

**ファイル**: `src/myao2/application/handlers/channel_sync_handler.py`

チャンネル同期（staleチャンネル削除）を実行。`PeriodicChecker` の `sync_channels` 機能を移行。

---

## プレゼンテーション層

### slack_handlers.py の変更

**ファイル**: `src/myao2/presentation/slack_handlers.py`

**変更前**:
```python
def register_handlers(
    app: AsyncApp,
    reply_use_case: ReplyToMentionUseCase,
    ...
) -> None:
    ...
    # mentionメッセージを直接ユースケースに渡す
    await reply_use_case.execute(message)
```

**変更後**:
```python
def register_handlers(
    app: AsyncApp,
    event_queue: EventQueue,
    ...
) -> None:
    ...
    # mentionメッセージをイベントとしてキューに追加
    event = Event(
        type=EventType.MESSAGE,
        payload={
            "channel_id": message.channel.id,
            "thread_ts": message.thread_ts,
            "message": message,
            "is_mention": True,
        },
    )
    await event_queue.enqueue(event)  # 遅延なし（即座に処理）
```

---

## 廃止するコンポーネント

| コンポーネント | ファイル | 理由 |
|---------------|---------|------|
| ReplyToMentionUseCase | `application/use_cases/reply_to_mention.py` | MessageEventHandler に移行 |
| PeriodicChecker | `application/services/periodic_checker.py` | EventScheduler + ハンドラに移行 |
| BackgroundMemory | `application/services/background_memory.py` | EventScheduler + SummaryEventHandler に移行 |

---

## 設定変更

**config.yaml** に追加:

```yaml
response:
  # 既存
  check_interval_seconds: 300
  # 新規
  channel_sync_interval_seconds: 3600  # 1時間ごとにチャンネル同期
```

**config.yaml.example** も同様に更新。

---

## ディレクトリ構成（変更後）

```
src/myao2/
├── domain/
│   ├── entities/
│   │   ├── event.py              # 新規
│   │   └── ...
│   └── ...
├── application/
│   ├── handlers/                 # 新規ディレクトリ
│   │   ├── __init__.py
│   │   ├── message_handler.py
│   │   ├── summary_handler.py
│   │   ├── autonomous_check_handler.py
│   │   └── channel_sync_handler.py
│   ├── use_cases/
│   │   ├── autonomous_response.py    # 変更なし
│   │   ├── generate_memory.py        # 変更なし
│   │   └── helpers.py                # 変更なし
│   │   # reply_to_mention.py 削除
│   └── services/
│       # periodic_checker.py 削除
│       # background_memory.py 削除
├── infrastructure/
│   ├── events/                   # 新規ディレクトリ
│   │   ├── __init__.py
│   │   ├── queue.py
│   │   ├── dispatcher.py
│   │   ├── loop.py
│   │   └── scheduler.py
│   └── ...
├── presentation/
│   └── slack_handlers.py         # 変更
└── __main__.py                   # 変更
```

---

## 実装タスク

### Phase 1: ドメイン層

- [ ] `src/myao2/domain/entities/event.py` 作成
- [ ] `src/myao2/domain/entities/__init__.py` 更新
- [ ] `tests/domain/entities/test_event.py` 作成

### Phase 2: インフラ層（イベントシステム）

- [ ] `src/myao2/infrastructure/events/__init__.py` 作成
- [ ] `src/myao2/infrastructure/events/queue.py` 作成
- [ ] `src/myao2/infrastructure/events/dispatcher.py` 作成
- [ ] `src/myao2/infrastructure/events/loop.py` 作成
- [ ] `src/myao2/infrastructure/events/scheduler.py` 作成
- [ ] `tests/infrastructure/events/` 配下にテスト作成

### Phase 3: アプリケーション層（ハンドラ）

- [ ] `src/myao2/application/handlers/__init__.py` 作成
- [ ] `src/myao2/application/handlers/message_handler.py` 作成
- [ ] `src/myao2/application/handlers/summary_handler.py` 作成
- [ ] `src/myao2/application/handlers/autonomous_check_handler.py` 作成
- [ ] `src/myao2/application/handlers/channel_sync_handler.py` 作成
- [ ] `tests/application/handlers/` 配下にテスト作成

### Phase 4: 統合

- [ ] `src/myao2/presentation/slack_handlers.py` 変更
- [ ] `src/myao2/__main__.py` 変更
- [ ] `config.yaml.example` に `channel_sync_interval_seconds` 追加
- [ ] 統合テスト作成

### Phase 5: クリーンアップ

- [ ] `src/myao2/application/use_cases/reply_to_mention.py` 削除
- [ ] `src/myao2/application/services/periodic_checker.py` 削除
- [ ] `src/myao2/application/services/background_memory.py` 削除
- [ ] 関連テストの削除/更新
- [ ] `src/myao2/application/use_cases/__init__.py` 更新

---

## 検証方法

```bash
# テスト実行
uv run pytest

# 特定テストのみ
uv run pytest tests/domain/entities/test_event.py
uv run pytest tests/infrastructure/events/
uv run pytest tests/application/handlers/

# Linter
uv run ruff check .
uv run ruff format .

# 型チェック
uv run ty check
```

### 手動検証

1. アプリケーション起動
2. Slackでボットにメンション → 応答が返ることを確認
3. 定期実行でサマリー生成・自律応答チェック・チャンネル同期が動作することを確認
4. 連続メンション時に重複応答が発生しないことを確認

---

## 考慮事項

### エラーハンドリング

- ハンドラでの例外はキャッチしてログ出力、他のイベント処理は継続
- キュー操作の失敗は即座にログ出力

### シャットダウン

- `EventLoop.stop()` で処理中のイベントを待機せずに終了
- `EventScheduler.stop()` で定期実行を停止
- キューに残っているイベントは破棄（インメモリのため）

### 将来の拡張性

#### 全メッセージイベント化（Phase 6以降）

1. slack_handlers.py で全メッセージをMESSAGEイベントとして発火
2. イベント発火前にjudgementを実行し、遅延時間を決定
3. `queue.enqueue(event, delay=judgment_result.delay)` で遅延enqueue
4. MessageEventHandler で応答生成
5. AutonomousResponseUseCase は廃止

#### その他

- 新しいイベント種別は `EventType` に追加
- 新しいハンドラは `@event_handler` デコレータで登録
- 永続化が必要になった場合は `EventQueue` をDB対応版に差し替え
