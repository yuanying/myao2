"""Memo tools for strands-agents.

LLM が自発的に重要だと思ったことを記憶に残すためのメモツール群。
"""

from datetime import datetime, timezone
from uuid import UUID

from strands import tool
from strands.types.tools import ToolContext

from myao2.domain.entities.memo import Memo, create_memo
from myao2.domain.repositories.memo_repository import MemoRepository

MEMO_REPOSITORY_KEY = "memo_repository"


def get_memo_repository(tool_context: ToolContext) -> MemoRepository:
    """ToolContext から MemoRepository を取得する。

    Args:
        tool_context: ツールコンテキスト

    Returns:
        MemoRepository インスタンス

    Raises:
        RuntimeError: MemoRepository が invocation_state に存在しない場合
    """
    repo = tool_context.invocation_state.get(MEMO_REPOSITORY_KEY)
    if repo is None:
        raise RuntimeError("MemoRepository not found in invocation_state")
    return repo


@tool(context=True)
async def add_memo(
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
        content: メモの内容（50文字程度を推奨、強制ではない。主語を明記すること）
        priority: 優先度（1-5、5が最高）
            - 5: 常に覚えておくべき重要情報（名前、家族、重要な予定）
            - 4: 頻繁に参照すべき情報（好み、興味、定期的な予定）
            - 3: 参考になる情報（一般的な話題、一時的な予定）
            - 2: 補足情報
            - 1: 一時的なメモ
        tags: タグリスト（最大3つ）。既存タグを確認してから指定すること。
        tool_context: ツールコンテキスト

    Returns:
        追加結果メッセージ
    """
    repo = get_memo_repository(tool_context)
    try:
        memo = create_memo(content=content, priority=priority, tags=tags)
    except ValueError as e:
        return f"メモの作成に失敗しました: {e}"

    await repo.save(memo)
    return f"メモを追加しました（ID: {str(memo.id)[:8]}）"


@tool(context=True)
async def edit_memo(
    memo_id: str,
    content: str | None,
    priority: int | None,
    tags: list[str] | None,
    detail: str | None,
    tool_context: ToolContext,
) -> str:
    """既存のメモを編集する。

    情報が古くなった場合や、詳細情報を追記する場合に使用する。
    detailを指定すると詳細情報として上書き更新される。

    Args:
        memo_id: 編集するメモのID
        content: 新しい内容（変更する場合のみ）
        priority: 新しい優先度（変更する場合のみ）
        tags: 新しいタグリスト（変更する場合のみ）
        detail: 詳細情報（上書き更新される）
        tool_context: ツールコンテキスト

    Returns:
        編集結果メッセージ
    """
    repo = get_memo_repository(tool_context)
    try:
        memo_uuid = UUID(memo_id)
    except ValueError:
        return f"無効なメモID: {memo_id}"

    existing = await repo.find_by_id(memo_uuid)
    if existing is None:
        return f"メモが見つかりません（ID: {memo_id}）"

    # 変更がない場合はそのまま保持
    new_content = content if content is not None else existing.content
    new_priority = priority if priority is not None else existing.priority
    new_tags = tags if tags is not None else existing.tags
    new_detail = detail if detail is not None else existing.detail

    try:
        updated = Memo(
            id=existing.id,
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
    return f"メモを更新しました（ID: {memo_id[:8]}）"


@tool(context=True)
async def remove_memo(
    memo_id: str,
    tool_context: ToolContext,
) -> str:
    """メモを削除する。

    不要になったメモを削除する場合に使用する。

    Args:
        memo_id: 削除するメモのID
        tool_context: ツールコンテキスト

    Returns:
        削除結果メッセージ
    """
    repo = get_memo_repository(tool_context)
    try:
        memo_uuid = UUID(memo_id)
    except ValueError:
        return f"無効なメモID: {memo_id}"

    deleted = await repo.delete(memo_uuid)
    if deleted:
        return f"メモを削除しました（ID: {memo_id[:8]}）"
    else:
        return f"メモが見つかりません（ID: {memo_id}）"


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
        tool_context: ツールコンテキスト

    Returns:
        メモ一覧（ID、優先度、タグ、内容、詳細有無を含む）
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
            f"- [{str(memo.id)[:8]}] 優先度{memo.priority} [{tags_str}] "
            f"{memo.content}{detail_marker}"
        )

    return "\n".join(lines)


@tool(context=True)
async def get_memo(
    memo_id: str,
    tool_context: ToolContext,
) -> str:
    """メモの詳細を取得する。

    詳細情報も含めて全て表示する。

    Args:
        memo_id: 取得するメモのID
        tool_context: ツールコンテキスト

    Returns:
        メモの全情報（ID, 優先度, タグ, 内容, 詳細情報, 作成日, 更新日）
    """
    repo = get_memo_repository(tool_context)
    try:
        memo_uuid = UUID(memo_id)
    except ValueError:
        return f"無効なメモID: {memo_id}"

    memo = await repo.find_by_id(memo_uuid)
    if memo is None:
        return f"メモが見つかりません（ID: {memo_id}）"

    tags_str = ", ".join(memo.tags) if memo.tags else "なし"
    lines = [
        "メモ詳細:",
        f"- ID: {str(memo.id)[:8]}",
        f"- 優先度: {memo.priority}",
        f"- タグ: {tags_str}",
        f"- 内容: {memo.content}",
    ]

    if memo.has_detail:
        lines.append(f"- 詳細: {memo.detail}")

    lines.extend(
        [
            f"- 作成日: {memo.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"- 更新日: {memo.updated_at.strftime('%Y-%m-%d %H:%M')}",
        ]
    )

    return "\n".join(lines)


@tool(context=True)
async def list_memo_tags(tool_context: ToolContext) -> str:
    """メモに使用されているタグの一覧を取得する。

    新しいタグを作成する前に、既存のタグを確認するために使用する。
    類似のタグが存在する場合は、新規作成せずにそれを使用すること。

    Args:
        tool_context: ツールコンテキスト

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


MEMO_TOOLS = [
    add_memo,
    edit_memo,
    remove_memo,
    list_memo,
    get_memo,
    list_memo_tags,
]


class MemoToolsFactory:
    """メモツールのファクトリ。

    リポジトリの注入と invocation_state の構築を担当する。
    """

    def __init__(self, memo_repository: MemoRepository) -> None:
        """ファクトリを初期化する。

        Args:
            memo_repository: メモリポジトリ
        """
        self._memo_repository = memo_repository

    def get_invocation_state(self) -> dict:
        """invocation_state を取得する。

        Returns:
            Agent に渡す invocation_state 辞書
        """
        return {MEMO_REPOSITORY_KEY: self._memo_repository}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得する。

        Returns:
            メモツール関数のリスト
        """
        return MEMO_TOOLS
