# extra02: 応答判定スキップ機能

## 目的

LLM への応答判定リクエストを削減するため、JudgmentResult の confidence 値に基づいて次回の応答判定をスキップする機能を追加する。

---

## 背景

### 現状の問題点

1. **毎回の LLM 判定**: `AutonomousResponseUseCase` は `check_channel()` で全ての未応答メッセージに対して毎回 LLM 判定を実行
2. **confidence 未活用**: `JudgmentResult.confidence` フィールドは存在するが、常に 1.0 で LLM から取得していない
3. **コスト・レート制限**: 頻繁な LLM API 呼び出しはコスト増加と API レート制限のリスク

### 解決策

- LLM から confidence 値を取得
- confidence の値に応じて次回判定日時を決定
- 次回判定日時まではそのスコープ（スレッド/トップレベル単位）の判定をスキップ

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/config/models.py` | JudgmentSkipConfig 追加 |
| `src/myao2/domain/entities/judgment_cache.py` | JudgmentCache エンティティ |
| `src/myao2/domain/repositories/judgment_cache_repository.py` | JudgmentCacheRepository Protocol |
| `src/myao2/infrastructure/persistence/models.py` | JudgmentCacheModel 追加 |
| `src/myao2/infrastructure/persistence/judgment_cache_repository.py` | SQLiteJudgmentCacheRepository |
| `src/myao2/infrastructure/llm/response_judgment.py` | confidence 取得対応 |
| `src/myao2/application/use_cases/autonomous_response.py` | スキップ判定・キャッシュ更新 |
| `tests/domain/entities/test_judgment_cache.py` | JudgmentCache テスト |
| `tests/infrastructure/persistence/test_judgment_cache_repository.py` | リポジトリテスト |
| `tests/infrastructure/llm/test_response_judgment.py` | confidence 取得テスト追加 |
| `tests/application/use_cases/test_autonomous_response.py` | スキップ判定テスト追加 |

---

## 依存関係

- タスク phase-3/03（ResponseJudgment）
- タスク phase-3/05（AutonomousResponseUseCase）
- タスク phase-3/extra01（DBChannelMonitor - スコープ識別と整合）

---

## インターフェース設計

### JudgmentSkipConfig（設定クラス）

```python
@dataclass
class JudgmentSkipThreshold:
    """判定スキップ閾値設定

    Attributes:
        min_confidence: 最小 confidence（この値以上で適用）
        skip_seconds: スキップする秒数
    """
    min_confidence: float
    skip_seconds: int


@dataclass
class JudgmentSkipConfig:
    """応答判定スキップ設定

    Attributes:
        enabled: スキップ機能有効/無効
        thresholds: confidence 閾値リスト（高い順にソート推奨）
        default_skip_seconds: どの閾値にも該当しない場合のスキップ秒数
    """
    enabled: bool = True
    thresholds: list[JudgmentSkipThreshold] = field(default_factory=lambda: [
        JudgmentSkipThreshold(min_confidence=0.9, skip_seconds=43200),  # 12時間
        JudgmentSkipThreshold(min_confidence=0.7, skip_seconds=3600),   # 1時間
    ])
    default_skip_seconds: int = 600  # 10分
```

### JudgmentCache エンティティ

```python
@dataclass(frozen=True)
class JudgmentCache:
    """応答判定キャッシュ

    スレッド/トップレベル単位で判定結果をキャッシュし、
    次回判定日時まで再判定をスキップする。

    Attributes:
        channel_id: チャンネル ID
        thread_ts: スレッド識別子（トップレベルは None）
        should_respond: 最後の判定結果
        confidence: 判定の確信度（0.0 - 1.0）
        reason: 判定理由
        latest_message_ts: キャッシュ作成時の最新メッセージのタイムスタンプ
        next_check_at: 次回判定日時（この時刻以降に再判定）
        created_at: 作成日時
        updated_at: 更新日時
    """
    channel_id: str
    thread_ts: str | None
    should_respond: bool
    confidence: float
    reason: str
    latest_message_ts: str
    next_check_at: datetime
    created_at: datetime
    updated_at: datetime

    @property
    def scope_key(self) -> str:
        """スコープを識別するキーを返す"""
        return f"{self.channel_id}:{self.thread_ts or 'top'}"

    def is_valid(self, current_time: datetime, current_latest_message_ts: str) -> bool:
        """キャッシュが有効かどうか判定

        Args:
            current_time: 現在時刻
            current_latest_message_ts: 現在の最新メッセージのタイムスタンプ

        Returns:
            next_check_at より前かつ新しいメッセージがなければ True（スキップ可能）
        """
        if current_time >= self.next_check_at:
            return False
        # 新しいメッセージがあればキャッシュ無効
        if current_latest_message_ts != self.latest_message_ts:
            return False
        return True
