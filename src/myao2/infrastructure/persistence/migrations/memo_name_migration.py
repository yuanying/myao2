"""Migration to add name column to memos table."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def migrate_memo_add_name(engine: AsyncEngine) -> None:
    """メモテーブルに name カラムを追加するマイグレーション

    既存のレコードには id の最初の8文字を name として設定する。
    重複がある場合は連番を付加する。

    Args:
        engine: SQLAlchemy AsyncEngine
    """
    async with engine.begin() as conn:
        # 1. memosテーブルが存在するか確認
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='memos'")
        )
        if result.fetchone() is None:
            logger.debug("memos table does not exist, skipping migration")
            return

        # 2. name カラムが既に存在するか確認
        result = await conn.execute(text("PRAGMA table_info(memos)"))
        columns = {row[1] for row in result.fetchall()}
        if "name" in columns:
            logger.debug("name column already exists, skipping migration")
            return

        logger.info("Starting memo name migration...")

        # 3. 既存のメモを取得
        result = await conn.execute(text("SELECT id FROM memos ORDER BY id"))
        existing_memos = result.fetchall()

        if not existing_memos:
            # データがない場合は新しいテーブルを作成して旧テーブルを置き換え
            await _create_new_table(conn)
            await conn.execute(text("DROP TABLE memos"))
            await conn.execute(text("ALTER TABLE memos_new RENAME TO memos"))
            logger.info("Memo name migration completed (no existing data)")
            return

        # 4. name の割り当て（重複時は連番付加）
        name_assignments: dict[str, str] = {}
        used_names: set[str] = set()

        for (memo_id,) in existing_memos:
            base_name = memo_id[:8]
            name = base_name
            counter = 2

            while name in used_names:
                name = f"{base_name}-{counter}"
                counter += 1

            name_assignments[memo_id] = name
            used_names.add(name)

        # 5. 新しいテーブルを作成
        await _create_new_table(conn)

        # 6. データを移行
        for memo_id, name in name_assignments.items():
            await conn.execute(
                text(
                    "INSERT INTO memos_new "
                    "(id, name, content, priority, tags, detail, "
                    "created_at, updated_at) "
                    "SELECT id, :name, content, priority, tags, detail, "
                    "created_at, updated_at FROM memos WHERE id = :memo_id"
                ),
                {"name": name, "memo_id": memo_id},
            )

        # 7. 旧テーブルを削除してリネーム
        await conn.execute(text("DROP TABLE memos"))
        await conn.execute(text("ALTER TABLE memos_new RENAME TO memos"))

        migrated_count = len(name_assignments)
        logger.info(f"Memo name migration completed. Migrated {migrated_count} memos.")


async def _create_new_table(conn) -> None:
    """新しい memos テーブルを作成する"""
    await conn.execute(
        text("""
            CREATE TABLE IF NOT EXISTS memos_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL,
                priority INTEGER NOT NULL,
                tags JSON,
                detail TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_memos_new_priority ON memos_new(priority)")
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_memos_new_updated_at "
            "ON memos_new(updated_at)"
        )
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_memos_new_name ON memos_new(name)")
    )
