# 02: 動的待機時間 - 実装手順書

**Status**: [ ] Not Started

## 目標

活発なチャンネルでは応答までの待機時間を自動的に短くし、より自然なタイミングで応答できるようにする。

## 成果物

チャンネルの活発度に基づいて待機時間を動的に調整するシステム

- ActivityCalculator サービス: チャンネルの活発度を計測
- 設定可能な閾値: 活発度に応じた待機時間係数
- AutonomousResponseUseCase への統合

---

## 決定事項サマリー

| 項目 | 決定内容 |
|------|---------|
| 活発度スコア | messages/分（直近N分間のメッセージ数 / N）|
| 測定ウィンドウ | 30分（設定可能）|
| 対象メッセージ | ボットのメッセージを除外 |
| 待機時間下限 | 60秒（spam防止、設定可能）|
| 閾値設定 | 設定ファイルでカスタマイズ可能 |
| 後方互換性 | 機能無効時は既存動作を維持 |

---

## 活発度スコアの計算

### 計算式

```
activity_score = messages_count / measurement_window_minutes
```

例: 過去30分間に15件のメッセージがある場合
```
activity_score = 15 / 30 = 0.5 (1分あたり0.5件)
```

### 活発度レベルと待機時間係数（デフォルト）

| レベル | messages/分 | 係数 | 300秒 → |
|--------|-------------|------|---------|
| 非常に活発 | >= 1.0 | 0.2 | 60秒 |
| 活発 | >= 0.5 | 0.4 | 120秒 |
| 普通 | >= 0.1 | 0.7 | 210秒 |
| 静か | < 0.1 | 1.0 | 300秒 |

### 待機時間計算フロー

```
1. チャンネルの活発度スコアを計算
2. 閾値リストを高い順に評価し、該当する係数を取得
3. base_min_wait_seconds × 係数 = 調整後待機時間
4. floor_wait_seconds との max を取る
5. jitter_ratio を適用して最終待機時間を決定
```

---

## タスク一覧

| # | タスク | 依存 | Status |
|---|--------|------|--------|
| 02a | 設定モデル追加（ActivityThreshold, DynamicWaitConfig）| - | [ ] |
| 02b | ActivityCalculator サービス作成 | 02a | [ ] |
| 02c | AutonomousResponseUseCase 統合 | 02b | [ ] |
| 02d | DI初期化更新（__main__.py）| 02c | [ ] |

---

## 実装順序（DAG図）

```
[02a] 設定モデル追加
          │
          ↓
[02b] ActivityCalculator サービス作成
          │
          ↓
[02c] AutonomousResponseUseCase 統合
          │
          ↓
[02d] DI初期化更新
```

---

## 設定仕様

### config.yaml への追加

```yaml
response:
  # 既存設定
  check_interval_seconds: 60
  min_wait_seconds: 300
  jitter_ratio: 0.3

  # 新規追加: 動的待機時間設定
  dynamic_wait:
    enabled: true                        # 動的待機時間の有効/無効
    measurement_window_minutes: 30       # 活発度測定の時間窓（分）
    floor_wait_seconds: 60               # 待機時間の下限（spam防止）
    # 活発度閾値（高い順に評価）
    thresholds:
      - min_score: 1.0                   # 1分あたり1件以上
        wait_multiplier: 0.2             # 待機時間を20%に
      - min_score: 0.5                   # 1分あたり0.5件以上
        wait_multiplier: 0.4             # 待機時間を40%に
      - min_score: 0.1                   # 1分あたり0.1件以上
        wait_multiplier: 0.7             # 待機時間を70%に
    # デフォルト（どの閾値にも該当しない場合）
    default_multiplier: 1.0              # 待機時間を100%（そのまま）
```

### 設定モデル

```python
@dataclass
class ActivityThreshold:
    """活発度閾値設定"""
    min_score: float       # 最小活発度スコア（messages/分）
    wait_multiplier: float # 待機時間係数（0.0-1.0）


@dataclass
class DynamicWaitConfig:
    """動的待機時間設定"""
    enabled: bool = True
    measurement_window_minutes: int = 30
    floor_wait_seconds: int = 60
    thresholds: list[ActivityThreshold] = field(default_factory=list)
    default_multiplier: float = 1.0
```

---

## ActivityCalculator サービス仕様

### インターフェース