```

### JudgmentCacheRepository Protocol

```python
class JudgmentCacheRepository(Protocol):
    """応答判定キャッシュリポジトリ"""

    async def save(self, cache: JudgmentCache) -> None:
        """キャッシュを保存（upsert）

        channel_id + thread_ts が同じレコードは更新する。
        """
        ...

    async def find_by_scope(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> JudgmentCache | None:
        """スコープでキャッシュを検索"""
        ...

    async def delete_expired(self, before: datetime) -> int:
        """期限切れキャッシュを削除

        next_check_at が指定時刻より前のレコードを削除。
        定期的なクリーンアップ用。
        """
        ...

    async def delete_by_scope(
        self,
        channel_id: str,
        thread_ts: str | None,
    ) -> None:
        """スコープのキャッシュを削除"""
        ...
```

---

## データモデル

### JudgmentCacheModel

```python
class JudgmentCacheModel(SQLModel, table=True):
    """応答判定キャッシュテーブル"""

    __tablename__ = "judgment_caches"

    id: int | None = Field(default=None, primary_key=True)
    channel_id: str = Field(index=True)
    thread_ts: str | None = Field(default=None, index=True)
    should_respond: bool
    confidence: float
    reason: str
    latest_message_ts: str  # キャッシュ作成時の最新メッセージのタイムスタンプ
    next_check_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("channel_id", "thread_ts", name="uq_channel_thread"),
    )
