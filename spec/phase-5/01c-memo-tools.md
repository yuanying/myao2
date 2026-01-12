# 01c: メモツール関数 - 詳細設計書

**Status: Done**

## 概要

strands-agents の `@tool` デコレータを使用してメモツール関数を定義する。

---

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/strands/memo_tools.py` | メモツール関数、MemoToolsFactory |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/myao2/infrastructure/llm/strands/__init__.py` | memo_tools エクスポート追加 |

## テストファイル

| ファイル | 説明 |
|---------|------|
| `tests/infrastructure/llm/strands/test_memo_tools.py` | メモツール関数のテスト |

---

## 実装方針

### ToolContext によるリポジトリアクセス

strands-agents の `@tool(context=True)` を使用し、`ToolContext.invocation_state` から MemoRepository にアクセスする。

```python
from strands import tool
from strands.types.tools import ToolContext

MEMO_REPOSITORY_KEY = "memo_repository"

def get_memo_repository(tool_context: ToolContext) -> MemoRepository:
    """ToolContext から MemoRepository を取得"""
    repo = tool_context.invocation_state.get(MEMO_REPOSITORY_KEY)
    if repo is None:
        raise RuntimeError("MemoRepository not found in invocation_state")
    return repo
```

### MemoToolsFactory

リポジトリの注入と invocation_state の構築を担当。

```python
class MemoToolsFactory:
    """メモツールのファクトリ"""

    def __init__(self, memo_repository: MemoRepository) -> None:
        self._memo_repository = memo_repository

    def get_invocation_state(self) -> dict:
        """invocation_state を取得"""
        return {MEMO_REPOSITORY_KEY: self._memo_repository}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得"""
        return MEMO_TOOLS
```

---

## ツール関数定義

### add_memo

```python
@tool(context=True)
async def add_memo(
    name: str,
    content: str,
    priority: int,
    tags: list[str] | None,
    tool_context: ToolContext,
) -> str:
    """重要だと思ったことをメモに追加する。

    ユーザーの好み、興味、家族構成、仕事情報、依頼事項、約束、予定など
    重要な情報を聞いた時に使用する。
    複数人のチャットなので「誰が」が重要。人に関連するメモには必ず主語を入れる。

    Args:
        name: メモの名前（ユニーク、1〜32文字）
        content: メモの内容（50文字程度を推奨、強制ではない。主語を明記すること）
        priority: 優先度（1-5、5が最高）
            - 5: 常に覚えておくべき重要情報（名前、家族、重要な予定）
            - 4: 頻繁に参照すべき情報（好み、興味、定期的な予定）
            - 3: 参考になる情報（一般的な話題、一時的な予定）
            - 2: 補足情報
            - 1: 一時的なメモ
        tags: タグリスト（最大3つ）。既存タグを確認してから指定すること。

    Returns:
        追加結果メッセージ
    """
    repo = get_memo_repository(tool_context)

    # 重複チェック
    if await repo.exists_by_name(name):
        return f"メモの名前「{name}」は既に使用されています"

    try:
        memo = create_memo(name=name, content=content, priority=priority, tags=tags)
    except ValueError as e:
        return f"メモの作成に失敗しました: {e}"

    await repo.save(memo)
    return f"メモを追加しました（name: {memo.name}）"
```

### edit_memo

```python
@tool(context=True)
async def edit_memo(
    memo_name: str,
    content: str | None,
    priority: int | None,
    tags: list[str] | None,
    detail: str | None,
    new_name: str | None,
    tool_context: ToolContext,
) -> str:
    """既存のメモを編集する。

    情報が古くなった場合や、詳細情報を追記する場合に使用する。
    detailを指定すると詳細情報として上書き更新される。

    Args:
        memo_name: 編集するメモの名前
        content: 新しい内容（変更する場合のみ）
        priority: 新しい優先度（変更する場合のみ）
        tags: 新しいタグリスト（変更する場合のみ）
        detail: 詳細情報（上書き更新される）
        new_name: 新しい名前（変更する場合のみ）

    Returns:
        編集結果メッセージ
    """
    repo = get_memo_repository(tool_context)

    existing = await repo.find_by_name(memo_name)
    if existing is None:
        return f"メモが見つかりません（name: {memo_name}）"

    # new_name が指定された場合、重複チェック
    if new_name is not None and new_name != existing.name:
        if await repo.exists_by_name(new_name):
            return f"メモの名前「{new_name}」は既に使用されています"

    # 変更がない場合はそのまま保持
    final_name = new_name if new_name is not None else existing.name
    new_content = content if content is not None else existing.content
    new_priority = priority if priority is not None else existing.priority
    new_tags = tags if tags is not None else existing.tags
    new_detail = detail if detail is not None else existing.detail

    try:
        updated = Memo(
            id=existing.id,
            name=final_name,
            content=new_content,
            priority=new_priority,
            tags=new_tags,
            detail=new_detail,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
        )
    except ValueError as e:
        return f"メモの更新に失敗しました: {e}"

    await repo.save(updated)
    return f"メモを更新しました（name: {updated.name}）"
```

### remove_memo

