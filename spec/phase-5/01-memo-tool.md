# 01: メモ帳ツール - 実装手順書

**Status**: ✅ Completed

## 目標

LLMが自発的に重要だと思ったことを記憶に残すメモ帳ツールを実装する。

## 成果物

応答生成時にLLMが自律的にメモを管理できるボット

- メモ帳ツール: add_memo, edit_memo, remove_memo, list_memo, get_memo, list_memo_tags
- ワークスペース全体で共有されるメモ
- 高優先度メモ + 直近メモの judgment/response プロンプトへの統合

---

## 決定事項サマリー

| 項目 | 決定内容 |
|------|---------|
| スコープ | ワークスペース全体で共有（チャンネル分離なし）|
| 操作タイミング | 応答生成時のみ（strands-agents @tool デコレータ）|
| 優先度 | 5段階（1-5）、優先度4以上をプロンプトに含める（上限20件）|
| メモ並び順 | 優先度降順 → 更新日時降順 |
| タグ機能 | フリータグ（1メモ=最大3タグ、全体=最大20種類）|
| タグデータ設計 | SQLite JSON型（sa_type=JSON）で保存 |
| 自動削除 | なし（手動削除のみ）|
| メモ対象 | 総合的（ユーザー情報 + タスク/予定）|
| プロンプト表示 | 詳細形式（ID, 優先度, タグ, 更新日, 内容）|
| 直近メモ | 最新5件を別セクション表示（重複削除、重要セクション優先）|
| ガイドライン | 詳細ガイドライン（response_query.j2に配置）|

---

## メモ帳システムの構成

### スコープ

| スコープ | 説明 |
|---------|------|
| ワークスペース | ワークスペース全体で共有（チャンネル分離なし）|

### 優先度

| レベル | 説明 |
|-------|------|
| 1 | 低優先度 |
| 2 | やや低優先度 |
| 3 | 通常 |
| 4 | やや高優先度 |
| 5 | 高優先度 |

- 高優先度（4-5）のメモは judgment_query.j2 と response_query.j2 に含まれる（上限20件）
- 直近5件のメモも別セクションで表示（重複除外）

### タグ機能

- 1メモあたり最大3タグ
- 全体で最大20種類
- フリータグ（LLMが自由に作成）
- 既存タグは list_memo_tags で確認してから使用

### 詳細情報

- `detail` フィールドで詳細情報を保存
- edit_memo で上書き更新
- list_memo で「[詳細あり]」表示、get_memo で全文表示

---

## タスク一覧

| # | タスク | 詳細設計書 | 依存 | Status |
|---|--------|-----------|------|--------|
| 01a | Memo エンティティ + MemoRepository Protocol | [01a-memo-domain.md](./01a-memo-domain.md) | - | ✅ |
| 01b | SQLiteMemoRepository + MemoModel | [01b-memo-infrastructure.md](./01b-memo-infrastructure.md) | 01a | ✅ |
| 01c | メモツール関数定義（@tool デコレータ）| [01c-memo-tools.md](./01c-memo-tools.md) | 01b | ✅ |
| 01d | ResponseGenerator統合 + プロンプトテンプレート更新 | [01d-memo-integration.md](./01d-memo-integration.md) | 01c | ✅ |

---

## 実装順序（DAG図）

```
[01a] Memo エンティティ + MemoRepository Protocol
          │
          ↓
[01b] SQLiteMemoRepository + MemoModel
          │
          ↓
[01c] メモツール関数定義（@tool デコレータ）
          │
          ↓
[01d] ResponseGenerator統合 + プロンプトテンプレート更新
```

---

## ツール仕様

### add_memo

新規メモを追加する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| content | str | ✓ | メモの内容（50文字程度を推奨）|
| priority | int | ✓ | 優先度（1-5、5が最高）|
| tags | list[str] | - | タグリスト（最大3つ）|

**出力例:**
```
メモを追加しました（ID: abc123）
```

### edit_memo

既存のメモを編集する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| memo_id | str | ✓ | 編集するメモのID |
| content | str | - | 新しい内容 |
| priority | int | - | 新しい優先度 |
| tags | list[str] | - | 新しいタグリスト |
| detail | str | - | 詳細情報（上書き更新）|

**出力例:**
```
メモを更新しました（ID: abc123）
```

### remove_memo

メモを削除する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| memo_id | str | ✓ | 削除するメモのID |

**出力例:**
```
メモを削除しました（ID: abc123）
```

### list_memo

メモの一覧を取得する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| tag | str | - | 指定したタグを持つメモのみフィルター |
| offset | int | - | スキップする件数（デフォルト: 0）|
| limit | int | - | 取得する最大件数（デフォルト: 10）|

