# 09: エントリポイント統合

## 目的

`__main__.py` を修正し、記憶システムを統合する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/__main__.py` | 記憶システム初期化・起動（修正） |
| `src/myao2/application/use_cases/autonomous_response.py` | MemoryRepository 依存追加（修正） |
| `src/myao2/application/use_cases/reply_to_mention.py` | MemoryRepository 依存追加（修正） |

---

## 依存関係

- タスク 07（BackgroundMemoryGenerator）に依存
- タスク 08（ResponseGenerator への記憶組み込み）に依存

---

## 変更内容

### __main__.py の変更

#### 1. 記憶関連コンポーネントの初期化

```python
from myao2.application.services.background_memory import BackgroundMemoryGenerator
from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.domain.services.memory_summarizer import MemorySummarizer
from myao2.infrastructure.llm.memory_summarizer import LLMMemorySummarizer
from myao2.infrastructure.persistence.memory_repository import SQLiteMemoryRepository


async def main() -> None:
    # ... 既存の初期化 ...

    # Memory Repository
    memory_repository = SQLiteMemoryRepository(db_manager.get_session)

    # Memory Summarizer 用の LLM クライアント
    memory_llm_config = config.llm.get(
        config.memory.memory_generation_llm,
        config.llm["default"],
    )
    memory_llm_client = LLMClient(memory_llm_config)
    memory_summarizer = LLMMemorySummarizer(
        client=memory_llm_client,
        config=config.memory,
    )

    # GenerateMemoryUseCase
    generate_memory_use_case = GenerateMemoryUseCase(
        memory_repository=memory_repository,
        message_repository=message_repository,
        channel_repository=channel_repository,
        memory_summarizer=memory_summarizer,
        config=config.memory,
        persona=config.persona,
    )

    # BackgroundMemoryGenerator
    background_memory_generator = BackgroundMemoryGenerator(
        generate_memory_use_case=generate_memory_use_case,
        config=config.memory,
    )
```

#### 2. ユースケースへの MemoryRepository 注入

```python
    # AutonomousResponseUseCase（修正）
    autonomous_response_use_case = AutonomousResponseUseCase(
        channel_monitor=channel_monitor,
        response_judgment=response_judgment,
        response_generator=response_generator,
        messaging_service=messaging_service,
        message_repository=message_repository,
        judgment_cache_repository=judgment_cache_repository,
        conversation_history_service=conversation_history_service,
        channel_sync_service=channel_sync_service,
        memory_repository=memory_repository,  # 追加
        config=config.response,
        persona=config.persona,
        bot_user_id=bot_user_id,
    )

    # ReplyToMentionUseCase（修正）
    reply_to_mention_use_case = ReplyToMentionUseCase(
        response_generator=response_generator,
        messaging_service=messaging_service,
        conversation_history_service=conversation_history_service,
        memory_repository=memory_repository,  # 追加
        persona=config.persona,
    )
```

#### 3. バックグラウンドタスクへの追加

```python
    # バックグラウンドタスクの作成
    checker_task = asyncio.create_task(periodic_checker.start())
    memory_task = asyncio.create_task(background_memory_generator.start())

    # グレースフルシャットダウン
    async def shutdown():
        logger.info("Shutting down...")
        await periodic_checker.stop()
        await background_memory_generator.stop()
        checker_task.cancel()
        memory_task.cancel()
        try:
            await checker_task
        except asyncio.CancelledError:
            pass
        try:
            await memory_task
        except asyncio.CancelledError:
            pass

    # ... シグナルハンドラの設定 ...

    try:
        await asyncio.gather(
            socket_handler.start_async(),
            checker_task,
            memory_task,
        )
    except asyncio.CancelledError:
        pass
    finally:
        await shutdown()
```

---

## AutonomousResponseUseCase の変更

### コンストラクタへの追加

```python
from myao2.domain.repositories.memory_repository import MemoryRepository


class AutonomousResponseUseCase:
    def __init__(
        self,
        channel_monitor: ChannelMonitor,
        response_judgment: ResponseJudgment,
        response_generator: ResponseGenerator,
        messaging_service: MessagingService,
        message_repository: MessageRepository,
        judgment_cache_repository: JudgmentCacheRepository,
        conversation_history_service: ConversationHistoryService,
        channel_sync_service: ChannelSyncService,
        memory_repository: MemoryRepository,  # 追加
        config: ResponseConfig,
        persona: PersonaConfig,
        bot_user_id: str,
    ) -> None:
        # ... 既存のフィールド ...
        self._memory_repository = memory_repository
