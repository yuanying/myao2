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
- タスク 04a（Context、ChannelMessages）に依存
- タスク 05（MemorySummarizer）に依存

---

## インターフェース設計

### GenerateMemoryUseCase

```python
import logging
from datetime import datetime, timedelta

from myao2.config.models import MemoryConfig, PersonaConfig
from myao2.domain.entities.channel_messages import ChannelMemory, ChannelMessages
from myao2.domain.entities.context import Context
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
    MemorySummarizer に Context を渡して記憶を生成する。
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
        persona: PersonaConfig,
    ) -> None:
        self._memory_repository = memory_repository
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._memory_summarizer = memory_summarizer
        self._config = config
        self._persona = persona

    async def execute(self) -> None:
        """全記憶を生成・更新する

        処理順序（依存関係に基づく）:
        1. 全チャンネルの短期記憶を生成（メッセージから）
        2. 全チャンネルの長期記憶を生成（短期記憶をマージ）
        3. ワークスペース短期記憶を生成（チャンネル短期記憶を統合）
        4. ワークスペース長期記憶を生成（チャンネル長期記憶を統合）
        5. アクティブなスレッドの短期記憶を生成
        """
        ...

    async def generate_channel_memories(self) -> dict[str, ChannelMemory]:
        """全チャンネルの記憶を生成・更新する

        Returns:
            生成されたチャンネル記憶のマップ（channel_id -> ChannelMemory）
        """
        ...

    async def generate_workspace_memory(
        self,
        channel_memories: dict[str, ChannelMemory],
    ) -> None:
        """ワークスペースの記憶を生成・更新する

        Args:
            channel_memories: チャンネル記憶（ワークスペース記憶生成に使用）
        """
        ...

    async def generate_thread_memory(
        self,
        channel_id: str,
        thread_ts: str,
        channel_memory: ChannelMemory | None = None,
    ) -> None:
        """スレッドの記憶を生成・更新する

        Args:
            channel_id: チャンネル ID
            thread_ts: スレッドの親メッセージ ts
            channel_memory: チャンネルの記憶（補助情報用）
        """
        ...
```

---

## 処理フロー

### execute()

```
1. 全チャンネルを取得
2. 各チャンネルについて:
   a. 短期記憶を生成（メッセージから）
   b. 長期記憶を生成（短期記憶をマージ）
   c. ChannelMemory を構築
3. ワークスペース短期記憶を生成（チャンネル短期記憶を統合）
4. ワークスペース長期記憶を生成（チャンネル長期記憶を統合）
5. 各チャンネルのアクティブなスレッドを特定
6. 各スレッドの短期記憶を生成
7. エラーはログに記録し、次のチャンネル/スレッドを処理
```

### generate_channel_memories()

```
1. 全チャンネルを取得
2. 各チャンネルについて:
   a. 短期記憶を生成:
      - メッセージを取得（時間窓内）
      - Context を構築（conversation_history にメッセージをセット）
      - MemorySummarizer.summarize() を呼び出し
   b. 長期記憶を生成:
      - 既存の長期記憶を取得
      - Context を構築（channel_memories に短期記憶をセット）
      - MemorySummarizer.summarize() を呼び出し
   c. ChannelMemory を構築して返す
```

### generate_workspace_memory()

```
1. 既存のワークスペース長期記憶を取得
2. 短期記憶を生成:
   - Context を構築（channel_memories にチャンネル短期記憶をセット）
   - MemorySummarizer.summarize() を呼び出し
3. 長期記憶を生成:
   - Context を構築（channel_memories にチャンネル長期記憶をセット）
   - MemorySummarizer.summarize() を呼び出し
```

### generate_thread_memory()

```
1. スレッドのメッセージを取得
2. Context を構築:
   - conversation_history にチャンネルメッセージをセット
   - target_thread_ts をセット
   - channel_memories にチャンネル記憶をセット（補助情報用）
3. MemorySummarizer.summarize() を呼び出し（短期記憶のみ）
```

---

## 実装詳細

### チャンネル記憶の生成