**出力例:**
```
メモ一覧（1-10件 / 全25件）
- [abc123] 優先度5 [user, schedule] ユーザーAは来週水曜日に会議
- [def456] 優先度4 [preference] 好きな食べ物はラーメン [詳細あり]
```

### get_memo

メモの詳細を取得する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| memo_id | str | ✓ | 取得するメモのID |

**出力例:**
```
メモ詳細:
- ID: def456
- 優先度: 4
- タグ: preference
- 内容: 好きな食べ物はラーメン
- 詳細: 特に味噌ラーメンが好み。週に2回は食べている。最寄りの店は「らーめん太郎」。
- 作成日: 2024-01-15 10:30
- 更新日: 2024-01-20 14:00
```

### list_memo_tags

メモに使用されているタグの一覧を取得する。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| なし | - | - | - |

**出力例:**
```
メモタグ一覧（5種類）:
- user: 10件（最終更新: 2024-01-20）
- schedule: 8件（最終更新: 2024-01-19）
- preference: 5件（最終更新: 2024-01-18）
```

---

## プロンプトへの統合

### 表示対象

1. **重要なメモ（優先度4以上）**: 上限20件
2. **直近のメモ**: 最新5件（重要メモと重複する場合は除外）

### 表示形式

**重要なメモセクション:**
```
- **ID**: abc123
  - 優先度: 5
  - タグ: user, schedule
  - 更新日: 2024-01-20 14:00
  - 内容: ユーザーAは来週水曜日に会議
```

**直近のメモセクション:**
```
- **ID**: def456 / 優先度: 3 / タグ: task / タスクAを完了する
```

---

## メモ管理ガイドライン

response_query.j2 に以下のガイドラインを追加:

- **いつメモすべきか**: ユーザーの好み、興味、家族構成、仕事情報、依頼事項、約束、予定など重要な情報を聞いた時
- **優先度の付け方**:
  - 5: 常に覚えておくべき重要情報（名前、家族、重要な予定）
  - 4: 頻繁に参照すべき情報（好み、興味、定期的な予定）
  - 3: 参考になる情報（一般的な話題、一時的な予定）
  - 2: 補足情報
  - 1: 一時的なメモ
- **タグの付け方**: 既存タグを確認してから使用（list_memo_tagsで確認）。類似タグがあればそれを使う
- **詳細情報**: より詳しい情報はedit_memoのdetailパラメータで記録
- **メモの更新**: 情報が古くなったら edit_memo で更新、不要になったら remove_memo で削除
- **重複注意**: 既存メモを確認し、同じ内容のメモを追加しないこと
- **主語を明記**: 複数人のチャットなので「誰が」が重要。人に関連するメモには必ず主語を入れる（例: 「ラーメンが好き」→「○○さんはラーメンが好き」）

---

## 影響を受けるファイル

### 新規作成

| ファイル | 説明 |
|---------|------|
| `src/myao2/domain/entities/memo.py` | Memo エンティティ |
| `src/myao2/domain/repositories/memo_repository.py` | MemoRepository Protocol |
| `src/myao2/infrastructure/persistence/memo_repository.py` | SQLiteMemoRepository |
| `src/myao2/infrastructure/llm/strands/memo_tools.py` | メモツール関数 |

### 変更

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/persistence/models.py` | MemoModel 追加 |
| `src/myao2/domain/entities/context.py` | high_priority_memos, recent_memos フィールド追加 |
| `src/myao2/infrastructure/llm/strands/response_generator.py` | ツール統合 |
| `src/myao2/infrastructure/llm/templates/response_query.j2` | メモセクション追加 |
| `src/myao2/infrastructure/llm/templates/judgment_query.j2` | メモセクション追加 |
| `src/myao2/application/use_cases/autonomous_response.py` | メモ取得・Context設定 |
| `src/myao2/application/use_cases/reply_to_mention.py` | メモ取得・Context設定 |
| `src/myao2/__main__.py` | MemoRepository 初期化 |

### テスト

| ファイル | 説明 |
|---------|------|
| `tests/domain/entities/test_memo.py` | 新規 |
| `tests/infrastructure/persistence/test_memo_repository.py` | 新規 |
| `tests/infrastructure/llm/strands/test_memo_tools.py` | 新規 |

---

## 手動検証

1. アプリケーション起動
2. Slack でボットにメッセージを送信
3. ボットがメモツールを使用してメモを追加することを確認
4. SQLiteでメモを確認: `sqlite3 ./data/memory.db "SELECT * FROM memos;"`
5. 高優先度メモが応答生成時のプロンプトに含まれていることを確認
