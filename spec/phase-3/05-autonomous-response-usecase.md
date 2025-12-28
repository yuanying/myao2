# 05: 自律応答ユースケース

## 目的

チャンネル監視結果と応答判定を組み合わせ、
自律的に応答を生成・送信するユースケースを実装する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/use_cases/autonomous_response.py` | AutonomousResponseUseCase |
| `tests/application/use_cases/test_autonomous_response.py` | テスト |

---

## 依存関係

- タスク 02（ChannelMonitor）
- タスク 03（ResponseJudgment）
- タスク 04（拡張 Context）
- 既存: MessagingService, ResponseGenerator, MessageRepository

---

## インターフェース設計

### AutonomousResponseUseCase

```python
class AutonomousResponseUseCase:
    """自律応答ユースケース

    チャンネルの未応答メッセージを検出し、
    応答判定を行い、必要に応じて応答を生成・送信する。
    """

    def __init__(
        self,
        channel_monitor: ChannelMonitor,
        response_judgment: ResponseJudgment,
        response_generator: ResponseGenerator,
        messaging_service: MessagingService,
        message_repository: MessageRepository,
        conversation_history_service: ConversationHistoryService,
        config: Config,
    ) -> None:
        ...

    async def execute(self) -> None:
        """自律応答を実行する

        1. 全チャンネルの未応答メッセージを取得
        2. 各メッセージに対して応答判定
        3. 応答すべき場合、コンテキストを構築して応答生成
        4. メッセージ送信・保存
        """
        ...

    async def check_channel(self, channel: Channel) -> None:
        """特定チャンネルをチェックする

        Args:
            channel: チェック対象のチャンネル
        """
        ...
```

---

## 処理フロー

```
[execute]
    │
    ├─> 全チャンネル取得（channel_monitor.get_channels）
    │
    ├─> 各チャンネルについて:
    │   │
    │   └─> [check_channel]
    │       │
    │       ├─> 未応答メッセージ取得
    │       │   （channel_monitor.get_unreplied_messages）
    │       │
    │       ├─> 各メッセージについて:
    │       │   │
    │       │   ├─> 会話履歴取得
    │       │   │
    │       │   ├─> 応答判定（response_judgment.judge）
    │       │   │
    │       │   ├─> 判定結果ログ出力
    │       │   │
    │       │   └─> 応答すべき場合:
    │       │       │
    │       │       ├─> 補助コンテキスト構築
    │       │       │
    │       │       ├─> Context 生成
    │       │       │
    │       │       ├─> 応答生成（response_generator.generate）
    │       │       │
    │       │       ├─> メッセージ送信（messaging_service.send_message）
    │       │       │
    │       │       └─> 履歴保存（message_repository.save）
    │       │
    │       └─> 完了
    │
    └─> 完了
```

---

## 補助コンテキストの構築

### 概要

応答対象のチャンネル/スレッド以外のメッセージを補助コンテキストとして構築する。

### 構築ロジック

1. 全チャンネルから最近のメッセージを取得
2. 応答対象チャンネルのメッセージを除外
3. チャンネルごとにフォーマット
4. 文字列として連結

---

## ReplyToMentionUseCase との責務分離

| 観点 | ReplyToMentionUseCase | AutonomousResponseUseCase |
|------|----------------------|---------------------------|
| トリガー | メンションイベント | 定期チェック |
| 判定 | 不要（常に応答） | LLM による判定が必要 |
| タイミング | 即座 | 待機時間考慮 |
| 補助コンテキスト | なし（オプション） | あり |

---

## テストケース

### execute

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 未応答メッセージあり・応答判定True | 正常系 | 応答が送信される |
| 未応答メッセージあり・応答判定False | 判定で却下 | 応答は送信されない |
| 未応答メッセージなし | 全て応答済み | 何もしない |
| チャンネルなし | ボット未参加 | 何もしない |

### check_channel

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 複数メッセージ | 2件の未応答 | それぞれ判定される |
| エラー発生 | LLM エラー | ログ出力、次のメッセージへ |

---

## 設計上の考慮事項

### 並行処理

- チャンネルごとの処理は順次実行（API レート制限考慮）
- 将来的に並行化も検討可能

### エラーハンドリング

- 個別メッセージのエラーは他のメッセージに影響しない
- チャンネル単位でのエラーは次のチャンネルへ継続

### ログ出力

- 判定結果（should_respond, reason）をログ出力
- 応答送信時もログ出力

---

## 完了基準

- [x] AutonomousResponseUseCase が定義されている
- [x] 未応答メッセージに対して応答判定が実行される
- [x] 応答すべき場合のみメッセージが送信される
- [x] 補助コンテキストが Context に含まれる
- [x] 送信したメッセージが保存される
- [x] 全テストケースが通過する
