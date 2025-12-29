# Extra03: Context リファクタリング

## 概要

strands-agents への将来的な移行を見据え、Context クラスを純粋なデータクラスに変更する。
会話履歴を含む全ての情報を system_prompt に含める形式に移行し、LLM の messages には system のみを渡す。

## 変更理由

1. **strands-agents 移行準備**: strands-agents では独自の messages 構築が行われるため、Context からメッセージ構築ロジックを分離
2. **シンプルな API**: Context はデータのみを保持し、プロンプト構築は利用側の責務とする
3. **メッセージ形式の統一**: 全てのメッセージ（履歴、他チャンネル）を同じ形式で system_prompt に含める

## 変更内容

### 1. Context エンティティの変更

**ファイル**: `src/myao2/domain/entities/context.py`

**変更点**:
- `build_system_prompt()` メソッド削除
- `build_messages_for_llm()` メソッド削除
- `auxiliary_context: str | None` → `other_channel_messages: dict[str, list[Message]]` に変更

### 2. メッセージフォーマットユーティリティの作成

**ファイル**: `src/myao2/domain/services/message_formatter.py` (新規)

以下の関数を提供:
- `format_message_with_metadata()`: メッセージを投稿時刻とユーザー名付きでフォーマット
- `format_conversation_history()`: 会話履歴を文字列にフォーマット
- `format_other_channels()`: 他チャンネルのメッセージをフォーマット

### 3. LiteLLMResponseGenerator の変更

**ファイル**: `src/myao2/infrastructure/llm/response_generator.py`

- `_build_system_prompt()` メソッドを追加
- Context から system_prompt を構築し、messages には system のみを含める
- 会話履歴、現在のメッセージ、他チャンネル情報を全て system_prompt に含める
- 最後に明確な指示を追加

### 4. AutonomousResponseUseCase の変更

**ファイル**: `src/myao2/application/use_cases/autonomous_response.py`

- `_build_auxiliary_context()` → `_build_other_channel_messages()` に変更
- 戻り値を `str | None` から `dict[str, list[Message]]` に変更

### 5. requirements.md の更新

**ファイル**: `requirements.md`

コンテキスト構築の方針を更新:
- チャンネルのメッセージ一覧はLLMのmessagesで構築しない
- 応答すべきスレッド/チャンネルのメッセージ一覧も、他チャンネルの情報も、全てsystem_promptに含める
- 各メッセージには投稿時刻とユーザー名を含める

## 新しい LLM messages 構造

LLM に送信される messages は以下の形式になる:

```
messages = [
    {
        "role": "system",
        "content": """ペルソナの system_prompt

## 会話履歴
[2024-01-01 12:00:00] user1: こんにちは
[2024-01-01 12:01:00] myao: やあ！

## 返答すべきメッセージ
[2024-01-01 12:02:00] user1: 今日の天気は？

## 他のチャンネルでの最近の会話
### #random
- [2024-01-01 12:00:00] user2: 今日は暑いね
- [2024-01-01 12:01:00] user3: エアコンつけたよ

---

上記の会話履歴と参考情報を元に、「返答すべきメッセージ」に対して自然な返答を生成してください。
"""
    }
]
```

## 影響範囲

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/domain/entities/context.py` | メソッド削除、フィールド変更 |
| `src/myao2/domain/services/message_formatter.py` | 新規作成 |
| `src/myao2/infrastructure/llm/response_generator.py` | プロンプト構築ロジック追加 |
| `src/myao2/application/use_cases/autonomous_response.py` | Context作成部分の変更 |
| `requirements.md` | コンテキスト構築の方針を更新 |

## 完了基準

- [x] Context エンティティからメソッドを削除
- [x] Context の `auxiliary_context` を `other_channel_messages` に変更
- [x] message_formatter モジュールを作成
- [x] LiteLLMResponseGenerator でシステムプロンプトを構築
- [x] AutonomousResponseUseCase を更新
- [x] requirements.md を更新
- [x] 全テストが通過
- [x] ruff check / ruff format 通過
- [x] ty check 通過