```python
class ActivityCalculator:
    """チャンネル活発度計算サービス"""

    def __init__(
        self,
        message_repository: MessageRepository,
        config: DynamicWaitConfig,
        bot_user_id: str,
    ) -> None: ...

    async def calculate_activity_score(self, channel_id: str) -> float:
        """チャンネルの活発度スコアを計算する

        Args:
            channel_id: チャンネルID

        Returns:
            活発度スコア（messages/分）
        """

    def calculate_wait_seconds(
        self,
        activity_score: float,
        base_wait_seconds: int,
    ) -> int:
        """活発度に基づいて待機時間を計算する

        Args:
            activity_score: 活発度スコア
            base_wait_seconds: 基準待機時間

        Returns:
            調整後の待機時間（秒）
        """
```

### 活発度スコア計算ロジック

1. 現在時刻から `measurement_window_minutes` 分前を計算
2. `MessageRepository.find_all_in_channel()` で該当期間のメッセージを取得
   - `min_timestamp`: 測定開始時刻
   - `exclude_bot_user_id`: ボットのメッセージを除外
3. メッセージ数 / 測定ウィンドウ分数 = 活発度スコア

### 待機時間計算ロジック

1. 閾値リストを `min_score` の降順でソート
2. `activity_score >= threshold.min_score` を満たす最初の閾値を採用
3. 該当なしの場合は `default_multiplier` を使用
4. `base_wait_seconds × multiplier` を計算
5. `floor_wait_seconds` との max を返す

---

## AutonomousResponseUseCase への統合

### コンストラクタ変更

```python
def __init__(
    self,
    # ... 既存パラメータ ...
    activity_calculator: ActivityCalculator | None = None,  # 追加
) -> None:
```

### check_channel メソッド変更

```python
async def check_channel(self, channel: Channel) -> None:
    base_wait = self._config.response.min_wait_seconds

    # 動的待機時間の計算
    if self._activity_calculator is not None:
        activity_score = await self._activity_calculator.calculate_activity_score(
            channel.id
        )
        adjusted_wait = self._activity_calculator.calculate_wait_seconds(
            activity_score, base_wait
        )
        logger.debug(
            "Channel %s: activity_score=%.2f, adjusted_wait=%d (from %d)",
            channel.id,
            activity_score,
            adjusted_wait,
            base_wait,
        )
    else:
        adjusted_wait = base_wait

    # jitter 適用
    wait_seconds = calculate_wait_with_jitter(
        adjusted_wait,
        self._config.response.jitter_ratio,
    )
    # ... 以下既存のロジック ...
```

---

## 影響を受けるファイル

### 新規作成

| ファイル | 説明 |
|---------|------|
| `src/myao2/application/services/activity_calculator.py` | ActivityCalculator サービス |
| `tests/application/services/test_activity_calculator.py` | ユニットテスト |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | ActivityThreshold, DynamicWaitConfig 追加 |
| `config.yaml.example` | dynamic_wait セクション追加 |
| `src/myao2/application/use_cases/autonomous_response.py` | 動的待機時間ロジック統合 |
| `src/myao2/__main__.py` | ActivityCalculator の初期化・注入 |
| `tests/application/use_cases/test_autonomous_response.py` | 動的待機時間関連テスト追加 |

---

## テスト方針

### ActivityCalculator ユニットテスト

| テストケース | 説明 |
|-------------|------|
| test_calculate_activity_score_no_messages | メッセージがない場合は 0 を返す |
| test_calculate_activity_score_with_messages | メッセージ数に基づいてスコアを計算 |
| test_calculate_activity_score_excludes_bot | ボットのメッセージは除外される |
| test_calculate_wait_seconds_very_active | 非常に活発な場合は待機時間が短くなる |
| test_calculate_wait_seconds_quiet | 静かな場合は待機時間がそのまま |
| test_calculate_wait_seconds_respects_floor | 下限を下回らない |

### AutonomousResponseUseCase 統合テスト

| テストケース | 説明 |
|-------------|------|
| test_uses_dynamic_wait_when_enabled | ActivityCalculator がある場合は動的計算を使用 |
| test_falls_back_to_static_when_disabled | ActivityCalculator が None の場合は既存動作 |

---

## 手動検証

1. config.yaml に `dynamic_wait` セクションを追加
2. アプリケーション起動
3. 活発なチャンネル（30分間に15件以上のメッセージ）でテスト
4. ログで `activity_score` と `adjusted_wait` を確認
5. 静かなチャンネルでは待機時間が長いことを確認
