"""Database management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Import models to register them with SQLModel metadata
from myao2.infrastructure.persistence import models as _models  # noqa: F401
from myao2.infrastructure.persistence.migrations.memo_name_migration import (
    migrate_memo_add_name,
)


class DatabaseManager:
    """データベース管理

    SQLite データベースの初期化、エンジン生成、セッション管理を行う。
    aiosqlite を使用した非同期アクセスをサポート。
    """

    def __init__(self, database_path: str) -> None:
        """初期化

        Args:
            database_path: SQLite データベースファイルのパス
                          ":memory:" を指定するとインメモリDBを使用
        """
        self._database_path = database_path
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def get_engine(self) -> AsyncEngine:
        """SQLAlchemy 非同期エンジンを取得する

        エンジンは遅延初期化され、キャッシュされる。
        データベースファイルの親ディレクトリが存在しない場合は自動作成する。

        Returns:
            AsyncEngine インスタンス
        """
        if self._engine is not None:
            return self._engine

        # Create parent directory for non-memory databases
        if self._database_path != ":memory:":
            db_path = Path(self._database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite+aiosqlite:///{self._database_path}"
        else:
            url = "sqlite+aiosqlite:///:memory:"

        self._engine = create_async_engine(url)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        return self._engine

    async def create_tables(self) -> None:
        """テーブルを作成する

        既存のテーブルがある場合は何もしない。
        マイグレーションも実行する。
        """
        engine = self.get_engine()

        # Run migrations first
        await migrate_memo_add_name(engine)

        # Then create any new tables
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """セッションを取得する（async context manager）

        Yields:
            AsyncSession インスタンス
        """
        self.get_engine()  # Ensures _session_factory is initialized
        assert self._session_factory is not None
        async with self._session_factory() as session:
            yield session

    async def close(self) -> None:
        """データベース接続をクローズする

        エンジンの dispose() を呼び出し、すべての接続を解放する。
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def is_healthy(self) -> bool:
        """データベース接続が正常かどうかを確認する

        簡単なクエリを実行して接続状態を確認する。

        Returns:
            接続が正常な場合は True、それ以外は False
        """
        if self._engine is None:
            return False

        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
