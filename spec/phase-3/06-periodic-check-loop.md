# 06: 定期チェックループ

## 目的

asyncio タスクとして定期的にチャンネルをチェックし、
自律応答ユースケースを実行するサービスを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/services/__init__.py` | モジュール初期化 |
| `src/myao2/application/services/periodic_checker.py` | PeriodicChecker |
| `tests/application/services/test_periodic_checker.py` | テスト |

---

## 依存関係

- タスク 01（ResponseConfig）の check_interval_seconds
- タスク 05（AutonomousResponseUseCase）

---

## インターフェース設計

### PeriodicChecker

```python
class PeriodicChecker:
    """定期チェックサービス

    指定間隔で自律応答ユースケースを実行する。
    asyncio タスクとして動作し、停止シグナルでグレースフルに終了する。
    """

    def __init__(
        self,
        autonomous_response_usecase: AutonomousResponseUseCase,
        config: ResponseConfig,
    ) -> None:
        ...

    async def start(self) -> None:
        """定期チェックを開始する

        停止シグナルを受け取るまでループを継続する。
        """
        ...

    async def stop(self) -> None:
        """定期チェックを停止する

        現在の処理が完了してからループを終了する。
        """
        ...

    @property
    def is_running(self) -> bool:
        """実行中かどうか"""
        ...
```

---

## 処理フロー

```
[start]
    │
    ├─> ループ開始
    │   │
    │   ├─> enabled チェック
    │   │   └─> False なら終了
    │   │
    │   ├─> AutonomousResponseUseCase.execute()
    │   │
    │   ├─> 例外発生時:
    │   │   └─> ログ出力、継続
    │   │
    │   ├─> check_interval_seconds 待機
    │   │   （asyncio.sleep）
    │   │
    │   └─> 停止シグナル確認
    │       └─> 停止シグナルあり → ループ終了
    │
    └─> [完了]

[stop]
    │
    ├─> 停止シグナル設定（asyncio.Event）
    │
    └─> 現在の処理完了を待機
```

---

## グレースフルシャットダウン

### 停止シグナル

- `asyncio.Event` を使用
- `stop()` 呼び出しで Event を set
- ループ内で Event をチェックし、set されていれば終了

### 待機中の停止

- `asyncio.wait_for` または `asyncio.Event.wait` を使用
- sleep 中でも停止シグナルに応答可能

---

## 実装パターン

```python
async def start(self) -> None:
    self._stop_event = asyncio.Event()

    while not self._stop_event.is_set():
        if not self._config.enabled:
            break

        try:
            await self._usecase.execute()
        except Exception as e:
            logger.error(f"Periodic check failed: {e}")

        # 停止シグナルを待ちつつ sleep
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=self._config.check_interval_seconds,
            )
            break  # 停止シグナル受信
        except asyncio.TimeoutError:
            pass  # タイムアウト = 次のループへ

async def stop(self) -> None:
    self._stop_event.set()
```

---

## テストケース

### start

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常動作 | ループ実行 | ユースケースが呼ばれる |
| 停止シグナル | stop() 呼び出し | ループ終了 |
| enabled=False | 設定で無効 | 即座に終了 |
| 例外発生 | ユースケースでエラー | ログ出力、継続 |

### stop

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 通常停止 | stop() 呼び出し | is_running=False |
| sleep 中の停止 | 待機中に stop() | 即座に終了 |

---

## 設計上の考慮事項

### 並行実行

- PeriodicChecker は単一の asyncio タスクとして動作
- Socket Mode ハンドラと並行して実行される

### エラー耐性

- 個別のチェック失敗でループは停止しない
- エラーをログに記録し、次のチェックを継続

### リソース管理

- stop() で確実にループを終了
- asyncio.Event で安全な停止シグナル

---

## 完了基準

- [ ] PeriodicChecker が定義されている
- [ ] 指定間隔でユースケースが実行される
- [ ] stop() でグレースフルに終了する
- [ ] enabled=False で起動しない
- [ ] 例外発生時も継続する
- [ ] 全テストケースが通過する