```python
async def _generate_channel_short_term_memory(
    self,
    channel_id: str,
    channel_name: str,
) -> str | None:
    """チャンネルの短期記憶を生成する"""
    # 時間窓内のメッセージを取得
    since = datetime.now() - timedelta(hours=self._config.short_term_window_hours)
    messages = await self._message_repository.find_by_channel_since(
        channel_id=channel_id,
        since=since,
        limit=1000,
    )

    if not messages:
        return None

    # ChannelMessages を構築
    channel_messages = self._build_channel_messages(
        channel_id, channel_name, messages
    )

    # Context を構築
    context = Context(
        persona=self._persona,
        conversation_history=channel_messages,
    )

    # 短期記憶を生成
    content = await self._memory_summarizer.summarize(
        context=context,
        scope=MemoryScope.CHANNEL,
        memory_type=MemoryType.SHORT_TERM,
    )

    return content if content else None


async def _generate_channel_long_term_memory(
    self,
    channel_id: str,
    channel_name: str,
    short_term_memory: str | None,
) -> str | None:
    """チャンネルの長期記憶を生成する（短期記憶をマージ）"""
    if not short_term_memory:
        # 短期記憶がなければ既存の長期記憶を維持
        existing = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.CHANNEL, channel_id, MemoryType.LONG_TERM
        )
        return existing.content if existing else None

    # 既存の長期記憶を取得
    existing = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.CHANNEL, channel_id, MemoryType.LONG_TERM
    )
    existing_content = existing.content if existing else None

    # Context を構築（短期記憶を channel_memories にセット）
    channel_messages = ChannelMessages(
        channel_id=channel_id,
        channel_name=channel_name,
    )
    channel_memory = ChannelMemory(
        channel_id=channel_id,
        channel_name=channel_name,
        short_term_memory=short_term_memory,
    )
    context = Context(
        persona=self._persona,
        conversation_history=channel_messages,
        channel_memories={channel_id: channel_memory},
    )

    # 長期記憶を生成
    content = await self._memory_summarizer.summarize(
        context=context,
        scope=MemoryScope.CHANNEL,
        memory_type=MemoryType.LONG_TERM,
        existing_memory=existing_content,
    )

    return content if content else None
```

### ワークスペース記憶の生成

```python
async def generate_workspace_memory(
    self,
    channel_memories: dict[str, ChannelMemory],
) -> None:
    """ワークスペースの記憶を生成・更新する"""
    logger.info("Generating workspace memory")

    # 既存の長期記憶を取得
    existing_long_term = await self._memory_repository.find_by_scope_and_type(
        MemoryScope.WORKSPACE, self.WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
    )
    existing_long_term_content = existing_long_term.content if existing_long_term else None

    # 空の conversation_history を作成
    empty_channel_messages = ChannelMessages(
        channel_id="",
        channel_name="",
    )

    # 短期記憶を生成
    context_short = Context(
        persona=self._persona,
        conversation_history=empty_channel_messages,
        channel_memories=channel_memories,
    )
    short_term_content = await self._memory_summarizer.summarize(
        context=context_short,
        scope=MemoryScope.WORKSPACE,
        memory_type=MemoryType.SHORT_TERM,
    )

    # 長期記憶を生成
    context_long = Context(
        persona=self._persona,
        conversation_history=empty_channel_messages,
        channel_memories=channel_memories,
    )
    long_term_content = await self._memory_summarizer.summarize(
        context=context_long,
        scope=MemoryScope.WORKSPACE,
        memory_type=MemoryType.LONG_TERM,
        existing_memory=existing_long_term_content,
    )

    # 記憶を保存
    await self._save_memory(
        MemoryScope.WORKSPACE,
        self.WORKSPACE_SCOPE_ID,
        MemoryType.SHORT_TERM,
        short_term_content,
    )
    await self._save_memory(
        MemoryScope.WORKSPACE,
        self.WORKSPACE_SCOPE_ID,
        MemoryType.LONG_TERM,
        long_term_content,
    )
```

### スレッド記憶の生成

```python
async def generate_thread_memory(
    self,
    channel_id: str,
    thread_ts: str,
    channel_memory: ChannelMemory | None = None,
) -> None:
    """スレッドの記憶を生成・更新する"""
    # スレッドのメッセージを取得
    messages = await self._message_repository.find_by_thread(
        channel_id=channel_id,
        thread_ts=thread_ts,
    )

    if not messages:
        return

    # ChannelMessages を構築
    channel = await self._channel_repository.find_by_id(channel_id)
    channel_name = channel.name if channel else ""
    channel_messages = ChannelMessages(
        channel_id=channel_id,
        channel_name=channel_name,
        thread_messages={thread_ts: messages},
    )

    # Context を構築
    channel_memories = {}
    if channel_memory:
        channel_memories[channel_id] = channel_memory

    context = Context(
        persona=self._persona,
        conversation_history=channel_messages,
        target_thread_ts=thread_ts,
        channel_memories=channel_memories,
    )

    # 短期記憶を生成
    content = await self._memory_summarizer.summarize(
        context=context,
        scope=MemoryScope.THREAD,
        memory_type=MemoryType.SHORT_TERM,
    )

    if content:
        scope_id = make_thread_scope_id(channel_id, thread_ts)
        await self._save_memory(
            MemoryScope.THREAD,
            scope_id,
            MemoryType.SHORT_TERM,
            content,
        )
```