```

### Context 構築時の記憶取得

```python
    async def _build_context(
        self,
        channel_id: str,
        thread_ts: str | None,
        conversation_history: list[Message],
        other_channel_messages: dict[str, list[Message]],
    ) -> Context:
        """記憶を含む Context を構築する"""
        # 記憶を取得
        ws_long_term = await self._memory_repository.find_by_scope_and_type(
            MemoryScope.WORKSPACE,
            GenerateMemoryUseCase.WORKSPACE_SCOPE_ID,
            MemoryType.LONG_TERM,
        )
        # ... 他の記憶も取得 ...

        return Context(
            persona=self._persona,
            conversation_history=conversation_history,
            other_channel_messages=other_channel_messages,
            workspace_long_term_memory=ws_long_term.content if ws_long_term else None,
            # ... 他の記憶も設定 ...
        )
```

---

## ReplyToMentionUseCase の変更

### コンストラクタへの追加

```python
class ReplyToMentionUseCase:
    def __init__(
        self,
        response_generator: ResponseGenerator,
        messaging_service: MessagingService,
        conversation_history_service: ConversationHistoryService,
        memory_repository: MemoryRepository,  # 追加
        persona: PersonaConfig,
    ) -> None:
        # ... 既存のフィールド ...
        self._memory_repository = memory_repository
```

### execute での記憶取得

```python
    async def execute(self, message: Message) -> None:
        # ... 会話履歴取得 ...

        # 記憶を取得
        context = await self._build_context_with_memory(
            channel_id=message.channel.id,
            thread_ts=message.thread_ts,
            conversation_history=conversation_history,
        )

        # ... 応答生成 ...
```

---

## 起動シーケンス

```
1. 設定ファイル読み込み
2. データベース初期化
3. リポジトリ初期化（MessageRepository, ChannelRepository, MemoryRepository）
4. LLM クライアント初期化（応答用、判定用、記憶生成用）
5. サービス初期化（ChannelMonitor, ResponseJudgment, MemorySummarizer）
6. ユースケース初期化（AutonomousResponse, ReplyToMention, GenerateMemory）
7. バックグラウンドサービス初期化（PeriodicChecker, BackgroundMemoryGenerator）
8. Slack ハンドラ初期化
9. 並行タスク起動:
   - Socket Mode ハンドラ
   - PeriodicChecker
   - BackgroundMemoryGenerator
10. シャットダウン時に各サービスを停止
```

---

## 設計上の考慮事項

### 依存関係の注入

- 全ての依存関係は `__main__.py` で構築
- ユースケースは Protocol に依存（具象クラスに依存しない）

### エラーハンドリング

- 記憶リポジトリ初期化失敗時はアプリケーション起動を中断
- バックグラウンドタスクのエラーは個別に処理

### グレースフルシャットダウン

- シグナル（SIGINT, SIGTERM）でシャットダウンを開始
- 各バックグラウンドサービスに停止を通知
- タスクの完了を待機

---

## テストケース

### 統合テスト

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 起動 | アプリケーション起動 | 全コンポーネントが初期化される |
| シャットダウン | SIGINT 送信 | グレースフルにシャットダウン |

### ユースケース

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 記憶ありの応答 | 記憶が存在する状態で応答 | 記憶が Context に含まれる |
| 記憶なしの応答 | 記憶が存在しない状態で応答 | エラーなく応答生成 |

---

## 完了基準

- [ ] MemoryRepository が初期化されている
- [ ] MemorySummarizer が初期化されている
- [ ] GenerateMemoryUseCase が初期化されている
- [ ] BackgroundMemoryGenerator が初期化されている
- [ ] AutonomousResponseUseCase に MemoryRepository が注入されている
- [ ] ReplyToMentionUseCase に MemoryRepository が注入されている
- [ ] BackgroundMemoryGenerator がバックグラウンドタスクとして起動される
- [ ] グレースフルシャットダウンが正しく動作する
- [ ] 全テストケースが通過する
