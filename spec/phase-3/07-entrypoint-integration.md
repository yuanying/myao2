# 07: エントリポイント統合

## 目的

main() で定期チェックループと Socket Mode を並行実行するよう
エントリポイントを修正する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/__main__.py` | エントリポイント修正 |

---

## 依存関係

- タスク 01（ResponseConfig）
- タスク 02（ChannelMonitor）
- タスク 03（ResponseJudgment）
- タスク 05（AutonomousResponseUseCase）
- タスク 06（PeriodicChecker）

---

## 現在の実装（Phase 2.5）

```python
async def main() -> None:
    # 設定読み込み
    config = load_config()
    setup_logging(config.logging)

    # 依存オブジェクト初期化
    app = AsyncApp(token=config.slack.bot_token)
    # ... 各種サービス初期化 ...

    # ハンドラ登録
    slack_handlers = SlackHandlers(...)
    slack_handlers.register(app)

    # Socket Mode 開始
    handler = AsyncSocketModeHandler(app, config.slack.app_token)
    await handler.start_async()
```

---

## 変更後の実装

### 概要

```python
async def main() -> None:
    # 設定読み込み
    config = load_config()
    setup_logging(config.logging)

    # 依存オブジェクト初期化（既存 + 新規）
    # ...

    # 定期チェッカー初期化
    periodic_checker = PeriodicChecker(
        autonomous_response_usecase=...,
        config=config.response,
    )

    # ハンドラ登録
    # ...

    # 並行実行
    handler = AsyncSocketModeHandler(app, config.slack.app_token)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(handler.start_async())
        tg.create_task(periodic_checker.start())
```

---

## 依存オブジェクトの初期化

### 新規追加するオブジェクト

```python
# ChannelMonitor
channel_monitor = SlackChannelMonitor(
    client=slack_client,
)

# ResponseJudgment
response_judgment = LLMResponseJudgment(
    llm_config=config.llm.get("judgment", config.llm["default"]),
)

# AutonomousResponseUseCase
autonomous_response_usecase = AutonomousResponseUseCase(
    channel_monitor=channel_monitor,
    response_judgment=response_judgment,
    response_generator=response_generator,
    messaging_service=messaging_service,
    message_repository=message_repository,
    conversation_history_service=conversation_history_service,
    config=config,
)

# PeriodicChecker
periodic_checker = PeriodicChecker(
    autonomous_response_usecase=autonomous_response_usecase,
    config=config.response,
)
```

---

## 並行実行パターン

### asyncio.TaskGroup（Python 3.11+）

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(handler.start_async())
    tg.create_task(periodic_checker.start())
```

### asyncio.gather（Python 3.10 互換）

```python
await asyncio.gather(
    handler.start_async(),
    periodic_checker.start(),
)
```

---

## シャットダウンハンドリング

### 現状

- Ctrl+C で KeyboardInterrupt
- handler.start_async() が終了

### 変更後

- Ctrl+C で両タスクを停止
- periodic_checker.stop() を呼び出し
- グレースフルシャットダウン

```python
import signal

async def main() -> None:
    # ...

    # シグナルハンドラ設定
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        periodic_checker.stop()
        # handler は自動的に終了する

    loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    # 並行実行
    # ...
```

---

## テスト観点

エントリポイントの統合テストは困難なため、以下で確認：

- 各コンポーネントの単体テスト
- 手動での動作確認（タスク 08）

---

## 設計上の考慮事項

### エラー分離

- Socket Mode のエラーは定期チェックに影響しない
- 定期チェックのエラーは Socket Mode に影響しない

### リソース管理

- 両タスクが同じ依存オブジェクトを共有
- SQLite アクセスは非同期ラッパー経由で安全

### 設定による制御

- config.response.enabled=False で定期チェックを無効化可能
- メンション応答のみの動作も可能

---

## 完了基準

- [ ] __main__.py が修正されている
- [ ] Socket Mode と定期チェックが並行実行される
- [ ] Ctrl+C でグレースフルに終了する
- [ ] response.enabled=False で定期チェックが無効化される
- [ ] 起動時のログに両コンポーネントの開始が記録される