```python
@tool(context=True)
async def remove_memo(
    memo_name: str,
    tool_context: ToolContext,
) -> str:
    """メモを削除する。

    不要になったメモを削除する場合に使用する。

    Args:
        memo_name: 削除するメモの名前

    Returns:
        削除結果メッセージ
    """
    repo = get_memo_repository(tool_context)

    deleted = await repo.delete_by_name(memo_name)
    if deleted:
        return f"メモを削除しました（name: {memo_name}）"
    else:
        return f"メモが見つかりません（name: {memo_name}）"
```

### list_memo

```python
@tool(context=True)
async def list_memo(
    tag: str | None,
    offset: int | None,
    limit: int | None,
    tool_context: ToolContext,
) -> str:
    """メモの一覧を取得する。

    Args:
        tag: 指定したタグを持つメモのみフィルター（optional）
        offset: スキップする件数（ページネーション用、デフォルト: 0）
        limit: 取得する最大件数（デフォルト: 10）

    Returns:
        メモ一覧（name、優先度、タグ、内容、詳細有無を含む）
    """
    repo = get_memo_repository(tool_context)
    offset_val = offset or 0
    limit_val = limit or 10

    if tag:
        memos = await repo.find_by_tag(tag, offset=offset_val, limit=limit_val)
        total = await repo.count(tag=tag)
    else:
        memos = await repo.find_all(offset=offset_val, limit=limit_val)
        total = await repo.count()

    if not memos:
        if tag:
            return f"タグ「{tag}」のメモは見つかりませんでした"
        return "メモがありません"

    start = offset_val + 1
    end = offset_val + len(memos)
    lines = [f"メモ一覧（{start}-{end}件 / 全{total}件）"]

    for memo in memos:
        tags_str = ", ".join(memo.tags) if memo.tags else "なし"
        detail_marker = " [詳細あり]" if memo.has_detail else ""
        lines.append(
            f"- [{memo.name}] 優先度{memo.priority} [{tags_str}] "
            f"{memo.content}{detail_marker}"
        )

    return "\n".join(lines)
```

### get_memo

```python
@tool(context=True)
async def get_memo(
    memo_name: str,
    tool_context: ToolContext,
) -> str:
    """メモの詳細を取得する。

    詳細情報も含めて全て表示する。

    Args:
        memo_name: 取得するメモの名前

    Returns:
        メモの全情報（name, 優先度, タグ, 内容, 詳細情報, 作成日, 更新日）
    """
    repo = get_memo_repository(tool_context)

    memo = await repo.find_by_name(memo_name)
    if memo is None:
        return f"メモが見つかりません（name: {memo_name}）"

    tags_str = ", ".join(memo.tags) if memo.tags else "なし"
    lines = [
        "メモ詳細:",
        f"- name: {memo.name}",
        f"- 優先度: {memo.priority}",
        f"- タグ: {tags_str}",
        f"- 内容: {memo.content}",
    ]

    if memo.has_detail:
        lines.append(f"- 詳細: {memo.detail}")

    lines.extend([
        f"- 作成日: {memo.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"- 更新日: {memo.updated_at.strftime('%Y-%m-%d %H:%M')}",
    ])

    return "\n".join(lines)
```

### list_memo_tags

```python
@tool(context=True)
async def list_memo_tags(tool_context: ToolContext) -> str:
    """メモに使用されているタグの一覧を取得する。

    新しいタグを作成する前に、既存のタグを確認するために使用する。
    類似のタグが存在する場合は、新規作成せずにそれを使用すること。

    Returns:
        タグ名、使用数、最新更新日のリスト
    """
    repo = get_memo_repository(tool_context)
    stats = await repo.get_all_tags_with_stats()

    if not stats:
        return "メモタグがありません"

    lines = [f"メモタグ一覧（{len(stats)}種類）:"]
    for stat in stats:
        date_str = stat.latest_updated_at.strftime("%Y-%m-%d")
        lines.append(f"- {stat.tag}: {stat.count}件（最終更新: {date_str}）")

    return "\n".join(lines)
```

### MEMO_TOOLS

```python
MEMO_TOOLS = [
    add_memo,
    edit_memo,
    remove_memo,
    list_memo,
    get_memo,
    list_memo_tags,
]
```

---

## テスト項目

### TestAddMemo

- 正常な追加
- タグ付きで追加
- 優先度範囲外でエラー
- 空コンテンツでエラー
- 重複名前でエラー
- 空名前でエラー
- 名前32文字超でエラー

### TestEditMemo

- 全フィールド更新
- 一部フィールドのみ更新
- detail 追加
- 名前変更
- 名前変更で重複エラー
- 存在しないメモ

### TestRemoveMemo

- 正常な削除
- 存在しないメモ

### TestListMemo

- 空の場合
- 複数件の場合（name表示確認）
- タグフィルター
- ページネーション
- 詳細ありマーカー

### TestGetMemo

- 正常な取得（name表示確認）
- 詳細情報付き
- 存在しないメモ

### TestListMemoTags

- タグなしの場合
- 複数タグの場合
- ソート順の確認

### TestMemoToolsFactory

- invocation_state の構築
- tools プロパティ