```

---

## LLM プロンプト修正

### システムプロンプト変更

```python
SYSTEM_PROMPT_TEMPLATE = """あなたは会話への参加判断を行うアシスタントです。
以下の会話を分析し、{persona_name}として応答すべきかを判断してください。

現在時刻: {current_time}

判断基準：
1. 誰も反応していないメッセージがあるか
2. 困っている/寂しそうな状況か
3. 有用なアドバイスができそうか
4. 会話に割り込むのが適切か
5. メッセージからの経過時間（長時間放置されているか）

以下の場合は応答しないでください：
- 明らかな独り言
- 活発な会話に無理に割り込む場合

必ずJSON形式で回答してください。他のテキストは含めないでください。
回答形式：
{{"should_respond": true/false, "reason": "理由", "confidence": 0.0-1.0}}

confidence について：
- 1.0: 完全に確信（状況が明確で、今後も変わる可能性が低い）
- 0.7-0.9: かなり確信（多少の不確実性はあるが、ほぼ判断可能）
- 0.4-0.6: やや不確実（状況が変わる可能性がある）
- 0.0-0.3: 非常に不確実（追加情報が必要）"""
```

### レスポンスパース修正

```python
def _parse_response(self, response: str) -> JudgmentResult:
    """LLM response を JudgmentResult に変換"""
    try:
        json_match = re.search(r"\{[^{}]*\}", response)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
        else:
            data = json.loads(response)

        should_respond = data.get("should_respond", False)
        reason = data.get("reason", "")
        confidence = data.get("confidence", 1.0)

        # confidence の範囲を正規化
        confidence = max(0.0, min(1.0, float(confidence)))

        return JudgmentResult(
            should_respond=bool(should_respond),
            reason=reason,
            confidence=confidence,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("Failed to parse LLM response: %s", e)
        return JudgmentResult(
            should_respond=False,
            reason=f"Failed to parse LLM response: {e}",
            confidence=0.0,  # パース失敗時は低い confidence
        )
```

---

## AutonomousResponseUseCase 修正

### スキップ判定メソッド

```python
async def _should_skip_judgment(self, message: Message) -> bool:
    """判定をスキップすべきかを判定

    キャッシュが有効かつ新しいメッセージがない場合のみスキップ。
    新しいメッセージがある場合は状況が変わっている可能性があるため再判定。
    """
    skip_config = self._config.response.judgment_skip
    if not skip_config.enabled:
        return False

    cache = await self._judgment_cache_repository.find_by_scope(
        channel_id=message.channel.id,
        thread_ts=message.thread_ts,
    )

    if cache is None:
        return False

    current_time = datetime.now(timezone.utc)
    # message.id が最新メッセージのタイムスタンプ
    return cache.is_valid(current_time, message.id)
```

### キャッシュ保存メソッド

```python
async def _cache_judgment_result(
    self,
    message: Message,
    result: JudgmentResult,
) -> None:
    """判定結果をキャッシュに保存"""
    skip_config = self._config.response.judgment_skip
    if not skip_config.enabled:
        return

    current_time = datetime.now(timezone.utc)
    skip_seconds = self._calculate_skip_seconds(result.confidence, skip_config)
    next_check_at = current_time + timedelta(seconds=skip_seconds)

    cache = JudgmentCache(
        channel_id=message.channel.id,
        thread_ts=message.thread_ts,
        should_respond=result.should_respond,
        confidence=result.confidence,
        reason=result.reason,
        latest_message_ts=message.id,  # キャッシュ作成時の最新メッセージ
        next_check_at=next_check_at,
        created_at=current_time,
        updated_at=current_time,
    )

    await self._judgment_cache_repository.save(cache)

def _calculate_skip_seconds(
    self,
    confidence: float,
    config: JudgmentSkipConfig,
) -> int:
    """confidence に基づいてスキップ秒数を計算"""
    sorted_thresholds = sorted(
        config.thresholds,
        key=lambda t: t.min_confidence,
        reverse=True,
    )

    for threshold in sorted_thresholds:
        if confidence >= threshold.min_confidence:
            return threshold.skip_seconds

    return config.default_skip_seconds
```

---

## config.yaml への追加

```yaml
response:
  check_interval_seconds: 60
  min_wait_seconds: 300
  message_limit: 20
  max_message_age_seconds: 43200

  # 判定スキップ設定
  judgment_skip:
    enabled: true
    thresholds:
      - min_confidence: 0.9
        skip_seconds: 43200  # 12時間
      - min_confidence: 0.7
        skip_seconds: 3600   # 1時間
    default_skip_seconds: 600  # 10分
```

---

## 処理フロー

### 通常フロー（キャッシュなし）

```
PeriodicChecker
  └─> AutonomousResponseUseCase.execute()
        └─> check_channel(channel)
              └─> get_unreplied_messages()
                    └─> _process_message(channel, message)
                          ├─> _should_skip_judgment() → False（キャッシュなし）
                          ├─> ResponseJudgment.judge() → JudgmentResult(confidence=0.85)
                          ├─> _cache_judgment_result() → DB保存（next_check_at = now + 1時間）
                          └─> (should_respond=Falseなら終了)
```

### キャッシュヒットフロー

```
PeriodicChecker
  └─> AutonomousResponseUseCase.execute()
        └─> check_channel(channel)
              └─> get_unreplied_messages()
                    └─> _process_message(channel, message)
                          └─> _should_skip_judgment() → True（next_check_at前）
                                └─> return（LLM呼び出しなし）
```

---

## テストケース

### JudgmentCache エンティティ

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| 生成 | 全フィールド指定 | 正しく生成される |
| scope_key | thread_ts あり | "channel_id:thread_ts" |
| scope_key | thread_ts なし | "channel_id:top" |
| is_valid | 現在時刻 < next_check_at かつ同一メッセージ | True |
| is_valid | 現在時刻 >= next_check_at | False |
| is_valid | 新しいメッセージあり（異なる latest_message_ts） | False |

### JudgmentCacheRepository

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| save | 新規キャッシュ | 保存される |
| save | 既存キャッシュ（同一スコープ） | 更新される |
| find_by_scope | 存在するスコープ | キャッシュが返る |
| find_by_scope | 存在しないスコープ | None が返る |
| delete_expired | 期限切れあり | 期限切れのみ削除 |

### LLMResponseJudgment（confidence 対応）

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| confidence 取得 | JSON に confidence あり | 正しく取得 |
| confidence なし | JSON に confidence なし | デフォルト 1.0 |
| confidence 範囲外 | confidence > 1.0 | 1.0 に正規化 |
| パース失敗 | 不正な JSON | confidence=0.0 |

### AutonomousResponseUseCase（スキップ判定）

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| スキップ無効 | enabled=False | 常に判定実行 |
| キャッシュなし | 初回判定 | 判定実行 + キャッシュ保存 |
| キャッシュ有効 | next_check_at 前 かつ同一メッセージ | 判定スキップ |
| キャッシュ期限切れ | next_check_at 後 | 再判定 + キャッシュ更新 |
| 新しいメッセージ | キャッシュあり + 異なるメッセージ ID | 再判定 + キャッシュ更新 |
| confidence=0.9 | 閾値0.9以上 | 12時間スキップ |
| confidence=0.8 | 閾値0.7-0.9 | 1時間スキップ |
| confidence=0.5 | 閾値未満 | 10分スキップ |

---

## 設計上の考慮事項

### コスト効率

- 高い confidence の判定結果は長時間スキップ
- 低い confidence でも最低限のスキップ時間を設定
- 判定スキップにより LLM API 呼び出し回数を大幅削減

### キャッシュ無効化タイミング

キャッシュは以下の場合に無効となる：

1. **next_check_at 経過後**: 設定された時間が経過した場合
2. **新しいメッセージがある場合**: `latest_message_ts` とメッセージの ID が異なる場合

これにより、同一スコープ（channel_id + thread_ts）で新しいメッセージが来た場合は自動的にキャッシュが無効化され、再判定が行われる。新しいメッセージは状況を変える可能性があるため、この動作は適切。

### データ整合性

- UniqueConstraint で channel_id + thread_ts の重複を防止
- 同一スコープの複数キャッシュは発生しない

### クリーンアップ

`delete_expired()` を定期的に呼び出して古いキャッシュを削除する。
`PeriodicChecker` のループ内で1日1回程度呼び出すことを推奨。

---

## 完了基準

- [x] JudgmentSkipConfig / JudgmentSkipThreshold が定義されている
- [x] JudgmentCache エンティティが定義されている
- [x] JudgmentCacheRepository Protocol が定義されている
- [x] JudgmentCacheModel が定義されている
- [x] SQLiteJudgmentCacheRepository が実装されている
- [x] LLMResponseJudgment が confidence を取得している
- [x] AutonomousResponseUseCase がスキップ判定を行っている
- [x] config.yaml に judgment_skip 設定が追加されている
- [x] 全テストケースが通過する
