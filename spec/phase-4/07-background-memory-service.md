# 07: バックグラウンド記憶生成サービス

## 目的

定期的に記憶を生成するバックグラウンドサービスを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/services/background_memory.py` | BackgroundMemoryGenerator（新規） |
| `src/myao2/application/services/__init__.py` | BackgroundMemoryGenerator エクスポート（修正） |
| `tests/application/services/test_background_memory.py` | テスト（新規） |

---

## 依存関係

- タスク 06（GenerateMemoryUseCase）に依存

---

## インターフェース設計

### BackgroundMemoryGenerator

```python
import asyncio
import logging

from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.config.models import MemoryConfig

logger = logging.getLogger(__name__)


class BackgroundMemoryGenerator:
    """バックグラウンド記憶生成サービス

    定期的に記憶を生成する。
    """

    def __init__(
        self,
        generate_memory_use_case: GenerateMemoryUseCase,
        config: MemoryConfig,
    ) -> None:
        self._generate_memory_use_case = generate_memory_use_case
        self._config = config
        self._stop_event = asyncio.Event()
        self._running = False

    async def start(self) -> None:
        """記憶生成ループを開始する

        停止イベントが設定されるまで、定期的に記憶を生成する。
        """
        ...

    async def stop(self) -> None:
        """記憶生成ループを停止する"""
        ...

    @property
    def is_running(self) -> bool:
        """実行中かどうかを返す"""
        return self._running
```

---

## 実装詳細

### start()

```python
async def start(self) -> None:
    """記憶生成ループを開始する"""
    logger.info("Starting background memory generator")
    self._running = True
    self._stop_event.clear()

    try:
        while not self._stop_event.is_set():
            try:
                logger.info("Running memory generation")
                await self._generate_memory_use_case.execute()
                logger.info("Memory generation completed")
            except Exception:
                logger.exception("Error during memory generation")

            # 次回実行まで待機（停止イベントで中断可能）
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._config.long_term_update_interval_seconds,
                )
                # 停止イベントが設定された場合
                break
            except asyncio.TimeoutError:
                # タイムアウト = 次のイテレーション
                continue
    finally:
        self._running = False
        logger.info("Background memory generator stopped")
```

### stop()

```python
async def stop(self) -> None:
    """記憶生成ループを停止する"""
    logger.info("Stopping background memory generator")
    self._stop_event.set()
```

---

## 処理フロー

```
1. start() が呼び出される
2. ループ開始:
   a. generate_memory_use_case.execute() を実行
      - 長期記憶・短期記憶ともに同時に処理される
      - ただし、新しいメッセージがなければ記憶は更新されない
   b. エラーが発生した場合はログに記録して続行
   c. long_term_update_interval_seconds 秒待機
   d. 停止イベントが設定されていればループ終了
3. stop() が呼び出されると停止イベントが設定される
4. 待機中に停止イベントが設定されるとすぐにループ終了
```

### 更新間隔について

長期記憶・短期記憶ともに `long_term_update_interval_seconds` ごとに更新チェックが行われる。
ただし、GenerateMemoryUseCase 内で新しいメッセージの有無を確認し、
更新がなければ既存の記憶がそのまま保持されるため、不必要な再生成は行われない。

---

## 設計上の考慮事項

### グレースフルシャットダウン

- `asyncio.Event` を使用して停止シグナルを伝達
- 待機中でも停止イベントですぐに終了
- 記憶生成中は完了を待ってから終了

### エラーハンドリング

- 記憶生成中のエラーはログに記録
- エラーが発生してもサービスは継続
- 次回のイテレーションで再試行

### ログ

- 開始・終了・エラーをログに記録
- デバッグ用に詳細なログを出力

### 初回実行

- start() 直後に即座に記憶生成を開始
- アプリケーション起動時に記憶を最新化

---

## PeriodicChecker との比較

| 項目 | PeriodicChecker | BackgroundMemoryGenerator |
|------|-----------------|---------------------------|
| 目的 | 応答判定 | 記憶生成（長期・短期両方） |
| 間隔設定 | check_interval_seconds | long_term_update_interval_seconds |
| 停止制御 | asyncio.Event | asyncio.Event |
| エラー処理 | ログ記録して続行 | ログ記録して続行 |
| 更新スキップ | - | 新メッセージがなければスキップ |

---

## テストケース

### start / stop

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常起動 | start() 呼び出し | is_running が True |
| 正常停止 | stop() 呼び出し | is_running が False |
| 即時停止 | start() 直後に stop() | 速やかに停止 |

### 記憶生成

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 定期実行 | 間隔経過 | generate_memory_use_case.execute() が呼ばれる |
| エラー時 | execute() で例外 | ログ記録、サービス継続 |

### 待機中断

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 停止中断 | 待機中に stop() | 待機がキャンセルされる |

---

## 使用例

### 基本的な使用

```python
# 初期化
background_memory = BackgroundMemoryGenerator(
    generate_memory_use_case=generate_memory_use_case,
    config=memory_config,
)

# 起動（バックグラウンドタスクとして）
memory_task = asyncio.create_task(background_memory.start())

# ... アプリケーション処理 ...

# 停止
await background_memory.stop()
await memory_task
```

### asyncio.gather での使用

```python
async def main():
    # ... 初期化 ...

    # バックグラウンドタスク
    periodic_checker = PeriodicChecker(...)
    background_memory = BackgroundMemoryGenerator(...)

    # 並行実行
    async def run_with_shutdown():
        try:
            await asyncio.gather(
                socket_handler.start_async(),
                periodic_checker.start(),
                background_memory.start(),
            )
        finally:
            await periodic_checker.stop()
            await background_memory.stop()

    await run_with_shutdown()
```

---

## 完了基準

- [x] BackgroundMemoryGenerator が実装されている
- [x] start() で記憶生成ループが開始される
- [x] stop() で記憶生成ループが停止される
- [x] 定期的に記憶生成が実行される
- [x] エラーが発生してもサービスが継続する
- [x] グレースフルシャットダウンがサポートされている
- [x] `__init__.py` でエクスポートされている
- [x] 全テストケースが通過する
