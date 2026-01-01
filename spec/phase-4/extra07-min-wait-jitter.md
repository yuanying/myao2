# extra07: min_wait_seconds への jitter 追加

## 目的

自律応答の待機時間にランダムなばらつき（jitter）を追加し、
より人間らしい応答タイミングを実現する。

---

## 背景

### 現状

- `min_wait_seconds` は固定値（デフォルト: 300秒 = 5分）
- 毎回同じ待機時間で判定されるため、機械的な印象を与える

### 問題点

1. 待機時間が常に一定で人間らしくない
2. 複数の未応答スレッドを同時に処理する際、全て同じタイミングになる

### 解決方針

- `ResponseConfig` に `jitter_ratio` を追加（デフォルト: 0.2 = ±20%）
- 実際の待機時間を `min_wait_seconds * (1 ± jitter_ratio)` の範囲でランダム化

---

## 実装するファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/config/models.py` | ResponseConfig に jitter_ratio 追加 |
| `src/myao2/config/loader.py` | jitter_ratio 読み込み |
| `src/myao2/application/use_cases/autonomous_response.py` | jitter 適用 |
| `config.yaml.example` | jitter_ratio 設定例追加 |
| `tests/config/test_loader.py` | jitter_ratio テスト追加 |
| `tests/application/use_cases/test_autonomous_response.py` | jitter テスト追加 |

---

## 設計

### ResponseConfig の変更

```python
@dataclass
class ResponseConfig:
    """自律応答設定"""
    check_interval_seconds: int = 60
    min_wait_seconds: int = 300
    jitter_ratio: float = 0.2  # 追加: ±20%のばらつき
    message_limit: int = 20
    max_message_age_seconds: int = 43200
    channel_messages_limit: int = 50
    active_channel_days: int = 7
    thread_memory_days: int = 7
    judgment_skip: JudgmentSkipConfig | None = None
```

### jitter 計算ロジック

```python
import random

def calculate_wait_with_jitter(
    min_wait_seconds: int,
    jitter_ratio: float,
) -> int:
    """jitter を適用した待機時間を計算する

    Args:
        min_wait_seconds: 基準の最小待機時間（秒）
        jitter_ratio: ばらつきの割合（0.0-1.0）

    Returns:
        jitter 適用後の待機時間（秒）

    Example:
        min_wait_seconds=300, jitter_ratio=0.2 の場合
        → 240〜360 秒の範囲でランダムに決定
    """
    if jitter_ratio <= 0:
        return min_wait_seconds

    jitter = min_wait_seconds * jitter_ratio
    min_time = int(min_wait_seconds - jitter)
    max_time = int(min_wait_seconds + jitter)
    return random.randint(min_time, max_time)
```

### 使用箇所

```python
# AutonomousResponseUseCase.check_channel()
wait_seconds = calculate_wait_with_jitter(
    config.response.min_wait_seconds,
    config.response.jitter_ratio,
)
unreplied_threads = await self._channel_monitor.get_unreplied_threads(
    channel_id,
    min_wait_seconds=wait_seconds,  # jitter 適用済みの値を渡す
    max_message_age_seconds=config.response.max_message_age_seconds,
)
```

---

## 設定例

```yaml
response:
  check_interval_seconds: 60
  min_wait_seconds: 300
  jitter_ratio: 0.2  # ±20%（240〜360秒）
  # jitter_ratio: 0.0  # jitter 無効（常に300秒）
  # jitter_ratio: 0.5  # ±50%（150〜450秒）
```

---

## テストケース

### ResponseConfig

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| load | jitter_ratio 設定あり | 値が正しく読み込まれる |
| load | jitter_ratio 設定なし | デフォルト値 0.2 が使用される |
| validation | jitter_ratio < 0 | 0.0 として扱う |
| validation | jitter_ratio > 1.0 | 1.0 として扱う |

### calculate_wait_with_jitter

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| calculate | jitter_ratio=0.2 | min〜max の範囲内の値 |
| calculate | jitter_ratio=0.0 | min_wait_seconds と同じ値 |
| calculate | 複数回呼び出し | 異なる値が返る（確率的） |

### AutonomousResponseUseCase

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| check_channel | jitter 有効 | jitter 適用後の値で呼び出される |

---

## 設計上の考慮事項

### jitter のタイミング

- check_channel() 呼び出し時に毎回 jitter を計算
- 同一チャンネル内でも呼び出しごとに異なる待機時間

### jitter_ratio の範囲

- `0.0`: jitter 無効（常に固定値）
- `0.2`: ±20%（推奨デフォルト）
- `1.0`: ±100%（最大ばらつき、0〜2倍）

### 負の値への対応

- jitter_ratio が負の場合は 0.0 として扱う
- min_time が負になる場合は 0 に丸める

---

## 完了基準

- [ ] ResponseConfig に jitter_ratio が追加されている
- [ ] config.yaml.example に jitter_ratio の設定例がある
- [ ] calculate_wait_with_jitter 関数が実装されている
- [ ] AutonomousResponseUseCase が jitter を適用している
- [ ] 全テストが通過する