### ChannelMessages の構築

```python
def _build_channel_messages(
    self,
    channel_id: str,
    channel_name: str,
    messages: list[Message],
) -> ChannelMessages:
    """メッセージリストから ChannelMessages を構築する"""
    top_level: list[Message] = []
    threads: dict[str, list[Message]] = {}

    for msg in messages:
        if msg.thread_ts:
            if msg.thread_ts not in threads:
                threads[msg.thread_ts] = []
            threads[msg.thread_ts].append(msg)
        else:
            top_level.append(msg)

    return ChannelMessages(
        channel_id=channel_id,
        channel_name=channel_name,
        top_level_messages=top_level,
        thread_messages=threads,
    )
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
        limit=1000,
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

### 処理順序と依存関係

新しい仕様では、記憶生成に依存関係がある：

1. **チャンネル長期記憶**は**チャンネル短期記憶**に依存
2. **ワークスペース短期記憶**は**チャンネル短期記憶**に依存
3. **ワークスペース長期記憶**は**チャンネル長期記憶**に依存

そのため、処理順序は：
チャンネル短期 → チャンネル長期 → ワークスペース短期 → ワークスペース長期 → スレッド

### Context 構築パターン

| スコープ | memory_type | conversation_history | channel_memories | target_thread_ts |
|---------|-------------|---------------------|------------------|------------------|
| CHANNEL | SHORT_TERM | メッセージをセット | 空 | なし |
| CHANNEL | LONG_TERM | 空 | 短期記憶をセット | なし |
| WORKSPACE | SHORT_TERM | 空 | 各チャンネルの記憶をセット | なし |
| WORKSPACE | LONG_TERM | 空 | 各チャンネルの記憶をセット | なし |
| THREAD | SHORT_TERM | スレッドメッセージをセット | チャンネル記憶をセット | thread_ts |

### エラーハンドリング

- 個別のチャンネル/スレッドでエラーが発生しても他は継続
- エラーはログに記録
- 致命的なエラー（DB 接続エラー等）は例外を送出

### パフォーマンス

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

### generate_channel_memories

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規生成 | 既存記憶なし、メッセージあり | 短期・長期記憶が生成される |
| 更新 | 既存記憶あり、新メッセージあり | 記憶が更新される |
| メッセージなし | メッセージが空 | 既存記憶を維持 |
| Context 構築 | 短期記憶生成 | conversation_history にメッセージがセットされる |
| Context 構築 | 長期記憶生成 | channel_memories に短期記憶がセットされる |

### generate_workspace_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 新規生成 | 既存記憶なし | 短期・長期記憶が生成される |
| 更新 | 既存記憶あり | 記憶が更新される |
| Context 構築 | 短期記憶生成 | channel_memories に短期記憶がセットされる |
| Context 構築 | 長期記憶生成 | channel_memories に長期記憶がセットされる |

### generate_thread_memory

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 正常生成 | スレッドにメッセージあり | 短期記憶が生成される |
| メッセージなし | スレッドにメッセージなし | 記憶は生成されない |
| Context 構築 | target_thread_ts | target_thread_ts がセットされる |
| 補助情報 | channel_memory あり | channel_memories にセットされる |

---

## 完了基準

- [x] GenerateMemoryUseCase が実装されている
- [x] execute() で全記憶が正しい順序で生成される
- [x] generate_channel_memories() でチャンネル記憶が生成される
  - [x] 短期記憶: メッセージから Context を構築
  - [x] 長期記憶: 短期記憶を channel_memories にセット
- [x] generate_workspace_memory() でワークスペース記憶が生成される
  - [x] 短期記憶: チャンネル短期記憶を統合
  - [x] 長期記憶: チャンネル長期記憶を統合
- [x] generate_thread_memory() でスレッド記憶が生成される
  - [x] target_thread_ts が正しくセットされる
- [x] Context 構築が正しく行われている
- [x] エラーハンドリングが実装されている
- [x] `__init__.py` でエクスポートされている
- [x] 全テストケースが通過する
