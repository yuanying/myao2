# 06: GenerateMemoryUseCase（記憶生成ユースケース）

## 目的

ワークスペース/チャンネル/スレッドの記憶を生成するユースケースを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/use_cases/generate_memory.py` | GenerateMemoryUseCase（新規） |
| `src/myao2/application/use_cases/__init__.py` | GenerateMemoryUseCase エクスポート（修正） |
| `tests/application/use_cases/test_generate_memory.py` | テスト（新規） |

---

## 依存関係

- タスク 03（MemoryRepository）に依存
- タスク 05（MemorySummarizer）に依存

---

## インターフェース設計

### GenerateMemoryUseCase

```python
import logging
from datetime import datetime, timedelta

from myao2.config.models import MemoryConfig
from myao2.domain.entities.memory import (
    Memory,
    MemoryScope,
    MemoryType,
    create_memory,
    make_thread_scope_id,
)
from myao2.domain.repositories.channel_repository import ChannelRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.repositories.message_repository import MessageRepository
from myao2.domain.services.memory_summarizer import MemorySummarizer

logger = logging.getLogger(__name__)


class GenerateMemoryUseCase:
    """記憶生成ユースケース

    ワークスペース、チャンネル、スレッドの記憶を生成・更新する。
    """

    # ワークスペースの固定 scope_id
    WORKSPACE_SCOPE_ID = "default"

    def __init__(
        self,
        memory_repository: MemoryRepository,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        memory_summarizer: MemorySummarizer,
        config: MemoryConfig,
    ) -> None:
        self._memory_repository = memory_repository
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._memory_summarizer = memory_summarizer
        self._config = config

    async def execute(self) -> None:
        """全記憶を生成・更新する

        1. ワークスペース記憶を生成
        2. 全チャンネルの記憶を生成
        3. アクティブなスレッドの記憶を生成
        """
        ...

    async def generate_workspace_memory(self) -> None:
        """ワークスペースの記憶を生成・更新する"""
        ...

    async def generate_channel_memory(self, channel_id: str) -> None:
        """チャンネルの記憶を生成・更新する"""
        ...

    async def generate_thread_memory(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> None:
        """スレッドの記憶を生成・更新する"""
        ...
```

---

## 処理フロー

### execute()

```
1. generate_workspace_memory() を呼び出す
2. 全チャンネルを取得
3. 各チャンネルについて:
   a. generate_channel_memory(channel_id) を呼び出す
   b. アクティブなスレッドを特定
   c. 各スレッドについて generate_thread_memory(channel_id, thread_ts) を呼び出す
4. エラーはログに記録し、次のチャンネル/スレッドを処理
```

### generate_workspace_memory()

```
1. 既存のワークスペース長期記憶を取得
2. 前回更新時の最新メッセージ ts を確認
3. 新しいメッセージを取得（全チャンネルから）
4. 新しいメッセージがあれば長期記憶を更新
5. 既存のワークスペース短期記憶を取得
6. 短期記憶用のメッセージを取得（短期間の時間窓）
7. 新しいメッセージがあれば短期記憶を更新（なければ既存を保持）
```

### generate_channel_memory()

```
1. 既存のチャンネル長期記憶を取得
2. 前回更新時の最新メッセージ ts を確認
3. 新しいメッセージを取得（チャンネル内）
4. 新しいメッセージがあれば長期記憶を更新
5. 既存のチャンネル短期記憶を取得
6. 短期記憶用のメッセージを取得（短期間の時間窓）
7. 新しいメッセージがあれば短期記憶を更新（なければ既存を保持）
```

### generate_thread_memory()

```
1. 既存のスレッド短期記憶を取得
2. スレッドのメッセージを取得
3. 新しいメッセージがあれば短期記憶を更新（なければ既存を保持）
```

---

## 実装詳細

### ワークスペース記憶の生成

```python
async def generate_workspace_memory(self) -> None:
    """ワークスペースの記憶を生成・更新する"""
    logger.info("Generating workspace memory")

    # 長期記憶の更新
    await self._generate_memory(
        scope=MemoryScope.WORKSPACE,
        scope_id=self.WORKSPACE_SCOPE_ID,
        memory_type=MemoryType.LONG_TERM,
    )

    # 短期記憶の生成
    await self._generate_memory(
        scope=MemoryScope.WORKSPACE,
        scope_id=self.WORKSPACE_SCOPE_ID,
        memory_type=MemoryType.SHORT_TERM,
    )
```

### 共通記憶生成処理

```python
async def _generate_memory(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
) -> None:
    """記憶を生成・更新する共通処理"""
    # 既存の記憶を取得
    existing = await self._memory_repository.find_by_scope_and_type(
        scope, scope_id, memory_type
    )

    # メッセージを取得
    messages = await self._get_messages_for_memory(
        scope, scope_id, memory_type, existing
    )

    if not messages and not existing:
        logger.debug(f"No messages for {scope.value}/{scope_id}/{memory_type.value}")
        return

    # 新しいメッセージがなければ既存記憶を保持
    if not messages and existing:
        logger.debug(
            f"No new messages for {scope.value}/{scope_id}/{memory_type.value}, "
            "keeping existing memory"
        )
        return

    # 記憶を生成
    existing_content = existing.content if existing else None
    content = await self._memory_summarizer.summarize(
        messages=messages,
        scope=scope,
        memory_type=memory_type,
        existing_memory=existing_content if memory_type == MemoryType.LONG_TERM else None,
    )

    # 記憶を保存
    if existing:
        # 更新
        updated_memory = Memory(
            id=existing.id,
            scope=scope,
            scope_id=scope_id,
            memory_type=memory_type,
            content=content,
            created_at=existing.created_at,
            updated_at=datetime.now(),
            source_message_count=len(messages) + existing.source_message_count,
            source_latest_message_ts=self._get_latest_message_ts(messages)
            or existing.source_latest_message_ts,
        )
    else:
        # 新規作成
        updated_memory = create_memory(
            scope=scope,
            scope_id=scope_id,
            memory_type=memory_type,
            content=content,
            source_message_count=len(messages),
            source_latest_message_ts=self._get_latest_message_ts(messages),
        )

    await self._memory_repository.save(updated_memory)
    logger.info(f"Generated {scope.value}/{scope_id}/{memory_type.value} memory")
```

### メッセージ取得

```python
async def _get_messages_for_memory(
    self,
    scope: MemoryScope,
    scope_id: str,
    memory_type: MemoryType,
    existing: Memory | None,
) -> list[Message]:
    """記憶生成用のメッセージを取得

    長期記憶・短期記憶ともに、既存記憶の source_latest_message_ts 以降の
    新しいメッセージのみを返す。新しいメッセージがなければ空リストを返す。
    """
    if memory_type == MemoryType.LONG_TERM:
        # 長期記憶: 前回更新以降のメッセージ
        since_ts = existing.source_latest_message_ts if existing else None
        return await self._get_messages_since(scope, scope_id, since_ts)
    else:
        # 短期記憶: 時間窓内かつ前回更新以降のメッセージ
        since = datetime.now() - timedelta(hours=self._config.short_term_window_hours)
        since_ts = str(since.timestamp())

        # 既存記憶がある場合、前回の最新メッセージ以降のみ取得
        if existing and existing.source_latest_message_ts:
            # 時間窓の開始点と前回の最新メッセージtsの大きい方を使用
            since_ts = max(since_ts, existing.source_latest_message_ts)

        messages = await self._get_messages_since(scope, scope_id, since_ts)

        # 新しいメッセージがなければ空リストを返す（既存記憶を保持するため）
        return messages
```

---

## アクティブなスレッドの特定

```python
async def _get_active_threads(self, channel_id: str) -> list[str]:
    """アクティブなスレッドを特定する

    短期記憶の時間窓内にメッセージがあるスレッドを返す。
    """
    since = datetime.now() - timedelta(hours=self._config.short_term_window_hours)
    messages = await self._message_repository.find_by_channel_since(
        channel_id=channel_id,
        since=since,
        limit=1000,  # 十分な数
    )

    # スレッドのルートメッセージを収集
    thread_roots: set[str] = set()
    for msg in messages:
        if msg.thread_ts:
            thread_roots.add(msg.thread_ts)

    return list(thread_roots)
```

---

## 設計上の考慮事項

### インクリメンタル更新

- 長期記憶・短期記憶ともに前回更新以降の新しいメッセージのみ処理
- `source_latest_message_ts` で前回の最新メッセージを記録
- 新しいメッセージがなければ既存記憶を保持（再生成しない）
- 長期記憶は LLM で既存記憶と新しいメッセージをマージ
- 短期記憶は時間窓内のメッセージで再生成（ただし更新がある場合のみ）

### エラーハンドリング

- 個別のチャンネル/スレッドでエラーが発生しても他は継続
- エラーはログに記録
- 致命的なエラー（DB 接続エラー等）は例外を送出

### パフォーマンス

- ワークスペース記憶は全チャンネルのメッセージを対象
- チャンネル数が多い場合は処理時間が増加
- 必要に応じて並列処理を検討（将来拡張）

---

## テストケース

### execute

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常系 | 複数チャンネル、複数スレッド | 全記憶が生成される |
| チャンネルなし | チャンネルが空 | エラーなし |
| 部分エラー | 一部チャンネルでエラー | 他チャンネルは処理される |

### generate_workspace_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規生成 | 既存記憶なし | 長期・短期記憶が生成される |
| 更新 | 既存記憶あり、新メッセージあり | 記憶が更新される |
| 更新なし | 既存記憶あり、新メッセージなし | 記憶は変更されない |

### generate_channel_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規生成 | 既存記憶なし | 長期・短期記憶が生成される |
| 更新 | 既存記憶あり | 記憶が更新される |
| メッセージなし | メッセージが空 | 記憶は生成されない |

### generate_thread_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | スレッドにメッセージあり | 短期記憶が生成される |
| メッセージなし | スレッドにメッセージなし | 記憶は生成されない |

---

## 完了基準

- [ ] GenerateMemoryUseCase が実装されている
- [ ] execute() で全記憶が生成される
- [ ] generate_workspace_memory() でワークスペース記憶が生成される
- [ ] generate_channel_memory() でチャンネル記憶が生成される
- [ ] generate_thread_memory() でスレッド記憶が生成される
- [ ] インクリメンタル更新がサポートされている
- [ ] エラーハンドリングが実装されている
- [ ] `__init__.py` でエクスポートされている
- [ ] 全テストケースが通過する
