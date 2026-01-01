# extra04: ResponseJudgment#judge インターフェース簡素化

## 目的

ResponseJudgment#judge の引数を簡素化し、Context のみで判定を行えるようにする。
同時に、ChannelMonitor の未応答取得をメッセージ単位からスレッド単位に変更する。

---

## 背景

### 現状の問題点

1. **ResponseJudgment#judge** - `context` と `message` の両方を渡しているが、
   `context.target_thread_ts` に判定対象が含まれているため冗長
2. **get_unreplied_messages** - メッセージ単位で取得するが、実際の判定・応答はスレッド単位で行う
3. **AutonomousResponseUseCase** - 未応答メッセージごとにコンテキストを構築するが、
   同一スレッド内のメッセージは重複処理される可能性がある

### 解決方針

- `judge(context)` のみで判定可能にし、対象スレッドは `context.target_thread_ts` から取得
- 未応答「スレッド」単位で処理することで、効率的な判定・応答を実現

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/services/response_judgment.py` | Protocol 引数変更 |
| `src/myao2/domain/services/channel_monitor.py` | メソッド名・戻り値変更 |
| `src/myao2/infrastructure/llm/response_judgment.py` | 実装変更 |
| `src/myao2/infrastructure/persistence/channel_monitor.py` | 実装変更 |
| `src/myao2/infrastructure/slack/channel_monitor.py` | 実装変更 |
| `src/myao2/application/use_cases/autonomous_response.py` | 呼び出し変更 |
| `tests/infrastructure/llm/test_response_judgment.py` | テスト更新 |
| `tests/infrastructure/persistence/test_channel_monitor.py` | テスト更新 |
| `tests/application/use_cases/test_autonomous_response.py` | テスト更新 |

---

## インターフェース設計

### ResponseJudgment Protocol（変更後）

```python
class ResponseJudgment(Protocol):
    async def judge(
        self,
        context: Context,
    ) -> JudgmentResult:
        """Determine whether to respond.

        判定対象のスレッドは context.target_thread_ts から取得。
        target_thread_ts が None の場合はトップレベルメッセージとして判定。
        """
        ...
```

### ChannelMonitor Protocol（変更後）

```python
async def get_unreplied_threads(
    self,
    channel_id: str,
    min_wait_seconds: int,
    max_message_age_seconds: int | None = None,
) -> list[str | None]:
    """未応答スレッドのタイムスタンプリストを取得する

    指定時間以上経過し、かつボットが応答していないスレッドを取得する。

    Returns:
        list[str | None]: 未応答スレッドの thread_ts リスト
                          - スレッド内: 親メッセージの thread_ts
                          - トップレベル: None
    """
```

---

## 処理フロー

### 変更前

```
AutonomousResponseUseCase.check_channel():
1. get_unreplied_messages() → list[Message]
2. for message in messages:
   3. build_context_with_memory(message)
   4. judge(context, message)
   5. if should_respond: generate and send
```

### 変更後

```
AutonomousResponseUseCase.check_channel():
1. get_unreplied_threads() → list[str | None] (thread_ts list)
2. for thread_ts in threads:
   3. build_context_with_memory(thread_ts)  # thread_ts は None の可能性あり
   4. judge(context)  # context.target_thread_ts から対象を取得
   5. if should_respond: generate and send
```

**備考:**
- `thread_ts = None` の場合、トップレベルのメッセージとして処理
- `context.target_thread_ts` に `None` または `thread_ts` が設定される
- トップレベルメッセージが複数未応答でも `None` は1つのみ返す（最新の1つに応答）
- リストには重複する thread_ts は含まれない

---

## テストケース

### ResponseJudgment

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| judge | context.target_thread_ts が設定済み | 対象スレッドで判定実行 |
| judge | context.target_thread_ts が None | トップレベルとして判定 |

### ChannelMonitor

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| get_unreplied_threads | 未応答スレッドあり | thread_ts リストが返る |
| get_unreplied_threads | 未応答トップレベルあり | None が含まれる |
| get_unreplied_threads | 全スレッド応答済み | 空リストが返る |
| get_unreplied_threads | 同一スレッド内に複数未応答 | 重複なしで1つのみ返る |
| get_unreplied_threads | スレッドとトップレベル混在 | [thread_ts, None, ...] のように混在 |

---

## 完了基準

- [x] ResponseJudgment Protocol の引数が context のみになっている
- [x] ChannelMonitor に get_unreplied_threads が実装されている
- [x] get_unreplied_messages は削除または非推奨になっている
- [x] LLMResponseJudgment が新インターフェースを実装している
- [x] DBChannelMonitor/SlackChannelMonitor が get_unreplied_threads を実装している
- [x] AutonomousResponseUseCase が新インターフェースを使用している
- [x] 全テストが通過する
