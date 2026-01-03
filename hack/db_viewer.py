#!/usr/bin/env python3
"""Database viewer script for myao2.

SQLiteデータベースの内容を可視化するCLIツール。

Usage:
    uv run python hack/db_viewer.py stats
    uv run python hack/db_viewer.py channels
    uv run python hack/db_viewer.py users
    uv run python hack/db_viewer.py memories [--scope SCOPE] [--type TYPE]
    uv run python hack/db_viewer.py messages [--channel CH] [--thread TH] [--limit N]
    uv run python hack/db_viewer.py judgments [--channel CHANNEL]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func
from sqlmodel import select

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_dotenv(env_path: Path) -> None:
    """シンプルな .env ファイル読み込み

    Args:
        env_path: .env ファイルのパス
    """
    if not env_path.exists():
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 空行とコメントをスキップ
            if not line or line.startswith("#"):
                continue
            # KEY=VALUE 形式をパース
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # クォートを除去
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                # 既存の環境変数は上書きしない
                if key not in os.environ:
                    os.environ[key] = value


from myao2.config.loader import load_config  # noqa: E402
from myao2.infrastructure.persistence.database import DatabaseManager  # noqa: E402
from myao2.infrastructure.persistence.models import (  # noqa: E402
    ChannelModel,
    JudgmentCacheModel,
    MemoryModel,
    MessageModel,
    UserModel,
)


class TableFormatter:
    """シンプルなテキストテーブルフォーマッター"""

    def __init__(self, max_width: int = 50) -> None:
        self._max_width = max_width

    def truncate(self, text: str, width: int | None = None) -> str:
        """テキストを指定幅で切り詰める"""
        width = width or self._max_width
        if len(text) <= width:
            return text
        return text[: width - 3] + "..."

    def format_datetime(self, dt: datetime | None) -> str:
        """日時を読みやすい形式に変換"""
        if dt is None:
            return "-"
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def print_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        title: str | None = None,
    ) -> None:
        """テーブルを出力"""
        if title:
            print(f"\n=== {title} ===\n")

        if not rows:
            print("(no data)")
            return

        # 列幅を計算
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))

        # ヘッダー出力
        header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        separator = "-+-".join("-" * w for w in widths)
        print(header_line)
        print(separator)

        # 行出力
        for row in rows:
            line = " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
            print(line)

        print(f"\nTotal: {len(rows)} records")


class DatabaseViewer:
    """データベース閲覧クラス"""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db_manager = db_manager
        self._formatter = TableFormatter()

    async def get_stats(self) -> dict[str, int]:
        """各テーブルの行数を取得"""
        stats: dict[str, int] = {}
        models = [
            ("messages", MessageModel),
            ("channels", ChannelModel),
            ("users", UserModel),
            ("memories", MemoryModel),
            ("judgment_caches", JudgmentCacheModel),
        ]

        async with self._db_manager.get_session() as session:
            for name, model in models:
                result = await session.exec(select(func.count()).select_from(model))
                stats[name] = result.one()

        return stats

    async def list_channels(self) -> list[dict[str, Any]]:
        """チャンネル一覧を取得"""
        async with self._db_manager.get_session() as session:
            result = await session.exec(
                select(ChannelModel).order_by(ChannelModel.name)
            )
            channels = result.all()

        return [
            {
                "channel_id": c.channel_id,
                "name": c.name,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in channels
        ]

    async def list_users(self, include_bots: bool = False) -> list[dict[str, Any]]:
        """ユーザー一覧を取得"""
        async with self._db_manager.get_session() as session:
            stmt = select(UserModel).order_by(UserModel.name)
            if not include_bots:
                stmt = stmt.where(UserModel.is_bot == False)  # noqa: E712
            result = await session.exec(stmt)
            users = result.all()

        return [
            {
                "user_id": u.user_id,
                "name": u.name,
                "is_bot": u.is_bot,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in users
        ]

    async def list_memories(
        self,
        scope: str | None = None,
        memory_type: str | None = None,
        scope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """記憶一覧を取得"""
        async with self._db_manager.get_session() as session:
            stmt = select(MemoryModel).order_by(
                MemoryModel.scope, MemoryModel.scope_id, MemoryModel.memory_type
            )
            if scope:
                stmt = stmt.where(MemoryModel.scope == scope)
            if memory_type:
                stmt = stmt.where(MemoryModel.memory_type == memory_type)
            if scope_id:
                stmt = stmt.where(MemoryModel.scope_id == scope_id)

            result = await session.exec(stmt)
            memories = result.all()

        return [
            {
                "scope": m.scope,
                "scope_id": m.scope_id,
                "memory_type": m.memory_type,
                "content": m.content,
                "source_message_count": m.source_message_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in memories
        ]

    async def list_messages(
        self,
        channel_id: str | None = None,
        thread_ts: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """メッセージ一覧を取得"""
        async with self._db_manager.get_session() as session:
            stmt = select(MessageModel).order_by(
                desc(MessageModel.timestamp)  # type: ignore[arg-type]
            )

            if channel_id:
                stmt = stmt.where(MessageModel.channel_id == channel_id)
            if thread_ts:
                stmt = stmt.where(MessageModel.thread_ts == thread_ts)

            stmt = stmt.limit(limit)
            result = await session.exec(stmt)
            messages = result.all()

        return [
            {
                "message_id": m.message_id,
                "channel_id": m.channel_id,
                "user_name": m.user_name,
                "text": m.text,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "thread_ts": m.thread_ts,
            }
            for m in messages
        ]

    async def list_judgments(
        self,
        channel_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """応答判定キャッシュ一覧を取得"""
        async with self._db_manager.get_session() as session:
            stmt = select(JudgmentCacheModel).order_by(
                desc(JudgmentCacheModel.updated_at)  # type: ignore[arg-type]
            )

            if channel_id:
                stmt = stmt.where(JudgmentCacheModel.channel_id == channel_id)

            result = await session.exec(stmt)
            judgments = result.all()

        return [
            {
                "channel_id": j.channel_id,
                "thread_ts": j.thread_ts,
                "should_respond": j.should_respond,
                "confidence": j.confidence,
                "reason": j.reason,
                "next_check_at": (
                    j.next_check_at.isoformat() if j.next_check_at else None
                ),
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            }
            for j in judgments
        ]


def print_stats(stats: dict[str, int], output_format: str) -> None:
    """統計情報を出力"""
    if output_format == "json":
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [[name, str(count)] for name, count in stats.items()]
    formatter.print_table(["Table", "Count"], rows, title="Database Statistics")


def print_channels(channels: list[dict[str, Any]], output_format: str) -> None:
    """チャンネル一覧を出力"""
    if output_format == "json":
        print(json.dumps(channels, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [[c["channel_id"], c["name"], c["updated_at"] or "-"] for c in channels]
    formatter.print_table(["Channel ID", "Name", "Updated At"], rows, title="Channels")


def print_users(users: list[dict[str, Any]], output_format: str) -> None:
    """ユーザー一覧を出力"""
    if output_format == "json":
        print(json.dumps(users, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [
        [
            u["user_id"],
            u["name"],
            "Yes" if u["is_bot"] else "No",
            u["updated_at"] or "-",
        ]
        for u in users
    ]
    formatter.print_table(["User ID", "Name", "Bot", "Updated At"], rows, title="Users")


def print_memories(memories: list[dict[str, Any]], output_format: str) -> None:
    """記憶一覧を出力"""
    if output_format == "json":
        print(json.dumps(memories, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [
        [
            m["scope"],
            formatter.truncate(m["scope_id"], 20),
            m["memory_type"],
            formatter.truncate(m["content"], 50),
            str(m["source_message_count"]),
        ]
        for m in memories
    ]
    formatter.print_table(
        ["Scope", "Scope ID", "Type", "Content (preview)", "Msg Count"],
        rows,
        title="Memories",
    )

    # 詳細表示
    if memories and output_format == "table":
        print("\n--- Memory Details ---")
        for i, m in enumerate(memories, 1):
            print(f"\n[{i}] {m['scope']} / {m['scope_id']} / {m['memory_type']}")
            print("-" * 60)
            print(m["content"])


def print_messages(messages: list[dict[str, Any]], output_format: str) -> None:
    """メッセージ一覧を出力"""
    if output_format == "json":
        print(json.dumps(messages, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [
        [
            m["timestamp"][:19] if m["timestamp"] else "-",
            m["user_name"],
            formatter.truncate(m["text"], 60),
            m["thread_ts"] or "-",
        ]
        for m in messages
    ]
    formatter.print_table(
        ["Timestamp", "User", "Text", "Thread"],
        rows,
        title="Messages",
    )


def print_judgments(judgments: list[dict[str, Any]], output_format: str) -> None:
    """応答判定キャッシュを出力"""
    if output_format == "json":
        print(json.dumps(judgments, indent=2, ensure_ascii=False))
        return

    formatter = TableFormatter()
    rows = [
        [
            j["channel_id"],
            j["thread_ts"] or "-",
            "Yes" if j["should_respond"] else "No",
            f"{j['confidence']:.2f}",
            formatter.truncate(j["reason"], 40),
        ]
        for j in judgments
    ]
    formatter.print_table(
        ["Channel", "Thread", "Respond", "Conf", "Reason"],
        rows,
        title="Judgment Caches",
    )


def create_parser() -> argparse.ArgumentParser:
    """CLIパーサーを作成"""
    parser = argparse.ArgumentParser(
        description="myao2 データベースビューア",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 共通オプション
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="config.yaml のパス (default: config.yaml)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="データベースファイルのパス (config より優先)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="出力形式 (default: table)",
    )

    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # stats
    subparsers.add_parser("stats", help="統計情報を表示")

    # channels
    subparsers.add_parser("channels", help="チャンネル一覧を表示")

    # users
    users_parser = subparsers.add_parser("users", help="ユーザー一覧を表示")
    users_parser.add_argument(
        "--bots",
        action="store_true",
        help="ボットも含める",
    )

    # memories
    memories_parser = subparsers.add_parser("memories", help="記憶一覧を表示")
    memories_parser.add_argument(
        "--scope",
        choices=["workspace", "channel", "thread"],
        help="スコープでフィルタ",
    )
    memories_parser.add_argument(
        "--type",
        choices=["long_term", "short_term"],
        help="記憶タイプでフィルタ",
    )
    memories_parser.add_argument(
        "--scope-id",
        help="スコープIDでフィルタ",
    )

    # messages
    messages_parser = subparsers.add_parser("messages", help="メッセージ一覧を表示")
    messages_parser.add_argument(
        "--channel",
        help="チャンネルIDでフィルタ",
    )
    messages_parser.add_argument(
        "--thread",
        help="スレッドでフィルタ",
    )
    messages_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="表示件数 (default: 20)",
    )

    # judgments
    judgments_parser = subparsers.add_parser(
        "judgments", help="応答判定キャッシュを表示"
    )
    judgments_parser.add_argument(
        "--channel",
        help="チャンネルIDでフィルタ",
    )

    return parser


async def main() -> None:
    """メインエントリポイント"""
    # プロジェクトルートの .env を読み込み
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # データベースパスを決定
    db_path: str
    if args.db:
        db_path = args.db
    else:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        config = load_config(config_path)
        db_path = config.memory.database_path

    # データベースファイルの存在確認
    if db_path != ":memory:" and not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # DatabaseManager を初期化
    db_manager = DatabaseManager(db_path)
    await db_manager.create_tables()  # テーブルがなければ作成（既存には影響しない）
    viewer = DatabaseViewer(db_manager)

    try:
        if args.command == "stats":
            stats = await viewer.get_stats()
            print_stats(stats, args.format)

        elif args.command == "channels":
            channels = await viewer.list_channels()
            print_channels(channels, args.format)

        elif args.command == "users":
            users = await viewer.list_users(include_bots=args.bots)
            print_users(users, args.format)

        elif args.command == "memories":
            memories = await viewer.list_memories(
                scope=args.scope,
                memory_type=args.type,
                scope_id=args.scope_id,
            )
            print_memories(memories, args.format)

        elif args.command == "messages":
            messages = await viewer.list_messages(
                channel_id=args.channel,
                thread_ts=args.thread,
                limit=args.limit,
            )
            print_messages(messages, args.format)

        elif args.command == "judgments":
            judgments = await viewer.list_judgments(channel_id=args.channel)
            print_judgments(judgments, args.format)

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
